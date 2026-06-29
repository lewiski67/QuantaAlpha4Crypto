from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from quantaalpha_crypto.evaluation.panel import CryptoPanel, build_crypto_panel

JSONL_READ_CHUNKSIZE = 250_000

BinanceLocalDataSourceFormat = Literal[
    "csv",
    "binance_spot_candles_jsonl",
    "binance_futures_jsonl",
]


@dataclass(frozen=True)
class BinanceLocalDataConfig:
    data_path: str | Path | list[str | Path]
    symbols: list[str]
    frequency: str
    start_time: str | pd.Timestamp | None = None
    end_time: str | pd.Timestamp | None = None
    product_type: Literal["spot", "futures", "mark"] = "spot"
    dependency_name: str = "binance_local_ohlcv"
    source_format: BinanceLocalDataSourceFormat = "csv"


@dataclass(frozen=True)
class BinanceCryptoPanelData:
    feature_panel: CryptoPanel
    pnl_panel: CryptoPanel
    feature_data_dependencies: list[str]
    pnl_data_dependencies: list[str]
    metadata: dict


def load_binance_crypto_panel_data(config: BinanceLocalDataConfig) -> BinanceCryptoPanelData:
    """Load local Binance OHLCV files into Feature Data and PnL Data CryptoPanels."""
    data_paths = config.data_path if isinstance(config.data_path, list) else [config.data_path]
    raw = _load_raw_binance_data(config)
    raw["timestamp"] = pd.to_datetime(raw["timestamp"])
    raw["symbol"] = raw["symbol"].astype(str)

    selected = raw[raw["symbol"].isin(config.symbols)]
    if config.start_time is not None:
        selected = selected[selected["timestamp"] >= _coerce_boundary(config.start_time, selected["timestamp"])]
    if config.end_time is not None:
        selected = selected[selected["timestamp"] <= _coerce_boundary(config.end_time, selected["timestamp"])]

    panel_data = _prefix_product_columns(
        build_crypto_panel(selected, freq=_to_pandas_frequency(config.frequency)),
        config.product_type,
    )
    return BinanceCryptoPanelData(
        feature_panel=CryptoPanel(data=panel_data, data_role="feature"),
        pnl_panel=CryptoPanel(data=panel_data, data_role="pnl", data_product=config.product_type),
        feature_data_dependencies=[config.dependency_name],
        pnl_data_dependencies=[config.dependency_name],
        metadata={
            "source_path": (
                [str(path) for path in data_paths]
                if isinstance(config.data_path, list)
                else str(config.data_path)
            ),
            "symbols": list(config.symbols),
            "frequency": config.frequency,
            "start_time": str(config.start_time) if config.start_time is not None else None,
            "end_time": str(config.end_time) if config.end_time is not None else None,
            "product_type": config.product_type,
            "dependency_name": config.dependency_name,
            "source_format": config.source_format,
        },
    )


def _load_raw_binance_data(config: BinanceLocalDataConfig) -> pd.DataFrame:
    data_paths = config.data_path if isinstance(config.data_path, list) else [config.data_path]
    paths = [Path(path) for path in data_paths]

    if config.source_format == "csv":
        return pd.concat([pd.read_csv(path) for path in paths], ignore_index=True)
    if config.source_format == "binance_spot_candles_jsonl":
        return pd.concat(
            [
                _load_spot_candle_jsonl(
                    _resolve_spot_candle_path(path, symbol, config.frequency),
                    config.start_time,
                    config.end_time,
                )
                for path in paths
                for symbol in config.symbols
            ],
            ignore_index=True,
        )
    if config.source_format == "binance_futures_jsonl":
        return pd.concat(
            [
                _load_futures_symbol_jsonl(path, symbol, config.frequency, config.start_time, config.end_time)
                for path in paths
                for symbol in config.symbols
            ],
            ignore_index=True,
        )
    raise ValueError(f"unsupported Binance data source_format: {config.source_format}")


def _prefix_product_columns(panel: pd.DataFrame, product_type: str) -> pd.DataFrame:
    prefix = "futures" if product_type in ("futures", "mark") else "spot"
    return panel.rename(columns={column: f"{prefix}_{column}" for column in panel.columns})


def _coerce_boundary(value: str | pd.Timestamp, timestamps: pd.Series) -> pd.Timestamp:
    boundary = pd.Timestamp(value)
    if isinstance(timestamps.dtype, pd.DatetimeTZDtype) and boundary.tzinfo is None:
        return boundary.tz_localize(timestamps.dt.tz)
    if not isinstance(timestamps.dtype, pd.DatetimeTZDtype) and boundary.tzinfo is not None:
        return boundary.tz_convert(None)
    return boundary


def _to_pandas_frequency(frequency: str) -> str:
    if frequency.endswith("m") and frequency[:-1].isdigit():
        return f"{frequency[:-1]}min"
    return frequency


def _resolve_spot_candle_path(root_or_file: Path, symbol: str, frequency: str) -> Path:
    if root_or_file.is_file():
        return root_or_file
    return root_or_file / "candles" / symbol / f"{frequency}.jsonl"


def _resolve_futures_symbol_root(root_or_symbol_root: Path, symbol: str) -> Path:
    if root_or_symbol_root.name == symbol:
        return root_or_symbol_root
    return root_or_symbol_root / "external" / "binance" / "futures" / symbol


