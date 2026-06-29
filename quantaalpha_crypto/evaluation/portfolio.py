from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import pandas as pd

from quantaalpha_crypto.evaluation.panel import CryptoPanel


PortfolioAction = Literal["spot_long", "perp_long", "perp_short"]


@dataclass(frozen=True)
class PortfolioBacktestConfig:
    rebalance_frequency: str
    input_lookback_window: str
    update_frequency: str
    holding_horizon: str
    action: PortfolioAction
    top_quantile: float
    fee_rate: float = 0.0
    slippage_rate: float = 0.0
    initial_equity: float = 1.0


@dataclass(frozen=True)
class PortfolioBacktestResult:
    artifact_type: str
    timing: dict[str, str]
    factor_names: list[str]
    action: PortfolioAction
    metrics: dict[str, float | int | str]
    equity_curve: pd.DataFrame
    cost_breakdown: dict[str, float]
    live_strategy: bool


def run_crypto_portfolio_backtest(
    factor_scores: dict[str, pd.Series],
    pnl_panel: CryptoPanel,
    config: PortfolioBacktestConfig,
) -> PortfolioBacktestResult:
    """Run a research-only crypto portfolio backtest over selected factor scores."""
    _validate_config(config, pnl_panel)
    combined_score = _combine_factor_scores(factor_scores)
    price_column = _price_column_for_action(pnl_panel.data, config.action)
    prices = pnl_panel.data[price_column].astype("float64").sort_index()
    returns = _next_period_returns(prices)
    funding = _next_period_funding(pnl_panel)
    timestamps = sorted(
        set(combined_score.index.get_level_values("timestamp"))
        & set(returns.index.get_level_values("timestamp"))
    )
    rebalance_delta = pd.Timedelta(config.rebalance_frequency)
    direction = -1.0 if config.action == "perp_short" else 1.0

    previous_weights = pd.Series(0.0, index=_symbols(combined_score), dtype="float64")
    active_weights = previous_weights.copy()
    last_rebalance: pd.Timestamp | None = None
    rows = []
    equity = float(config.initial_equity)
    rebalance_count = 0
    total_turnover = 0.0
    total_fee = 0.0
    total_slippage = 0.0
    total_funding = 0.0

    for timestamp in timestamps:
        timestamp = pd.Timestamp(timestamp)
        should_rebalance = (
            last_rebalance is None
            or timestamp - last_rebalance >= rebalance_delta
        )
        if should_rebalance:
            target_weights = _target_weights_at(combined_score, timestamp, config.top_quantile)
            target_weights = target_weights.reindex(previous_weights.index, fill_value=0.0)
            turnover = float((target_weights - previous_weights).abs().sum())
            fee = turnover * config.fee_rate
            slippage = turnover * config.slippage_rate
            active_weights = target_weights
            previous_weights = target_weights
            last_rebalance = timestamp
            rebalance_count += 1
        else:
            turnover = 0.0
            fee = 0.0
            slippage = 0.0

        step_returns = returns.xs(timestamp, level="timestamp", drop_level=True)
        pnl_return = float((active_weights * step_returns.reindex(active_weights.index).fillna(0.0)).sum())
        pnl_return *= direction
        funding_return = 0.0
        if config.action.startswith("perp"):
            step_funding = funding.xs(timestamp, level="timestamp", drop_level=True)
            funding_return = float((active_weights * step_funding.reindex(active_weights.index).fillna(0.0)).sum())
            funding_return *= -direction
        net_return = pnl_return + funding_return - fee - slippage
        equity *= 1.0 + net_return

        total_turnover += turnover
        total_fee += fee
        total_slippage += slippage
        total_funding += funding_return
        rows.append(
            {
                "timestamp": timestamp,
                "gross_return": pnl_return,
                "funding_return": funding_return,
                "fee": fee,
                "slippage": slippage,
                "net_return": net_return,
                "turnover": turnover,
                "equity": equity,
            }
        )

    equity_curve = pd.DataFrame(rows)
    net_returns = equity_curve["net_return"] if not equity_curve.empty else pd.Series(dtype="float64")
    metrics = {
        "metric_basis": "net_after_cost",
        "total_return": float(equity - float(config.initial_equity)),
        "sharpe": _simple_sharpe(net_returns),
        "max_drawdown": _max_drawdown(equity_curve["equity"]) if not equity_curve.empty else 0.0,
        "turnover": total_turnover,
        "total_fee": total_fee,
        "total_slippage": total_slippage,
        "total_funding": total_funding,
        "rebalance_count": rebalance_count,
    }
    return PortfolioBacktestResult(
        artifact_type="crypto_portfolio_backtest",
        timing={
            "input_lookback_window": config.input_lookback_window,
            "update_frequency": config.update_frequency,
            "rebalance_frequency": config.rebalance_frequency,
            "holding_horizon": config.holding_horizon,
        },
        factor_names=sorted(factor_scores),
        action=config.action,
        metrics=metrics,
        equity_curve=equity_curve,
        cost_breakdown={
            "fee": total_fee,
            "slippage": total_slippage,
            "funding": total_funding,
            "turnover": total_turnover,
        },
        live_strategy=False,
    )


