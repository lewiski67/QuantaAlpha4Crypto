import pandas as pd
import pytest

import quantaalpha_crypto.evaluation.grid as grid_module
from quantaalpha_crypto import (
    CryptoPanel,
    WalkForwardWindow,
    build_crypto_panel,
    build_walk_forward_windows,
    evaluate_directional_factor,
    evaluate_walk_forward,
)


def test_default_walk_forward_schedule_uses_180d_30d_30d_windows_with_30d_step():
    windows = build_walk_forward_windows(
        start="2026-01-01",
        end="2026-10-01",
    )

    assert windows == [
        WalkForwardWindow(
            train_start=pd.Timestamp("2026-01-01"),
            train_end=pd.Timestamp("2026-06-30"),
            validation_start=pd.Timestamp("2026-06-30"),
            validation_end=pd.Timestamp("2026-07-30"),
            test_start=pd.Timestamp("2026-07-30"),
            test_end=pd.Timestamp("2026-08-29"),
        ),
        WalkForwardWindow(
            train_start=pd.Timestamp("2026-01-31"),
            train_end=pd.Timestamp("2026-07-30"),
            validation_start=pd.Timestamp("2026-07-30"),
            validation_end=pd.Timestamp("2026-08-29"),
            test_start=pd.Timestamp("2026-08-29"),
            test_end=pd.Timestamp("2026-09-28"),
        ),
    ]


def test_walk_forward_schedule_requires_positive_windows_and_step():
    with pytest.raises(ValueError, match="positive"):
        build_walk_forward_windows(
            start="2026-01-01",
            end="2026-10-01",
            step="0D",
        )
    with pytest.raises(ValueError, match="positive"):
        build_walk_forward_windows(
            start="2026-01-01",
            end="2026-10-01",
            train_window="-180D",
        )


