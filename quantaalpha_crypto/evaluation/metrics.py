"""Shared metric primitives for crypto factor evaluation.

These were previously duplicated or scattered across ``grid.py``,
``portfolio.py``, and ``factor.py``. Centralizing them gives the evaluation
core a single source of truth for Sharpe, forward returns, Rank IC, drawdown,
and annualization, and keeps the larger modules focused on orchestration.

Depends only on pandas so it can be imported by any evaluation module without
creating an import cycle.
"""

from __future__ import annotations

import pandas as pd


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


def _forward_returns(
    data: pd.DataFrame,
    horizon: pd.Timedelta,
    price_column: str = "close",
    name: str = "forward_return",
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
        return pd.Series(dtype="float64", name=name)

    return pd.concat(pieces).sort_index()


def _rank_ic(scores: pd.Series, returns: pd.Series) -> float:
    if len(scores) < 2:
        return float("nan")
    if scores.nunique(dropna=True) < 2 or returns.nunique(dropna=True) < 2:
        return float("nan")
    return float(scores.rank().corr(returns.rank()))


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


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