def _validate_config(config: PortfolioBacktestConfig, pnl_panel: CryptoPanel) -> None:
    if pnl_panel.data_role != "pnl":
        raise ValueError("pnl_panel must be PnL Data")
    if (
        config.action == "spot_long"
        and pnl_panel.data_product != "spot"
        and "spot_close" not in pnl_panel.data
    ):
        raise ValueError("spot_long requires spot PnL Data")
    if (
        config.action.startswith("perp")
        and pnl_panel.data_product not in ("futures", "mark")
        and "futures_close" not in pnl_panel.data
    ):
        raise ValueError("perpetual portfolio backtest requires futures or mark PnL Data")
    if (
        config.action.startswith("perp")
        and "futures_funding_rate" not in pnl_panel.data
        and "funding_rate" not in pnl_panel.data
    ):
        raise ValueError("perpetual portfolio backtest requires funding_rate or futures_funding_rate")
    if not 0.0 < config.top_quantile <= 1.0:
        raise ValueError("top_quantile must be in (0, 1]")
    for field_name in ("rebalance_frequency", "input_lookback_window", "update_frequency", "holding_horizon"):
        if pd.Timedelta(getattr(config, field_name)) <= pd.Timedelta(0):
            raise ValueError(f"{field_name} must be positive")


def _combine_factor_scores(factor_scores: dict[str, pd.Series]) -> pd.Series:
    if not factor_scores:
        raise ValueError("factor_scores must not be empty")
    frame = pd.concat(
        [score.rename(name) for name, score in factor_scores.items()],
        axis=1,
        join="inner",
    ).dropna(how="all")
    if frame.empty:
        raise ValueError("factor_scores have no overlapping rows")
    ranks = frame.groupby(level="timestamp").rank(pct=True)
    return ranks.mean(axis=1).rename("combined_score")


def _target_weights_at(scores: pd.Series, timestamp: pd.Timestamp, top_quantile: float) -> pd.Series:
    timestamp_scores = scores.xs(timestamp, level="timestamp", drop_level=True).dropna()
    if timestamp_scores.empty:
        return pd.Series(dtype="float64")
    threshold = timestamp_scores.quantile(1.0 - top_quantile)
    selected = timestamp_scores[timestamp_scores >= threshold]
    if selected.empty:
        return pd.Series(0.0, index=timestamp_scores.index, dtype="float64")
    weight = 1.0 / len(selected)
    return pd.Series(weight, index=selected.index, dtype="float64")


def _symbols(scores: pd.Series) -> pd.Index:
    return pd.Index(sorted(scores.index.get_level_values("symbol").unique()), name="symbol")


def _next_period_returns(prices: pd.Series) -> pd.Series:
    pieces = []
    for symbol, symbol_prices in prices.groupby(level="symbol", sort=False):
        pieces.append(symbol_prices.groupby(level="symbol").pct_change().shift(-1))
    return pd.concat(pieces).sort_index().dropna()


def _next_period_funding(pnl_panel: CryptoPanel) -> pd.Series:
    funding_column = _funding_column_for_product(pnl_panel)
    if funding_column is None:
        return pd.Series(0.0, index=pnl_panel.data.index, name="funding")
    return pnl_panel.data[funding_column].astype("float64").fillna(0.0).sort_index()


def _price_column_for_action(data: pd.DataFrame, action: PortfolioAction) -> str:
    preferred = "spot_close" if action == "spot_long" else "futures_close"
    if preferred in data:
        return preferred
    if "close" in data:
        return "close"
    raise ValueError(f"{action} requires {preferred} PnL price data")


def _funding_column_for_product(pnl_panel: CryptoPanel) -> str | None:
    if pnl_panel.data_product == "spot":
        return None
    if "futures_funding_rate" in pnl_panel.data:
        return "futures_funding_rate"
    if "funding_rate" in pnl_panel.data:
        return "funding_rate"
    return None


def _simple_sharpe(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    std = returns.std(ddof=0)
    if std == 0:
        return float("inf") if returns.mean() > 0 else 0.0
    return float(returns.mean() / std)


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


def portfolio_backtest_result_to_dict(result: PortfolioBacktestResult) -> dict:
    payload = asdict(result)
    payload["equity_curve"] = result.equity_curve.to_dict(orient="records")
    for row in payload["equity_curve"]:
        row["timestamp"] = str(row["timestamp"])
    return payload
