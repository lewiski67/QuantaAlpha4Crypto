from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Literal, NotRequired, TypedDict

import pandas as pd

from quantaalpha_crypto.evaluation.factor import FactorEvaluation
from quantaalpha_crypto.evaluation.panel import CryptoPanel


TradingAction = Literal["spot_long", "perp_long", "perp_short"]
CostSource = Literal["fallback", "account", "symbol"]
PnlPanelInput = CryptoPanel | Mapping[str, CryptoPanel]


class EvaluationGridItem(TypedDict):
    action: TradingAction
    threshold_quantile: float
    holding_horizon: str
    leverage: float
    update_frequency: NotRequired[str]
    rebalance_frequency: NotRequired[str]
    score_threshold: NotRequired[float]


@dataclass(frozen=True)
class EvaluationGridTrial:
    action: TradingAction
    threshold_quantile: float
    holding_horizon: pd.Timedelta
    leverage: float
    update_frequency: pd.Timedelta | None = None
    rebalance_frequency: pd.Timedelta | None = None
    score_threshold: float | None = None
    trade_count: int = 0
    gross_return: float = float("nan")
    turnover: float = 0.0
    fee: float = 0.0
    funding_return: float = 0.0
    fee_rate: float = 0.0
    cost_source: CostSource = "fallback"
    uses_cost_fallback: bool = True
    net_return: float = float("nan")
    sharpe: float = float("nan")
    rank_ic: float = float("nan")
    grouped_returns: tuple[dict, ...] = ()
    selected: bool = False
    rejection_reason: str | None = None


@dataclass(frozen=True)
class EvaluationGridResult:
    trials: list[EvaluationGridTrial]
    selected_trial: EvaluationGridTrial | None = None


def build_default_evaluation_grid(
    threshold_quantiles: list[float],
    holding_horizons: list[str],
) -> list[EvaluationGridItem]:
    """Build the first-stage fixed Evaluation Grid."""
    grid: list[EvaluationGridItem] = []
    for threshold_quantile in threshold_quantiles:
        for holding_horizon in holding_horizons:
            grid.append(
                {
                    "action": "spot_long",
                    "threshold_quantile": threshold_quantile,
                    "holding_horizon": holding_horizon,
                    "leverage": 1.0,
                }
            )
            for leverage in (1.0, 2.0, 3.0):
                grid.append(
                    {
                        "action": "perp_long",
                        "threshold_quantile": threshold_quantile,
                        "holding_horizon": holding_horizon,
                        "leverage": leverage,
                    }
                )
            for leverage in (1.0, 2.0, 3.0):
                grid.append(
                    {
                        "action": "perp_short",
                        "threshold_quantile": 1.0 - threshold_quantile,
                        "holding_horizon": holding_horizon,
                        "leverage": leverage,
                    }
                )
    return grid


def evaluate_fixed_grid(
    factor_evaluation: FactorEvaluation,
    pnl_panel: PnlPanelInput,
    grid: list[EvaluationGridItem],
    train_start: str | pd.Timestamp | None = None,
    train_end: str | pd.Timestamp | None = None,
    fee_rate: float = 0.0,
    cost_source: CostSource = "fallback",
    return_cache: dict[tuple, tuple[pd.Series, pd.Series]] | None = None,
) -> EvaluationGridResult:
    """Evaluate a Directional Factor only across the explicitly configured grid."""
    pnl_panels = _build_pnl_panel_lookup(pnl_panel)
    if cost_source not in ("fallback", "account", "symbol"):
        raise ValueError("cost_source must be fallback, account, or symbol")

    trials = []
    if return_cache is None:
        return_cache = {}
    for item in grid:
        trial = _build_trial(item)
        trial_pnl_panel = _pnl_panel_for_trial(trial, pnl_panels)
        price_returns, funding_returns = _cached_forward_returns(
            return_cache,
            trial_pnl_panel,
            trial.holding_horizon,
            trial,
        )
        trials.append(
            _score_trial(
                factor_evaluation=factor_evaluation,
                trial=trial,
                price_returns=price_returns,
                funding_returns=funding_returns,
                train_start=train_start,
                train_end=train_end,
                fee_rate=fee_rate,
                cost_source=cost_source,
            )
        )
    selected_idx = _select_trial_idx(trials)
    if selected_idx is None:
        return EvaluationGridResult(trials=trials)

    trials[selected_idx] = replace(trials[selected_idx], selected=True)
    return EvaluationGridResult(trials=trials, selected_trial=trials[selected_idx])


