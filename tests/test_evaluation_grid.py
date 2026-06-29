import pandas as pd
import pytest

import quantaalpha_crypto.evaluation.grid as grid_module
from quantaalpha_crypto import (
    CryptoPanel,
    build_default_evaluation_grid,
    build_crypto_panel,
    evaluate_directional_factor,
    evaluate_fixed_grid,
)


def test_evaluate_fixed_grid_uses_only_configured_trials_and_rejects_excess_leverage():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "BTCUSDT",
                "open": 101,
                "high": 102,
                "low": 100,
                "close": 101,
                "volume": 10,
            },
        ]
    )
    panel_data = build_crypto_panel(raw)
    panel = CryptoPanel(data=panel_data, data_role="feature")
    spot_pnl_panel = CryptoPanel(data=panel_data, data_role="pnl", data_product="spot")
    futures_pnl_panel = CryptoPanel(
        data=panel_data.assign(funding_rate=0.0),
        data_role="pnl",
        data_product="futures",
    )
    factor_evaluation = evaluate_directional_factor(
        panel,
        lambda data: data["close"],
        horizon="1min",
    )
    grid = [
        {
            "action": "spot_long",
            "threshold_quantile": 0.8,
            "holding_horizon": "1min",
            "leverage": 1.0,
        },
        {
            "action": "perp_short",
            "threshold_quantile": 0.2,
            "holding_horizon": "1min",
            "leverage": 3.0,
        },
    ]

    result = evaluate_fixed_grid(factor_evaluation, pnl_panel=futures_pnl_panel, grid=grid[1:])

    assert [
        (
            trial.action,
            trial.threshold_quantile,
            trial.holding_horizon,
            trial.leverage,
        )
        for trial in result.trials
    ] == [
        ("perp_short", 0.2, pd.Timedelta("1min"), 3.0),
    ]

    spot_result = evaluate_fixed_grid(
        factor_evaluation,
        pnl_panel=spot_pnl_panel,
        grid=grid[:1],
    )

    assert [
        (
            trial.action,
            trial.threshold_quantile,
            trial.holding_horizon,
            trial.leverage,
        )
        for trial in spot_result.trials
    ] == [
        ("spot_long", 0.8, pd.Timedelta("1min"), 1.0),
    ]

    with pytest.raises(ValueError, match="leverage.*10"):
        evaluate_fixed_grid(
            factor_evaluation,
            pnl_panel=futures_pnl_panel,
            grid=[
                {
                    "action": "perp_long",
                    "threshold_quantile": 0.8,
                    "holding_horizon": "1min",
                    "leverage": 11.0,
                }
            ],
        )


def test_default_evaluation_grid_maps_short_candidates_to_lower_score_tail():
    grid = build_default_evaluation_grid(
        threshold_quantiles=[0.8],
        holding_horizons=["1min"],
    )

    assert [
        (
            item["action"],
            item["threshold_quantile"],
            item["holding_horizon"],
            item["leverage"],
        )
        for item in grid
    ] == [
        ("spot_long", 0.8, "1min", 1.0),
        ("perp_long", 0.8, "1min", 1.0),
        ("perp_long", 0.8, "1min", 2.0),
        ("perp_long", 0.8, "1min", 3.0),
        ("perp_short", 0.19999999999999996, "1min", 1.0),
        ("perp_short", 0.19999999999999996, "1min", 2.0),
        ("perp_short", 0.19999999999999996, "1min", 3.0),
    ]


