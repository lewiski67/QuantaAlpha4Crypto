import pandas as pd

from quantaalpha_crypto import (
    CryptoPanel,
    PortfolioBacktestConfig,
    build_crypto_panel,
    build_round_feedback_context,
    create_crypto_factor_workspace,
    run_crypto_portfolio_backtest,
    write_portfolio_backtest_result,
)


def test_crypto_portfolio_backtest_handles_rebalance_costs_funding_and_equity_curve():
    pnl_panel = _portfolio_pnl_panel()
    scores = {
        "momentum": _score_series([3, 1, 3, 1], [1, 3, 1, 3]),
        "quality": _score_series([2, 1, 2, 1], [1, 2, 1, 2]),
    }

    result = run_crypto_portfolio_backtest(
        factor_scores=scores,
        pnl_panel=pnl_panel,
        config=PortfolioBacktestConfig(
            rebalance_frequency="2min",
            input_lookback_window="4h",
            update_frequency="1min",
            holding_horizon="1min",
            action="perp_long",
            top_quantile=0.5,
            fee_rate=0.001,
            slippage_rate=0.0005,
        ),
    )

    assert result.timing == {
        "input_lookback_window": "4h",
        "update_frequency": "1min",
        "rebalance_frequency": "2min",
        "holding_horizon": "1min",
    }
    assert list(result.equity_curve["timestamp"].astype(str)) == [
        "2026-01-01 00:00:00",
        "2026-01-01 00:01:00",
        "2026-01-01 00:02:00",
    ]
    assert result.metrics["rebalance_count"] == 2
    assert result.metrics["turnover"] > 0
    assert result.metrics["total_fee"] > 0
    assert result.metrics["total_slippage"] > 0
    assert result.metrics["total_funding"] != 0
    assert "sharpe" in result.metrics
    assert result.live_strategy is False


def test_portfolio_backtest_artifact_is_available_to_mining_feedback(tmp_path):
    workspace = create_crypto_factor_workspace(
        output_dir=tmp_path,
        run_id="portfolio_round",
        crypto_data_universe={
            "feature_data": ["fixture"],
            "pnl_data": ["fixture"],
        },
        candidate_horizons=["1min"],
        evaluation_grid=[
            {
                "action": "spot_long",
                "threshold_quantile": 0.8,
                "holding_horizon": "1min",
                "leverage": 1.0,
            }
        ],
        walk_forward_settings={
            "train_window": "1min",
            "validation_window": "1min",
            "test_window": "1min",
            "step": "1min",
        },
    )
    result = run_crypto_portfolio_backtest(
        factor_scores={"momentum": _score_series([3, 1, 3, 1], [1, 3, 1, 3])},
        pnl_panel=_portfolio_pnl_panel(data_product="spot"),
        config=PortfolioBacktestConfig(
            rebalance_frequency="2min",
            input_lookback_window="4h",
            update_frequency="1min",
            holding_horizon="1min",
            action="spot_long",
            top_quantile=0.5,
            fee_rate=0.001,
            slippage_rate=0.0005,
        ),
    )

    reference = write_portfolio_backtest_result(workspace, result, name="accepted_factors")
    feedback = build_round_feedback_context(workspace)

    assert reference == "portfolio_backtests/accepted_factors.json"
    assert (workspace.root / reference).exists()
    assert feedback["portfolio_backtests"][0]["artifact_path"] == reference
    assert feedback["portfolio_backtests"][0]["metrics"]["metric_basis"] == "net_after_cost"
    assert "equity_curve" not in feedback["portfolio_backtests"][0]


def _portfolio_pnl_panel(data_product="futures"):
    panel_data = build_crypto_panel(
        pd.DataFrame(
            [
                {
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 10,
                    "funding_rate": funding_rate,
                }
                for timestamp, btc_close, eth_close, funding_rate in [
                    ("2026-01-01 00:00:00", 100, 100, 0.0001),
                    ("2026-01-01 00:01:00", 110, 90, 0.0001),
                    ("2026-01-01 00:02:00", 121, 81, 0.0001),
                    ("2026-01-01 00:03:00", 133.1, 72.9, 0.0001),
                ]
                for symbol, close in [("BTCUSDT", btc_close), ("ETHUSDT", eth_close)]
            ]
        )
    )
    return CryptoPanel(data=panel_data, data_role="pnl", data_product=data_product)


def _score_series(btc_scores, eth_scores):
    return pd.Series(
        [
            score
            for btc_score, eth_score in zip(btc_scores, eth_scores, strict=True)
            for score in [btc_score, eth_score]
        ],
        index=pd.MultiIndex.from_product(
            [
                pd.to_datetime(
                    [
                        "2026-01-01 00:00:00",
                        "2026-01-01 00:01:00",
                        "2026-01-01 00:02:00",
                        "2026-01-01 00:03:00",
                    ]
                ),
                ["BTCUSDT", "ETHUSDT"],
            ],
            names=["timestamp", "symbol"],
        ),
    )