def _cached_forward_returns(
    cache: dict[tuple, tuple[pd.Series, pd.Series]],
    pnl_panel: CryptoPanel,
    holding_horizon: pd.Timedelta,
    trial: EvaluationGridTrial,
) -> tuple[pd.Series, pd.Series]:
    price_column = _price_column_for_trial(pnl_panel.data, trial)
    funding_column = _funding_column_for_trial(pnl_panel.data, trial)
    key = (id(pnl_panel), holding_horizon, price_column, funding_column)
    if key not in cache:
        cache[key] = (
            _forward_returns(pnl_panel.data, holding_horizon, price_column=price_column),
            _trial_funding_returns(pnl_panel, holding_horizon, funding_column=funding_column),
        )
    return cache[key]


def _build_trial(item: EvaluationGridItem) -> EvaluationGridTrial:
    action = item["action"]
    if action not in ("spot_long", "perp_long", "perp_short"):
        raise ValueError(f"unsupported action: {action}")

    leverage = float(item["leverage"])
    if action.startswith("perp_") and leverage > 10.0:
        raise ValueError("perpetual leverage must be <= 10")
    if action == "spot_long" and leverage != 1.0:
        raise ValueError("spot_long leverage must be 1")

    threshold_quantile = float(item["threshold_quantile"])
    if not 0.0 <= threshold_quantile <= 1.0:
        raise ValueError("threshold_quantile must be between 0 and 1")

    return EvaluationGridTrial(
        action=action,
        threshold_quantile=threshold_quantile,
        holding_horizon=pd.Timedelta(item["holding_horizon"]),
        leverage=leverage,
        update_frequency=_optional_positive_timedelta(item.get("update_frequency"), "update_frequency"),
        rebalance_frequency=_optional_positive_timedelta(item.get("rebalance_frequency"), "rebalance_frequency"),
        score_threshold=(
            float(item["score_threshold"])
            if "score_threshold" in item
            else None
        ),
    )


def _build_pnl_panel_lookup(pnl_panel: PnlPanelInput) -> dict[str, CryptoPanel]:
    if isinstance(pnl_panel, CryptoPanel):
        _validate_pnl_panel(pnl_panel)
        product = pnl_panel.data_product
        if product is None:
            raise ValueError("pnl_panel must define data_product")
        pnl_panels = {product: pnl_panel}
        if "spot_close" in pnl_panel.data:
            pnl_panels.setdefault("spot", pnl_panel)
        if "futures_close" in pnl_panel.data:
            pnl_panels.setdefault("futures", pnl_panel)
        return pnl_panels

    pnl_panels: dict[str, CryptoPanel] = {}
    for product, product_panel in pnl_panel.items():
        _validate_pnl_panel(product_panel)
        if product != product_panel.data_product:
            raise ValueError("pnl_panel mapping keys must match data_product")
        pnl_panels[product] = product_panel
    return pnl_panels


def _validate_pnl_panel(pnl_panel: CryptoPanel) -> None:
    if pnl_panel.data_role != "pnl":
        raise ValueError("pnl_panel must be PnL Data")


def _pnl_panel_for_trial(
    trial: EvaluationGridTrial,
    pnl_panels: dict[str, CryptoPanel],
) -> CryptoPanel:
    if trial.action == "spot_long":
        if "spot" not in pnl_panels:
            raise ValueError("spot_long requires spot PnL Data")
        return pnl_panels["spot"]

    panel = None
    if "futures" in pnl_panels:
        panel = pnl_panels["futures"]
    elif "mark" in pnl_panels:
        panel = pnl_panels["mark"]
    if panel is not None:
        if "futures_funding_rate" not in panel.data and "funding_rate" not in panel.data:
            raise ValueError("perpetual PnL Data requires funding_rate or futures_funding_rate")
        return panel
    raise ValueError("perpetual actions require futures or mark perpetual PnL Data")