def _load_spot_candle_jsonl(
    path: Path,
    start_time: str | pd.Timestamp | None,
    end_time: str | pd.Timestamp | None,
) -> pd.DataFrame:
    start = _jsonl_boundary(start_time)
    end = _jsonl_boundary(end_time)
    pieces = []
    for chunk in pd.read_json(path, lines=True, chunksize=JSONL_READ_CHUNKSIZE):
        chunk = chunk.copy()
        chunk["timestamp"] = pd.to_datetime(chunk["open_time"], utc=True)
        filtered = _filter_timestamp_frame(chunk, start, end)
        if not filtered.empty:
            for column in (
                "quote_volume",
                "trade_count",
                "taker_buy_base_volume",
                "taker_buy_quote_volume",
            ):
                if column not in filtered:
                    filtered[column] = None
            pieces.append(
                filtered.loc[
                    :,
                    [
                        "timestamp",
                        "symbol",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "quote_volume",
                        "trade_count",
                        "taker_buy_base_volume",
                        "taker_buy_quote_volume",
                    ],
                ]
            )
        if end is not None and chunk["timestamp"].max() > end:
            break
    if not pieces:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "symbol",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trade_count",
                "taker_buy_base_volume",
                "taker_buy_quote_volume",
            ]
        )
    return pd.concat(pieces, ignore_index=True)


def _load_futures_symbol_jsonl(
    root_or_symbol_root: Path,
    symbol: str,
    frequency: str,
    start_time: str | pd.Timestamp | None,
    end_time: str | pd.Timestamp | None,
) -> pd.DataFrame:
    symbol_root = _resolve_futures_symbol_root(root_or_symbol_root, symbol)
    raw = _load_kline_array_jsonl(
        symbol_root / f"um_klines_{frequency}.jsonl",
        symbol,
        start_time,
        end_time,
    )
    mark_path = symbol_root / f"mark_price_klines_{frequency}.jsonl"
    if mark_path.exists():
        raw = raw.merge(
            _load_kline_array_jsonl(mark_path, symbol, start_time, end_time)
            .loc[:, ["timestamp", "symbol", "close"]]
            .rename(columns={"close": "mark_close"}),
            on=["timestamp", "symbol"],
            how="left",
        )
    premium_path = symbol_root / f"premium_index_klines_{frequency}.jsonl"
    if premium_path.exists():
        raw = raw.merge(
            _load_kline_array_jsonl(premium_path, symbol, start_time, end_time)
            .loc[:, ["timestamp", "symbol", "close"]]
            .rename(columns={"close": "premium_close"}),
            on=["timestamp", "symbol"],
            how="left",
        )
    funding_path = symbol_root / "funding_rate.jsonl"
    if funding_path.exists():
        raw = raw.merge(
            _load_funding_rate_jsonl(funding_path, start_time, end_time),
            on=["timestamp", "symbol"],
            how="left",
        )
    raw["funding_rate"] = raw.get("funding_rate", 0.0)
    raw["funding_rate"] = raw["funding_rate"].fillna(0.0)
    return raw


def _load_kline_array_jsonl(
    path: Path,
    symbol: str,
    start_time: str | pd.Timestamp | None,
    end_time: str | pd.Timestamp | None,
) -> pd.DataFrame:
    start = _jsonl_boundary(start_time)
    end = _jsonl_boundary(end_time)
    pieces = []
    for chunk in pd.read_json(path, lines=True, chunksize=JSONL_READ_CHUNKSIZE):
        chunk = chunk.copy()
        chunk["timestamp"] = pd.to_datetime(chunk[0], unit="ms", utc=True)
        filtered = _filter_timestamp_frame(chunk, start, end)
        if not filtered.empty:
            pieces.append(
                pd.DataFrame(
                    {
                        "timestamp": filtered["timestamp"],
                        "symbol": symbol,
                        "open": filtered[1],
                        "high": filtered[2],
                        "low": filtered[3],
                        "close": filtered[4],
                        "volume": filtered[5],
                        "quote_volume": filtered[7],
                        "trade_count": filtered[8],
                        "taker_buy_base_volume": filtered[9],
                        "taker_buy_quote_volume": filtered[10],
                    }
                )
            )
        if end is not None and chunk["timestamp"].max() > end:
            break
    if not pieces:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "symbol",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trade_count",
                "taker_buy_base_volume",
                "taker_buy_quote_volume",
            ]
        )
    return pd.concat(pieces, ignore_index=True)


def _load_funding_rate_jsonl(
    path: Path,
    start_time: str | pd.Timestamp | None,
    end_time: str | pd.Timestamp | None,
) -> pd.DataFrame:
    start = _jsonl_boundary(start_time)
    end = _jsonl_boundary(end_time)
    pieces = []
    for chunk in pd.read_json(path, lines=True, chunksize=JSONL_READ_CHUNKSIZE):
        chunk = chunk.copy()
        chunk["timestamp"] = pd.to_datetime(chunk["fundingTime"], unit="ms", utc=True)
        filtered = _filter_timestamp_frame(chunk, start, end)
        if not filtered.empty:
            pieces.append(
                filtered.loc[:, ["timestamp", "symbol", "fundingRate"]].rename(
                    columns={"fundingRate": "funding_rate"}
                )
            )
        if end is not None and chunk["timestamp"].max() > end:
            break
    if not pieces:
        return pd.DataFrame(columns=["timestamp", "symbol", "funding_rate"])
    return pd.concat(pieces, ignore_index=True)


def _filter_timestamp_frame(
    frame: pd.DataFrame,
    start_time: pd.Timestamp | None,
    end_time: pd.Timestamp | None,
) -> pd.DataFrame:
    mask = pd.Series(True, index=frame.index)
    if start_time is not None:
        mask &= frame["timestamp"] >= start_time
    if end_time is not None:
        mask &= frame["timestamp"] <= end_time
    return frame.loc[mask]


def _jsonl_boundary(value: str | pd.Timestamp | None) -> pd.Timestamp | None:
    if value is None:
        return None
    boundary = pd.Timestamp(value)
    if boundary.tzinfo is None:
        return boundary.tz_localize("UTC")
    return boundary.tz_convert("UTC")
