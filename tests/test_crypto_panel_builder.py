import pandas as pd
import pytest

from quantaalpha_crypto import CryptoPanel, build_crypto_panel


def test_build_crypto_panel_indexes_rows_by_timestamp_and_symbol():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "ETHUSDT",
                "open": "20",
                "high": "22",
                "low": "19",
                "close": "21",
                "volume": "200",
            },
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": "10",
                "high": "12",
                "low": "9",
                "close": "11",
                "volume": "100",
            },
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "ETHUSDT",
                "open": "30",
                "high": "32",
                "low": "29",
                "close": "31",
                "volume": "300",
            },
        ]
    )

    panel = build_crypto_panel(raw)

    assert panel.index.names == ["timestamp", "symbol"]
    assert panel.index.tolist() == [
        (pd.Timestamp("2026-01-01 00:00:00"), "BTCUSDT"),
        (pd.Timestamp("2026-01-01 00:00:00"), "ETHUSDT"),
        (pd.Timestamp("2026-01-01 00:01:00"), "ETHUSDT"),
    ]
    assert panel.loc[(pd.Timestamp("2026-01-01 00:00:00"), "BTCUSDT"), "close"] == 11.0


def test_build_crypto_panel_resamples_at_bar_end_without_future_rows():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 10,
                "high": 12,
                "low": 9,
                "close": 11,
                "volume": 100,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "BTCUSDT",
                "open": 20,
                "high": 24,
                "low": 19,
                "close": 23,
                "volume": 200,
            },
            {
                "timestamp": "2026-01-01 00:02:00",
                "symbol": "BTCUSDT",
                "open": 30,
                "high": 35,
                "low": 29,
                "close": 34,
                "volume": 300,
            },
        ]
    )

    panel = build_crypto_panel(raw, freq="2min")

    assert panel.index.tolist() == [
        (pd.Timestamp("2026-01-01 00:00:00"), "BTCUSDT"),
        (pd.Timestamp("2026-01-01 00:02:00"), "BTCUSDT"),
    ]
    assert panel.loc[(pd.Timestamp("2026-01-01 00:00:00"), "BTCUSDT")].to_dict() == {
        "open": 10.0,
        "high": 12.0,
        "low": 9.0,
        "close": 11.0,
        "volume": 100.0,
    }
    assert panel.loc[(pd.Timestamp("2026-01-01 00:02:00"), "BTCUSDT")].to_dict() == {
        "open": 20.0,
        "high": 35.0,
        "low": 19.0,
        "close": 34.0,
        "volume": 500.0,
    }


def test_build_crypto_panel_normalizes_ohlcv_field_types():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": "10",
                "high": "12.5",
                "low": "9",
                "close": "11.25",
                "volume": "100",
            }
        ]
    )

    panel = build_crypto_panel(raw)

    assert panel.dtypes.to_dict() == {
        "open": "float64",
        "high": "float64",
        "low": "float64",
        "close": "float64",
        "volume": "float64",
    }


def test_crypto_panel_wrapper_distinguishes_feature_data_from_pnl_data():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 10,
                "high": 12,
                "low": 9,
                "close": 11,
                "volume": 100,
            }
        ]
    )
    data = build_crypto_panel(raw)

    feature_panel = CryptoPanel(data=data, data_role="feature")
    pnl_panel = CryptoPanel(data=data, data_role="pnl", data_product="spot")

    assert feature_panel.data_role == "feature"
    assert pnl_panel.data_role == "pnl"
    assert pnl_panel.data_product == "spot"
    pd.testing.assert_frame_equal(feature_panel.data, pnl_panel.data)


def test_crypto_panel_wrapper_rejects_unknown_data_role():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 10,
                "high": 12,
                "low": 9,
                "close": 11,
                "volume": 100,
            }
        ]
    )

    with pytest.raises(ValueError, match="data_role"):
        CryptoPanel(data=build_crypto_panel(raw), data_role="execution")


def test_crypto_panel_wrapper_requires_timestamp_symbol_index():
    not_a_crypto_panel = pd.DataFrame({"close": [11.0]})

    with pytest.raises(ValueError, match="timestamp.*symbol"):
        CryptoPanel(data=not_a_crypto_panel, data_role="feature")


def test_crypto_panel_wrapper_requires_product_for_pnl_data():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 10,
                "high": 12,
                "low": 9,
                "close": 11,
                "volume": 100,
            }
        ]
    )

    with pytest.raises(ValueError, match="data_product"):
        CryptoPanel(data=build_crypto_panel(raw), data_role="pnl")


def test_crypto_panel_wrapper_requires_funding_for_perpetual_pnl_data():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 10,
                "high": 12,
                "low": 9,
                "close": 11,
                "volume": 100,
            }
        ]
    )

    with pytest.raises(ValueError, match="funding_rate"):
        CryptoPanel(data=build_crypto_panel(raw), data_role="pnl", data_product="futures")


def test_build_crypto_panel_preserves_funding_rate_for_perpetual_pnl_data():
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 10,
                "high": 12,
                "low": 9,
                "close": 11,
                "volume": 100,
                "funding_rate": "0.001",
            }
        ]
    )

    panel = build_crypto_panel(raw)
    pnl_panel = CryptoPanel(data=panel, data_role="pnl", data_product="futures")

    assert panel.loc[(pd.Timestamp("2026-01-01 00:00:00"), "BTCUSDT"), "funding_rate"] == 0.001
    assert pnl_panel.data_product == "futures"