def _score_trial(
    factor_evaluation: FactorEvaluation,
    trial: EvaluationGridTrial,
    price_returns: pd.Series,
    funding_returns: pd.Series,
    train_start: str | pd.Timestamp | None,
    train_end: str | pd.Timestamp | None,
    fee_rate: float,
    cost_source: CostSource,
) -> EvaluationGridTrial:
    frame = pd.concat(
        [
            factor_evaluation.scores.rename("score"),
            price_returns.rename("price_return"),
            funding_returns.rename("funding_return"),
        ],
        axis=1,
        join="inner",
    ).dropna()
    frame = _filter_train_window(frame, train_start, train_end)
    frame = _filter_by_frequency(frame, trial.update_frequency)
    if frame.empty:
        return replace(trial, rejection_reason="no_train_rows")

    threshold = (
        trial.score_threshold
        if trial.score_threshold is not None
        else frame["score"].quantile(trial.threshold_quantile)
    )
    if trial.action in ("spot_long", "perp_long"):
        trades = frame[frame["score"] >= threshold]
        direction = 1.0
    else:
        trades = frame[frame["score"] <= threshold]
        direction = -1.0
    trades = _filter_by_frequency(trades, trial.rebalance_frequency)

    if trades.empty:
        return replace(trial, rejection_reason="no_trades")

    gross_trade_returns = direction * trial.leverage * trades["price_return"]
    funding_trade_returns = -direction * trial.leverage * trades["funding_return"]
    turnover = 2.0 * trial.leverage * len(trades)
    trade_fee = float(fee_rate) * 2.0 * trial.leverage
    net_trade_returns = gross_trade_returns + funding_trade_returns - trade_fee
    sharpe = _annualized_decision_period_sharpe(
        net_trade_returns,
        decision_timestamps=frame.index.get_level_values("timestamp"),
    )
    rank_ic = _rank_ic(frame["score"], frame["price_return"])
    grouped_returns = _grouped_forward_returns(frame)
    return replace(
        trial,
        score_threshold=float(threshold),
        trade_count=len(net_trade_returns),
        gross_return=float(gross_trade_returns.sum()),
        turnover=float(turnover),
        fee=float(fee_rate * turnover),
        funding_return=float(funding_trade_returns.sum()),
        fee_rate=float(fee_rate),
        cost_source=cost_source,
        uses_cost_fallback=cost_source == "fallback",
        net_return=float(net_trade_returns.sum()),
        sharpe=sharpe,
        rank_ic=rank_ic,
        grouped_returns=grouped_returns,
        rejection_reason=None if net_trade_returns.sum() > 0 else "non_positive_net_return",
    )


def _filter_train_window(
    frame: pd.DataFrame,
    train_start: str | pd.Timestamp | None,
    train_end: str | pd.Timestamp | None,
) -> pd.DataFrame:
    timestamps = frame.index.get_level_values("timestamp")
    mask = pd.Series(True, index=frame.index)
    if train_start is not None:
        mask &= timestamps >= pd.Timestamp(train_start)
    if train_end is not None:
        mask &= timestamps < pd.Timestamp(train_end)
    return frame[mask.to_numpy()]


def _optional_positive_timedelta(value: str | None, field_name: str) -> pd.Timedelta | None:
    if value is None:
        return None
    delta = pd.Timedelta(value)
    if delta <= pd.Timedelta(0):
        raise ValueError(f"{field_name} must be positive")
    return delta


def _filter_by_frequency(frame: pd.DataFrame, frequency: pd.Timedelta | None) -> pd.DataFrame:
    if frequency is None or frame.empty:
        return frame
    timestamps = frame.index.get_level_values("timestamp")
    symbols = frame.index.get_level_values("symbol")
    last_by_symbol: dict[str, pd.Timestamp] = {}
    keep = []
    for timestamp, symbol in zip(timestamps, symbols):
        timestamp = pd.Timestamp(timestamp)
        symbol = str(symbol)
        last = last_by_symbol.get(symbol)
        should_keep = last is None or timestamp - last >= frequency
        keep.append(should_keep)
        if should_keep:
            last_by_symbol[symbol] = timestamp
    return frame[keep]


def _select_trial_idx(trials: list[EvaluationGridTrial]) -> int | None:
    candidates = [
        (idx, trial)
        for idx, trial in enumerate(trials)
        if trial.trade_count > 0 and trial.net_return > 0 and pd.notna(trial.sharpe)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: (-candidate[1].sharpe, candidate[1].leverage))[0]


def _trial_funding_returns(
    pnl_panel: CryptoPanel,
    holding_horizon: pd.Timedelta,
    funding_column: str | None,
) -> pd.Series:
    if pnl_panel.data_product == "spot":
        return pd.Series(0.0, index=pnl_panel.data.index, name="funding_return")
    return _forward_funding(pnl_panel.data, holding_horizon, funding_column=funding_column)


