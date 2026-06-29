import json

import pandas as pd

from quantaalpha_crypto import BinanceLocalDataConfig, load_binance_crypto_panel_data


def test_binance_local_data_adapter_loads_filtered_spot_csv_into_crypto_panels(tmp_path):
    csv_path = tmp_path / "spot_1m.csv"
    pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100.5,
                "volume": 10,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "BTCUSDT",
                "open": 100.5,
                "high": 102,
                "low": 100,
                "close": 101.5,
                "volume": 12,
            },
            {
                "timestamp": "2026-01-01 00:01:00",
                "symbol": "ETHUSDT",
                "open": 20,
                "high": 21,
                "low": 19,
                "close": 20.5,
                "volume": 7,
            },
        ]
    ).to_csv(csv_path, index=False)

    result = load_binance_crypto_panel_data(
        BinanceLocalDataConfig(
            data_path=csv_path,
            symbols=["BTCUSDT"],
            frequency="1min",
            start_time="2026-01-01 00:00:00",
            end_time="2026-01-01 00:01:00",
            product_type="spot",
            dependency_name="binance_spot_1m_ohlcv",
        )
    )

    assert result.feature_panel.data_role == "feature"
    assert result.pnl_panel.data_role == "pnl"
    assert result.pnl_panel.data_product == "spot"
    assert result.feature_panel.data.index.names == ["timestamp", "symbol"]
    assert result.feature_panel.data.index.get_level_values("symbol").unique().tolist() == ["BTCUSDT"]
    assert result.feature_panel.data.index.get_level_values("timestamp").tolist() == [
        pd.Timestamp("2026-01-01 00:00:00"),
        pd.Timestamp("2026-01-01 00:01:00"),
    ]
    assert result.pnl_panel.data.equals(result.feature_panel.data)
    assert result.feature_data_dependencies == ["binance_spot_1m_ohlcv"]
    assert result.pnl_data_dependencies == ["binance_spot_1m_ohlcv"]
    assert result.metadata["source_path"] == str(csv_path)
    assert result.metadata["symbols"] == ["BTCUSDT"]
    assert result.metadata["frequency"] == "1min"
    assert result.metadata["product_type"] == "spot"


def test_binance_local_data_adapter_can_load_multiple_csv_references(tmp_path):
    btc_path = tmp_path / "btc.csv"
    eth_path = tmp_path / "eth.csv"
    pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "BTCUSDT",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100.5,
                "volume": 10,
            }
        ]
    ).to_csv(btc_path, index=False)
    pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01 00:00:00",
                "symbol": "ETHUSDT",
                "open": 20,
                "high": 21,
                "low": 19,
                "close": 20.5,
                "volume": 7,
            }
        ]
    ).to_csv(eth_path, index=False)

    result = load_binance_crypto_panel_data(
        BinanceLocalDataConfig(
            data_path=[btc_path, eth_path],
            symbols=["BTCUSDT", "ETHUSDT"],
            frequency="1min",
            product_type="spot",
            dependency_name="binance_spot_multi_symbol_1m_ohlcv",
        )
    )

    assert result.feature_panel.data.index.get_level_values("symbol").unique().tolist() == [
        "BTCUSDT",
        "ETHUSDT",
    ]
    assert result.metadata["source_path"] == [str(btc_path), str(eth_path)]


