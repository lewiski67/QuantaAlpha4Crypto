import pandas as pd
import pytest

from quantaalpha_crypto import CryptoPanel, build_crypto_panel, evaluate_directional_factor
from quantaalpha_crypto.evaluation.factor import _scores_close_enough


def test_evaluate_directional_factor_aligns_scores_with_forward_returns():
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
                "open": 102,
                "high": 103,
                "low": 101,
                "close": 102,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "ETHUSDT",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "ETHUSDT",
                "open": 99,
                "high": 100,
                "low": 98,
                "close": 99,
                "volume": 10,
            },
        ]
    )
    panel = CryptoPanel(data=build_crypto_panel(raw), data_role="feature")

    def close_score(data):
        return data["close"]

    result = evaluate_directional_factor(panel, close_score, horizon="1min")

    assert result.scores.index.tolist() == [
        (pd.Timestamp("2026-01-01 00:00:00"), "BTCUSDT"),
        (pd.Timestamp("2026-01-01 00:00:00"), "ETHUSDT"),
    ]
    assert result.scores.tolist() == [100.0, 100.0]
    assert result.forward_returns.tolist() == pytest.approx([0.02, -0.01])


def test_evaluate_directional_factor_reports_basic_ic_evidence():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 110,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "BTCUSDT",
                "open": 121,
                "high": 122,
                "low": 120,
                "close": 121,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "ETHUSDT",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 90,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "ETHUSDT",
                "open": 81,
                "high": 82,
                "low": 80,
                "close": 81,
                "volume": 10,
            },
        ]
    )
    panel = CryptoPanel(data=build_crypto_panel(raw), data_role="feature")

    result = evaluate_directional_factor(panel, lambda data: data["close"], horizon="1min")

    assert result.ic == pytest.approx(1.0)
    assert result.rank_ic == pytest.approx(1.0)


def test_evaluate_directional_factor_requires_feature_data():
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
    pnl_panel = CryptoPanel(
        data=build_crypto_panel(raw),
        data_role="pnl",
        data_product="spot",
    )

    with pytest.raises(ValueError, match="Feature Data"):
        evaluate_directional_factor(pnl_panel, lambda data: data["close"], horizon="1min")


def test_evaluate_directional_factor_rejects_future_dependent_scores():
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
    panel = CryptoPanel(data=build_crypto_panel(raw), data_role="feature")

    def future_close(data):
        return data.groupby(level="symbol")["close"].shift(-1)

    with pytest.raises(ValueError, match="future-looking|lookback"):
        evaluate_directional_factor(
            panel,
            future_close,
            horizon="1min",
            input_lookback_window="2min",
        )


def test_evaluate_directional_factor_accepts_trailing_window_scores():
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
    panel = CryptoPanel(data=build_crypto_panel(raw), data_role="feature")

    def trailing_mean(data):
        return (
            data["close"]
            .groupby(level="symbol")
            .rolling(window=2, min_periods=1)
            .mean()
            .droplevel(0)
        )

    result = evaluate_directional_factor(
        panel,
        trailing_mean,
        horizon="1min",
        input_lookback_window="2min",
    )

    assert result.scores.tolist() == pytest.approx([100.0, 100.5, 101.5])


def test_factor_input_audit_tolerates_floating_point_roundoff_only():
    index = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2026-01-01 00:00:00"), "BTCUSDT"),
            (pd.Timestamp("2026-01-01 00:00:00"), "SOLUSDT"),
        ],
        names=["timestamp", "symbol"],
    )
    expected = pd.Series([1.0, -2.0], index=index)
    near = pd.Series([1.0 + 1e-13, -2.0 - 1e-13], index=index)
    far = pd.Series([1.0 + 1e-5, -2.0], index=index)

    assert _scores_close_enough(near, expected) is True
    assert _scores_close_enough(far, expected) is False