def test_walk_forward_selects_grid_parameters_in_train_and_reuses_them_out_of_sample():
    raw = pd.DataFrame(
        [
            {
                "timestamp": timestamp,
                "symbol": symbol,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 10,
            }
            for timestamp, btc_close, eth_close in [
                ("2026-01-01 00:00:00", 100, 10),
                ("2026-01-01 00:01:00", 110, 9),
                ("2026-01-01 00:02:00", 100, 10),
                ("2026-01-01 00:03:00", 90, 11),
            ]
            for symbol, close in [("BTCUSDT", btc_close), ("ETHUSDT", eth_close)]
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

    result = evaluate_walk_forward(
        factor_evaluation,
        pnl_panel=spot_pnl_panel,
        grid=[
            {
                "action": "spot_long",
                "threshold_quantile": 0.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            },
            {
                "action": "spot_long",
                "threshold_quantile": 0.8,
                "holding_horizon": "1min",
                "leverage": 1.0,
            },
        ],
        windows=[
            WalkForwardWindow(
                train_start=pd.Timestamp("2026-01-01 00:00:00"),
                train_end=pd.Timestamp("2026-01-01 00:01:00"),
                validation_start=pd.Timestamp("2026-01-01 00:01:00"),
                validation_end=pd.Timestamp("2026-01-01 00:02:00"),
                test_start=pd.Timestamp("2026-01-01 00:02:00"),
                test_end=pd.Timestamp("2026-01-01 00:03:00"),
            )
        ],
    )

    window_result = result.windows[0]

    assert window_result.train_result.selected_trial is not None
    assert window_result.train_result.selected_trial.threshold_quantile == 0.8
    assert [trial.threshold_quantile for trial in window_result.validation_result.trials] == [0.8]
    assert [trial.threshold_quantile for trial in window_result.test_result.trials] == [0.8]
    assert result.validation_net_return == pytest.approx(-0.0909090909)
    assert result.test_net_return == pytest.approx(-0.1)


def test_walk_forward_reuses_train_score_threshold_out_of_sample():
    raw = pd.DataFrame(
        [
            {
                "timestamp": timestamp,
                "symbol": symbol,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 10,
            }
            for timestamp, btc_close, eth_close in [
                ("2026-01-01 00:00:00", 100, 10),
                ("2026-01-01 00:01:00", 110, 60),
                ("2026-01-01 00:02:00", 80, 70),
                ("2026-01-01 00:03:00", 90, 80),
            ]
            for symbol, close in [("BTCUSDT", btc_close), ("ETHUSDT", eth_close)]
        ]
    )
    panel_data = build_crypto_panel(raw)
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    spot_pnl_panel = CryptoPanel(data=panel_data, data_role="pnl", data_product="spot")
    scores = pd.Series(
        [100.0, 10.0, 70.0, 60.0, 80.0, 70.0, 90.0, 80.0],
        index=panel_data.index,
    )
    factor_evaluation = evaluate_directional_factor(
        feature_panel,
        lambda data: scores,
        horizon="1min",
    )

    result = evaluate_walk_forward(
        factor_evaluation,
        pnl_panel=spot_pnl_panel,
        grid=[
            {
                "action": "spot_long",
                "threshold_quantile": 1.0,
                "holding_horizon": "1min",
                "leverage": 1.0,
            }
        ],
        windows=[
            WalkForwardWindow(
                train_start=pd.Timestamp("2026-01-01 00:00:00"),
                train_end=pd.Timestamp("2026-01-01 00:01:00"),
                validation_start=pd.Timestamp("2026-01-01 00:01:00"),
                validation_end=pd.Timestamp("2026-01-01 00:02:00"),
                test_start=pd.Timestamp("2026-01-01 00:02:00"),
                test_end=pd.Timestamp("2026-01-01 00:03:00"),
            )
        ],
    )

    window_result = result.windows[0]

    assert window_result.train_result.selected_trial is not None
    assert window_result.train_result.selected_trial.score_threshold == 100.0
    assert window_result.validation_result.trials[0].score_threshold == 100.0
    assert window_result.test_result.trials[0].score_threshold == 100.0
    assert window_result.validation_result.trials[0].trade_count == 0
    assert window_result.test_result.trials[0].trade_count == 0


def test_walk_forward_rejects_windows_that_are_not_time_ordered():
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
    spot_pnl_panel = CryptoPanel(data=panel_data, data_role="pnl", data_product="spot")
    factor_evaluation = evaluate_directional_factor(
        feature_panel,
        lambda data: data["close"],
        horizon="1min",
    )

    with pytest.raises(ValueError, match="time ordered"):
        evaluate_walk_forward(
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
            windows=[
                WalkForwardWindow(
                    train_start=pd.Timestamp("2026-01-01 00:00:00"),
                    train_end=pd.Timestamp("2026-01-01 00:02:00"),
                    validation_start=pd.Timestamp("2026-01-01 00:01:00"),
                    validation_end=pd.Timestamp("2026-01-01 00:03:00"),
                    test_start=pd.Timestamp("2026-01-01 00:03:00"),
                    test_end=pd.Timestamp("2026-01-01 00:04:00"),
                )
            ],
        )


def test_walk_forward_keeps_window_when_train_has_no_selected_trial():
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
                ("2026-01-01 00:01:00", 99),
                ("2026-01-01 00:02:00", 98),
                ("2026-01-01 00:03:00", 97),
            ]
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

    result = evaluate_walk_forward(
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
        windows=[
            WalkForwardWindow(
                train_start=pd.Timestamp("2026-01-01 00:00:00"),
                train_end=pd.Timestamp("2026-01-01 00:01:00"),
                validation_start=pd.Timestamp("2026-01-01 00:01:00"),
                validation_end=pd.Timestamp("2026-01-01 00:02:00"),
                test_start=pd.Timestamp("2026-01-01 00:02:00"),
                test_end=pd.Timestamp("2026-01-01 00:03:00"),
            )
        ],
    )

    assert len(result.windows) == 1
    assert result.windows[0].train_result.selected_trial is None
    assert result.windows[0].validation_result.trials == []
    assert result.windows[0].test_result.trials == []


def test_walk_forward_reuses_forward_returns_across_windows(monkeypatch):
    panel_data = build_crypto_panel(
        pd.DataFrame(
            [
                {
                    "timestamp": timestamp,
                    "symbol": "BTCUSDT",
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 10,
                    "funding_rate": 0.0,
                }
                for timestamp, close in [
                    ("2026-01-01 00:00:00", 100),
                    ("2026-01-01 00:01:00", 101),
                    ("2026-01-01 00:02:00", 102),
                    ("2026-01-01 00:03:00", 103),
                    ("2026-01-01 00:04:00", 104),
                    ("2026-01-01 00:05:00", 105),
                ]
            ]
        )
    )
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    pnl_panel = CryptoPanel(data=panel_data, data_role="pnl", data_product="futures")
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

    evaluate_walk_forward(
        factor_evaluation=factor_evaluation,
        pnl_panel=pnl_panel,
        grid=[
            {
                "action": "perp_long",
                "threshold_quantile": 0.8,
                "holding_horizon": "1min",
                "leverage": 1.0,
            }
        ],
        windows=build_walk_forward_windows(
            start="2026-01-01 00:00:00",
            end="2026-01-01 00:06:00",
            train_window="1min",
            validation_window="1min",
            test_window="1min",
            step="1min",
        ),
    )

    assert call_counts == {"price": 1, "funding": 1}