def test_evaluate_fixed_grid_accepts_product_pnl_mapping_for_mixed_actions():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "BTCUSDT",
                "open": 101,
                "high": 102,
                "low": 100,
                "close": 101,
                "volume": 10,
            },
        ]
    )
    panel_data = build_crypto_panel(raw)
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    spot_pnl_panel = CryptoPanel(data=panel_data, data_role="pnl", data_product="spot")
    futures_pnl_panel = CryptoPanel(
        data=panel_data.assign(funding_rate=0.0),
        data_role="pnl",
        data_product="futures",
    )
    factor_evaluation = evaluate_directional_factor(
        feature_panel,
        lambda data: data["close"],
        horizon="1min",
    )

    result = evaluate_fixed_grid(
        factor_evaluation,
        pnl_panel={"spot": spot_pnl_panel, "futures": futures_pnl_panel},
        grid=build_default_evaluation_grid(
            threshold_quantiles=[0.8],
            holding_horizons=["1min"],
        ),
    )

    assert [
        (trial.action, trial.leverage)
        for trial in result.trials
    ] == [
        ("spot_long", 1.0),
        ("perp_long", 1.0),
        ("perp_long", 2.0),
        ("perp_long", 3.0),
        ("perp_short", 1.0),
        ("perp_short", 2.0),
        ("perp_short", 3.0),
    ]