def _forward_returns(
    data: pd.DataFrame,
    horizon: pd.Timedelta,
    price_column: str = "close",
) -> pd.Series:
    pieces = []
    for symbol, symbol_data in data.sort_index().groupby(level="symbol", sort=False):
        close = symbol_data[price_column].astype("float64")
        timestamps = close.index.get_level_values("timestamp")
        future_index = pd.MultiIndex.from_arrays(
            [timestamps + horizon, [symbol] * len(timestamps)],
            names=["timestamp", "symbol"],
        )
        future_close = close.reindex(future_index)
        future_close.index = close.index
        pieces.append(future_close / close - 1.0)

    if not pieces:
        return pd.Series(dtype="float64", name="pnl_return")

    return pd.concat(pieces).sort_index()


def _forward_funding(
    data: pd.DataFrame,
    horizon: pd.Timedelta,
    funding_column: str | None = "funding_rate",
) -> pd.Series:
    if funding_column is None or funding_column not in data:
        return pd.Series(0.0, index=data.index, name="funding")

    pieces = []
    for symbol, symbol_data in data.sort_index().groupby(level="symbol", sort=False):
        funding = symbol_data[funding_column].astype("float64").fillna(0.0)
        cumulative_funding = funding.cumsum()
        timestamps = funding.index.get_level_values("timestamp")
        future_index = pd.MultiIndex.from_arrays(
            [timestamps + horizon, [symbol] * len(timestamps)],
            names=["timestamp", "symbol"],
        )
        future_funding = cumulative_funding.reindex(future_index)
        future_funding.index = funding.index
        pieces.append(future_funding - cumulative_funding)

    if not pieces:
        return pd.Series(dtype="float64", name="funding")

    return pd.concat(pieces).sort_index()


def _price_column_for_trial(data: pd.DataFrame, trial: EvaluationGridTrial) -> str:
    preferred = "spot_close" if trial.action == "spot_long" else "futures_close"
    if preferred in data:
        return preferred
    if "close" in data:
        return "close"
    raise ValueError(f"{trial.action} requires {preferred} PnL price data")


def _funding_column_for_trial(data: pd.DataFrame, trial: EvaluationGridTrial) -> str | None:
    if trial.action == "spot_long":
        return None
    if "futures_funding_rate" in data:
        return "futures_funding_rate"
    if "funding_rate" in data:
        return "funding_rate"
    return None


def _simple_sharpe(returns: pd.Series) -> float:
    if returns.empty:
        return float("nan")
    mean = returns.mean()
    std = returns.std(ddof=0)
    if std == 0:
        if mean > 0:
            return float("inf")
        if mean < 0:
            return float("-inf")
        return 0.0
    return float(mean / std)


def _rank_ic(scores: pd.Series, returns: pd.Series) -> float:
    if len(scores) < 2:
        return float("nan")
    if scores.nunique(dropna=True) < 2 or returns.nunique(dropna=True) < 2:
        return float("nan")
    return float(scores.rank().corr(returns.rank()))


def _grouped_forward_returns(frame: pd.DataFrame, groups: int = 2) -> tuple[dict, ...]:
    if frame.empty:
        return ()
    group_count = min(groups, len(frame))
    grouped_frame = frame.copy()
    grouped_frame["group"] = pd.qcut(
        grouped_frame["score"].rank(method="first"),
        q=group_count,
        labels=range(1, group_count + 1),
    )
    grouped = grouped_frame.groupby("group", observed=False)["price_return"].mean()
    return tuple(
        {
            "group": int(group),
            "mean_forward_return": float(mean_forward_return),
        }
        for group, mean_forward_return in grouped.items()
    )


def _annualized_decision_period_sharpe(
    trade_returns: pd.Series,
    decision_timestamps: pd.Index,
) -> float:
    if trade_returns.empty:
        return float("nan")
    unique_timestamps = pd.Index(decision_timestamps).drop_duplicates().sort_values()
    if len(unique_timestamps) < 2:
        return _simple_sharpe(trade_returns)
    period_returns = (
        trade_returns.groupby(level="timestamp").sum()
        .reindex(unique_timestamps, fill_value=0.0)
    )
    return _simple_sharpe(period_returns) * _annualization_factor(unique_timestamps)


def _annualization_factor(timestamps: pd.Index) -> float:
    if len(timestamps) < 2:
        return 1.0
    diffs = pd.Series(timestamps).sort_values().diff().dropna()
    if diffs.empty:
        return 1.0
    median_delta = diffs.median()
    if median_delta <= pd.Timedelta(0):
        return 1.0
    periods_per_year = pd.Timedelta(days=365) / median_delta
    return float(periods_per_year ** 0.5)
