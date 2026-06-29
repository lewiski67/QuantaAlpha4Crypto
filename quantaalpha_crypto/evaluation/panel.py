from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd


CryptoPanelRole = Literal["feature", "pnl"]
CryptoPanelProduct = Literal["spot", "futures", "mark"]
OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")
OPTIONAL_COLUMNS = (
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "funding_rate",
    "mark_close",
    "premium_close",
)
OHLCV_AGG = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
}
OPTIONAL_AGG = {
    "quote_volume": "sum",
    "trade_count": "sum",
    "taker_buy_base_volume": "sum",
    "taker_buy_quote_volume": "sum",
    "funding_rate": "sum",
    "mark_close": "last",
    "premium_close": "last",
}


@dataclass(frozen=True)
class CryptoPanel:
    data: pd.DataFrame
    data_role: CryptoPanelRole
    data_product: CryptoPanelProduct | None = None

    def __post_init__(self) -> None:
        if self.data_role not in ("feature", "pnl"):
            raise ValueError("data_role must be 'feature' or 'pnl'")
        if self.data_product is not None and self.data_product not in ("spot", "futures", "mark"):
            raise ValueError("data_product must be 'spot', 'futures', or 'mark'")
        if self.data_role == "pnl" and self.data_product is None:
            raise ValueError("pnl CryptoPanel requires data_product")
        if (
            self.data_role == "pnl"
            and self.data_product in ("futures", "mark")
            and "funding_rate" not in self.data.columns
            and "futures_funding_rate" not in self.data.columns
        ):
            raise ValueError("perpetual PnL Data requires funding_rate or futures_funding_rate")
        if not isinstance(self.data.index, pd.MultiIndex) or self.data.index.names != [
            "timestamp",
            "symbol",
        ]:
            raise ValueError("CryptoPanel data must be indexed by timestamp and symbol")


def build_crypto_panel(raw: pd.DataFrame, freq: str | None = None) -> pd.DataFrame:
    """Build a timestamp-by-symbol Crypto Panel from completed OHLCV bars."""
    panel = raw.copy()
    panel["timestamp"] = pd.to_datetime(panel["timestamp"])
    panel["symbol"] = panel["symbol"].astype(str)

    for column in OHLCV_COLUMNS:
        panel[column] = pd.to_numeric(panel[column], errors="raise").astype("float64")
    optional_columns = [column for column in OPTIONAL_COLUMNS if column in panel.columns]
    for column in optional_columns:
        panel[column] = pd.to_numeric(panel[column], errors="raise").astype("float64")

    if freq is not None:
        panel = _resample_ohlcv(panel, freq, optional_columns)

    return (
        panel.set_index(["timestamp", "symbol"])
        .sort_index()
        .loc[:, [*OHLCV_COLUMNS, *optional_columns]]
    )


def _resample_ohlcv(
    panel: pd.DataFrame,
    freq: str,
    optional_columns: list[str],
) -> pd.DataFrame:
    agg = {**OHLCV_AGG, **{column: OPTIONAL_AGG[column] for column in optional_columns}}
    pieces = []
    for symbol, symbol_panel in panel.sort_values("timestamp").groupby("symbol", sort=False):
        resampled = (
            symbol_panel.set_index("timestamp")
            .resample(freq, closed="right", label="right")
            .agg(agg)
            .dropna(subset=["open", "high", "low", "close"])
            .reset_index()
        )
        resampled["symbol"] = symbol
        pieces.append(resampled)

    if not pieces:
        return panel.iloc[0:0].loc[:, ["timestamp", "symbol", *OHLCV_COLUMNS, *optional_columns]]

    return pd.concat(pieces, ignore_index=True)