def test_evaluate_fixed_grid_uses_action_product_prefixed_pnl_columns():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 100,
                "high": 100,
                "low": 100,
                "close": 100,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "BTCUSDT",
                "open": 100,
                "high": 100,
                "low": 100,
                "close": 100,
                "volume": 10,
            },
        ]
    )
    panel_data = build_crypto_panel(raw)
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    spot_pnl_panel = CryptoPanel(
        data=panel_data.rename(columns={"close": "spot_close"}).drop(
            columns=["open", "high", "low", "volume"]
        ),
        data_role="pnl",
        data_product="spot",
    )
    futures_pnl_panel = CryptoPanel(
        data=panel_data.rename(columns={"close": "futures_close"})
        .drop(columns=["open", "high", "low", "volume"])
        .assign(futures_funding_rate=0.0),
        data_role="pnl",
        data_product="futures",
    )
    spot_pnl_panel = CryptoPanel(
        data=spot_pnl_panel.data.assign(spot_close=[100.0, 110.0]),
        data_role="pnl",
        data_product="spot",
    )
    futures_pnl_panel = CryptoPanel(
        data=futures_pnl_panel.data.assign(futures_close=[100.0, 90.0]),
        data_role="pnl",
        data_product="futures",
    )
    factor_evaluation = evaluate_directional_factor(
        feature_panel,
        lambda data: pd.Series(1.0, index=data.index),
        horizon="1min",
    )

    result = evaluate_fixed_grid(
        factor_evaluation,
        pnl_panel={"spot": spot_pnl_panel, "futures": futures_pnl_panel},
        grid=[
            {
                "action": "spot_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            },
            {
                "action": "perp_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            },
        ],
    )

    assert result.trials[0].gross_return == pytest.approx(0.1)
    assert result.trials[1].gross_return == pytest.approx(-0.1)


def test_evaluate_fixed_grid_can_route_mixed_actions_on_one_prefixed_pnl_panel():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 100,
                "high": 100,
                "low": 100,
                "close": 100,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "BTCUSDT",
                "open": 100,
                "high": 100,
                "low": 100,
                "close": 100,
                "volume": 10,
            },
        ]
    )
    panel_data = build_crypto_panel(raw)
    prefixed_pnl = panel_data.drop(columns=["open", "high", "low", "close", "volume"]).assign(
        spot_close=[100.0, 110.0],
        futures_close=[100.0, 90.0],
        futures_funding_rate=0.0,
    )
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    pnl_panel = CryptoPanel(data=prefixed_pnl, data_role="pnl", data_product="futures")
    factor_evaluation = evaluate_directional_factor(
        feature_panel,
        lambda data: pd.Series(1.0, index=data.index),
        horizon="1min",
    )

    result = evaluate_fixed_grid(
        factor_evaluation,
        pnl_panel=pnl_panel,
        grid=[
            {
                "action": "spot_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            },
            {
                "action": "perp_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            },
        ],
    )

    assert result.trials[0].gross_return == pytest.approx(0.1)
    assert result.trials[1].gross_return == pytest.approx(-0.1)


def test_evaluate_fixed_grid_selects_winner_from_train_window_and_prefers_lower_leverage_on_tie():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "BTCUSDT",
                "open": 110,
                "high": 111,
                "low": 109,
                "close": 110,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:02:00",
                "symbol": "BTCUSDT",
                "open": 115.5,
                "high": 116,
                "low": 115,
                "close": 115.5,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:03:00",
                "symbol": "BTCUSDT",
                "open": 60,
                "high": 61,
                "low": 59,
                "close": 60,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:04:00",
                "symbol": "BTCUSDT",
                "open": 30,
                "high": 31,
                "low": 29,
                "close": 30,
                "volume": 10,
            },
        ]
    )
    panel_data = build_crypto_panel(raw)
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    pnl_panel = CryptoPanel(
        data=panel_data.assign(funding_rate=0.0),
        data_role="pnl",
        data_product="futures",
    )
    factor_evaluation = evaluate_directional_factor(
        feature_panel,
        lambda data: data["close"],
        horizon="1min",
    )

    result = evaluate_fixed_grid(
        factor_evaluation,
        pnl_panel=pnl_panel,
        grid=[
            {
                "action": "perp_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 2.0,
            },
            {
                "action": "perp_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            },
            {
                "action": "perp_short",
                "threshold_quantile": 1.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            },
        ],
        train_start="2026-01-01 00:00:00",
        train_end="2026-01-01 00:02:00",
    )

    assert result.selected_trial is not None
    assert result.selected_trial.action == "perp_long"
    assert result.selected_trial.leverage == 1.0
    assert [(trial.trade_count, trial.selected) for trial in result.trials] == [
        (2, False),
        (2, True),
        (2, False),
    ]


def test_evaluate_fixed_grid_applies_perpetual_funding_to_returns():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "BTCUSDT",
                "open": 101,
                "high": 102,
                "low": 100,
                "close": 101,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:02:00",
                "symbol": "BTCUSDT",
                "open": 102.01,
                "high": 103,
                "low": 102,
                "close": 102.01,
                "volume": 10,
            },
        ]
    )
    panel_data = build_crypto_panel(raw)
    futures_data = panel_data.assign(funding_rate=[0.0, 0.001, 0.002])
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    futures_pnl_panel = CryptoPanel(data=futures_data, data_role="pnl", data_product="futures")
    factor_evaluation = evaluate_directional_factor(
        feature_panel,
        lambda data: data["close"],
        horizon="1min",
    )

    result = evaluate_fixed_grid(
        factor_evaluation,
        pnl_panel=futures_pnl_panel,
        grid=[
            {
                "action": "perp_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            },
            {
                "action": "perp_short",
                "threshold_quantile": 1.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            },
        ],
    )

    assert result.trials[0].gross_return == pytest.approx(0.02)
    assert result.trials[0].funding_return == pytest.approx(-0.003)
    assert result.trials[0].net_return == pytest.approx(0.017)
    assert result.trials[1].gross_return == pytest.approx(-0.02)
    assert result.trials[1].funding_return == pytest.approx(0.003)
    assert result.trials[1].net_return == pytest.approx(-0.017)


def test_evaluate_fixed_grid_exposes_round_trip_turnover_and_cost_adjusted_return():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "BTCUSDT",
                "open": 101,
                "high": 102,
                "low": 100,
                "close": 101,
                "volume": 10,
            },
        ]
    )
    panel_data = build_crypto_panel(raw)
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    spot_pnl_panel = CryptoPanel(data=panel_data, data_role="pnl", data_product="spot")
    factor_evaluation = evaluate_directional_factor(
        feature_panel,
        lambda data: data["close"],
        horizon="1min",
    )

    result = evaluate_fixed_grid(
        factor_evaluation,
        pnl_panel=spot_pnl_panel,
        grid=[
            {
                "action": "spot_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            }
        ],
        fee_rate=0.001,
    )

    trial = result.trials[0]
    assert trial.turnover == pytest.approx(2.0)
    assert trial.fee == pytest.approx(0.002)
    assert trial.net_return == pytest.approx(0.008)


def test_evaluate_fixed_grid_respects_rebalance_frequency_on_trade_triggers():
    raw = pd.DataFrame(
        [
            {
                "timestamp": timestamp,
                "symbol": "BTCUSDT",
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 10,
            }
            for timestamp, close in [
                ("2026-01-01 00:00:00", 100),
                ("2026-01-01 00:01:00", 101),
                ("2026-01-01 00:02:00", 102),
                ("2026-01-01 00:03:00", 103),
            ]
        ]
    )
    panel_data = build_crypto_panel(raw)
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    pnl_panel = CryptoPanel(data=panel_data, data_role="pnl", data_product="spot")
    factor_evaluation = evaluate_directional_factor(
        feature_panel,
        lambda data: pd.Series(1.0, index=data.index),
        horizon="1min",
    )

    result = evaluate_fixed_grid(
        factor_evaluation,
        pnl_panel=pnl_panel,
        grid=[
            {
                "action": "spot_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
                "rebalance_frequency": "2min",
            }
        ],
    )

    assert result.trials[0].trade_count == 2
    assert result.trials[0].turnover == pytest.approx(4.0)


def test_evaluate_fixed_grid_respects_update_frequency_before_trade_selection():
    raw = pd.DataFrame(
        [
            {
                "timestamp": timestamp,
                "symbol": "BTCUSDT",
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 10,
            }
            for timestamp, close in [
                ("2026-01-01 00:00:00", 100),
                ("2026-01-01 00:01:00", 101),
                ("2026-01-01 00:02:00", 102),
                ("2026-01-01 00:03:00", 103),
            ]
        ]
    )
    panel_data = build_crypto_panel(raw)
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    pnl_panel = CryptoPanel(data=panel_data, data_role="pnl", data_product="spot")
    factor_evaluation = evaluate_directional_factor(
        feature_panel,
        lambda data: pd.Series(1.0, index=data.index),
        horizon="1min",
    )

    result = evaluate_fixed_grid(
        factor_evaluation,
        pnl_panel=pnl_panel,
        grid=[
            {
                "action": "spot_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
                "update_frequency": "2min",
            }
        ],
    )

    assert result.trials[0].trade_count == 2


def test_evaluate_fixed_grid_records_binance_cost_fallback_metadata():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "BTCUSDT",
                "open": 101,
                "high": 102,
                "low": 100,
                "close": 101,
                "volume": 10,
            },
        ]
    )
    panel_data = build_crypto_panel(raw)
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    pnl_panel = CryptoPanel(data=panel_data, data_role="pnl", data_product="spot")
    factor_evaluation = evaluate_directional_factor(
        feature_panel,
        lambda data: data["close"],
        horizon="1min",
    )

    result = evaluate_fixed_grid(
        factor_evaluation,
        pnl_panel=pnl_panel,
        grid=[
            {
                "action": "spot_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            }
        ],
        fee_rate=0.001,
        cost_source="fallback",
    )

    trial = result.trials[0]
    assert trial.cost_source == "fallback"
    assert trial.uses_cost_fallback is True
    assert trial.fee_rate == pytest.approx(0.001)
    assert trial.fee == pytest.approx(0.002)


def test_evaluate_fixed_grid_reports_annualized_decision_period_sharpe():
    raw = pd.DataFrame(
        [
            {
                "timestamp": timestamp,
                "symbol": "BTCUSDT",
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 10,
            }
            for timestamp, close in [
                ("2026-01-01 00:00:00", 100),
                ("2026-01-01 00:01:00", 101),
                ("2026-01-01 00:02:00", 103),
                ("2026-01-01 00:03:00", 104),
            ]
        ]
    )
    panel_data = build_crypto_panel(raw)
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    pnl_panel = CryptoPanel(data=panel_data, data_role="pnl", data_product="spot")
    factor_evaluation = evaluate_directional_factor(
        feature_panel,
        lambda data: pd.Series(1.0, index=data.index),
        horizon="1min",
    )

    result = evaluate_fixed_grid(
        factor_evaluation,
        pnl_panel=pnl_panel,
        grid=[
            {
                "action": "spot_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            }
        ],
    )

    trade_returns = pd.Series([0.01, 0.01980198019801982, 0.009708737864077666])
    raw_trade_sharpe = trade_returns.mean() / trade_returns.std(ddof=0)
    assert result.trials[0].sharpe > raw_trade_sharpe * 100


def test_evaluate_fixed_grid_requires_matching_pnl_product_for_action():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "BTCUSDT",
                "open": 101,
                "high": 102,
                "low": 100,
                "close": 101,
                "volume": 10,
            },
        ]
    )
    panel_data = build_crypto_panel(raw)
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    spot_pnl_panel = CryptoPanel(data=panel_data, data_role="pnl", data_product="spot")
    futures_pnl_panel = CryptoPanel(
        data=panel_data.assign(funding_rate=0.0),
        data_role="pnl",
        data_product="futures",
    )
    factor_evaluation = evaluate_directional_factor(
        feature_panel,
        lambda data: data["close"],
        horizon="1min",
    )

    evaluate_fixed_grid(
        factor_evaluation,
        pnl_panel=spot_pnl_panel,
        grid=[
            {
                "action": "spot_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            }
        ],
    )
    evaluate_fixed_grid(
        factor_evaluation,
        pnl_panel=futures_pnl_panel,
        grid=[
            {
                "action": "perp_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            }
        ],
    )

    with pytest.raises(ValueError, match="spot PnL Data"):
        evaluate_fixed_grid(
            factor_evaluation,
            pnl_panel=futures_pnl_panel,
            grid=[
                {
                    "action": "spot_long",
                    "threshold_quantile": 0.0,
                    "holding_horizon": "1min",
                    "leverage": 1.0,
                }
            ],
        )
    with pytest.raises(ValueError, match="perpetual PnL Data"):
        evaluate_fixed_grid(
            factor_evaluation,
            pnl_panel=spot_pnl_panel,
            grid=[
                {
                    "action": "perp_short",
                    "threshold_quantile": 0.0,
                    "holding_horizon": "1min",
                    "leverage": 1.0,
                }
            ],
        )


def test_evaluate_fixed_grid_caches_forward_returns_per_panel_and_horizon(monkeypatch):
    raw = pd.DataFrame(
        [
            {
                "timestamp": timestamp,
                "symbol": "BTCUSDT",
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 10,
            }
            for timestamp, close in [
                ("2026-01-01 00:00:00", 100),
                ("2026-01-01 00:01:00", 101),
                ("2026-01-01 00:02:00", 102),
            ]
        ]
    )
    panel_data = build_crypto_panel(raw)
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    futures_pnl_panel = CryptoPanel(
        data=panel_data.assign(funding_rate=0.0),
        data_role="pnl",
        data_product="futures",
    )
    factor_evaluation = evaluate_directional_factor(
        feature_panel,
        lambda data: data["close"],
        horizon="1min",
    )
    call_counts = {"price": 0, "funding": 0}
    original_forward_returns = grid_module._forward_returns
    original_forward_funding = grid_module._forward_funding

    def counting_forward_returns(data, horizon, **kwargs):
        call_counts["price"] += 1
        return original_forward_returns(data, horizon, **kwargs)

    def counting_forward_funding(data, horizon, **kwargs):
        call_counts["funding"] += 1
        return original_forward_funding(data, horizon, **kwargs)

    monkeypatch.setattr(grid_module, "_forward_returns", counting_forward_returns)
    monkeypatch.setattr(grid_module, "_forward_funding", counting_forward_funding)

    evaluate_fixed_grid(
        factor_evaluation,
        pnl_panel=futures_pnl_panel,
        grid=[
            {
                "action": "perp_long",
                "threshold_quantile": 0.8,
                "holding_horizon": "1min",
                "leverage": 1.0,
            },
            {
                "action": "perp_long",
                "threshold_quantile": 0.8,
                "holding_horizon": "1min",
                "leverage": 2.0,
            },
            {
                "action": "perp_short",
                "threshold_quantile": 0.2,
                "holding_horizon": "1min",
                "leverage": 1.0,
            },
        ],
    )

    assert call_counts == {"price": 1, "funding": 1}