def test_binance_local_data_adapter_loads_spot_candle_jsonl_root(tmp_path):
    candle_dir = tmp_path / "candles" / "BTCUSDT"
    candle_dir.mkdir(parents=True)
    candle_path = candle_dir / "1m.jsonl"
    _write_jsonl(
        candle_path,
        [
            {
                "open_time": "2026-01-01T00:00:00+00:00",
                "symbol": "BTCUSDT",
                "open": "100",
                "high": "101",
                "low": "99",
                "close": "100.5",
                "volume": "10",
                "quote_volume": "1005",
                "trade_count": 3,
                "taker_buy_base_volume": "4",
                "taker_buy_quote_volume": "402",
            },
            {
                "open_time": "2026-01-01T00:01:00+00:00",
                "symbol": "BTCUSDT",
                "open": "100.5",
                "high": "102",
                "low": "100",
                "close": "101.5",
                "volume": "12",
                "quote_volume": "1218",
                "trade_count": 5,
                "taker_buy_base_volume": "6",
                "taker_buy_quote_volume": "609",
            },
        ],
    )

    result = load_binance_crypto_panel_data(
        BinanceLocalDataConfig(
            data_path=tmp_path,
            symbols=["BTCUSDT"],
            frequency="1m",
            source_format="binance_spot_candles_jsonl",
            start_time="2026-01-01 00:00:00",
            end_time="2026-01-01 00:01:00",
            product_type="spot",
            dependency_name="binance_spot_jsonl_1m",
        )
    )

    panel = result.feature_panel.data
    assert panel.index.names == ["timestamp", "symbol"]
    assert panel.index.get_level_values("symbol").unique().tolist() == ["BTCUSDT"]
    assert panel["spot_close"].tolist() == [100.5, 101.5]
    assert panel["spot_quote_volume"].tolist() == [1005.0, 1218.0]
    assert panel["spot_trade_count"].tolist() == [3.0, 5.0]
    assert result.metadata["source_format"] == "binance_spot_candles_jsonl"


def test_binance_local_data_adapter_loads_futures_jsonl_with_mark_premium_and_funding(tmp_path):
    symbol_dir = tmp_path / "external" / "binance" / "futures" / "BTCUSDT"
    symbol_dir.mkdir(parents=True)
    _write_jsonl(
        symbol_dir / "um_klines_1m.jsonl",
        [
            [1767225600000, "100", "101", "99", "100.5", "10", 1767225659999, "1005", 3, "4", "402", "0"],
            [1767225660000, "100.5", "102", "100", "101.5", "12", 1767225719999, "1218", 5, "6", "609", "0"],
        ],
    )
    _write_jsonl(
        symbol_dir / "mark_price_klines_1m.jsonl",
        [
            [1767225600000, "100", "101", "99", "100.4", "0", 1767225659999, "0", 0, "0", "0", "0"],
            [1767225660000, "100.5", "102", "100", "101.4", "0", 1767225719999, "0", 0, "0", "0", "0"],
        ],
    )
    _write_jsonl(
        symbol_dir / "premium_index_klines_1m.jsonl",
        [
            [1767225600000, "0", "0", "0", "0.0001", "0", 1767225659999, "0", 0, "0", "0", "0"],
            [1767225660000, "0", "0", "0", "0.0002", "0", 1767225719999, "0", 0, "0", "0", "0"],
        ],
    )
    _write_jsonl(
        symbol_dir / "funding_rate.jsonl",
        [
            {"fundingRate": "0.0003", "fundingTime": 1767225600000, "markPrice": "100.4", "symbol": "BTCUSDT"}
        ],
    )

    result = load_binance_crypto_panel_data(
        BinanceLocalDataConfig(
            data_path=tmp_path,
            symbols=["BTCUSDT"],
            frequency="1m",
            source_format="binance_futures_jsonl",
            product_type="futures",
            dependency_name="binance_futures_jsonl_1m",
        )
    )

    panel = result.feature_panel.data
    assert result.pnl_panel.data_product == "futures"
    assert panel["futures_close"].tolist() == [100.5, 101.5]
    assert panel["futures_mark_close"].tolist() == [100.4, 101.4]
    assert panel["futures_premium_close"].tolist() == [0.0001, 0.0002]
    assert panel["futures_funding_rate"].tolist() == [0.0003, 0.0]
    assert result.metadata["source_format"] == "binance_futures_jsonl"


def _write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row))
            file.write("\n")
