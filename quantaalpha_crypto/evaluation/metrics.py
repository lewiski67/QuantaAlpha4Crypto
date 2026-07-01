"""Shared metric primitives for crypto factor evaluation.

These were previously duplicated or scattered across ``grid.py``,
``portfolio.py``, and ``factor.py``. Centralizing them gives the evaluation
core a single source of truth for Sharpe, forward returns, Rank IC, drawdown,
and annualization, and keeps the larger modules focused on orchestration.

Depends only on pandas so it can be imported by any evaluation module without
creating an import cycle.
"""

from __future__ import annotations

import numpy as np
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
    execution_lag_bars: int = 1,
) -> pd.Series:
    pieces = []
    for symbol, symbol_data in data.sort_index().groupby(level="symbol", sort=False):
        close = symbol_data[price_column].astype("float64")
        timestamps = close.index.get_level_values("timestamp")

        # Entry: positional shift so irregular gaps don't produce phantom bars.
        # Rebuild via DatetimeIndex (not ``.values``, which would drop the tz and
        # break reindex alignment against a tz-aware panel).
        entry_timestamps = pd.DatetimeIndex(
            pd.Series(timestamps).shift(-execution_lag_bars)
        )
        entry_index = pd.MultiIndex.from_arrays(
            [entry_timestamps, [symbol] * len(timestamps)],
            names=["timestamp", "symbol"],
        )
        entry_close = close.reindex(entry_index)
        entry_close.index = close.index

        # Exit: time-based from entry so horizon means real elapsed time.
        exit_index = pd.MultiIndex.from_arrays(
            [entry_timestamps + horizon, [symbol] * len(timestamps)],
            names=["timestamp", "symbol"],
        )
        exit_close = close.reindex(exit_index)
        exit_close.index = close.index

        pieces.append(exit_close / entry_close - 1.0)

    if not pieces:
        return pd.Series(dtype="float64", name=name)

    return pd.concat(pieces).sort_index()


def _rank_ic(scores: pd.Series, returns: pd.Series) -> float:
    if len(scores) < 2:
        return float("nan")
    if scores.nunique(dropna=True) < 2 or returns.nunique(dropna=True) < 2:
        return float("nan")
    return float(scores.rank().corr(returns.rank()))


def _nw_tstat(series: pd.Series, lag: int) -> float:
    """Newey-West (HAC) t-statistic for the mean of a per-bar series.

    ``series`` is a per-bar contribution stream (e.g. the demeaned-score times
    demeaned-return products underlying an IC). Overlapping forward returns make
    adjacent terms autocorrelated, so the naive ``std/sqrt(T)`` standard error
    understates uncertainty and inflates significance. This corrects it with a
    Bartlett-kernel long-run variance out to ``lag`` (0 recovers the naive
    t-stat). The point estimate ``mean(series)`` is left untouched.

    Returns NaN for degenerate inputs (empty, ``T <= lag``, zero variance, or a
    numerically non-positive long-run variance).
    """
    if lag < 0:
        raise ValueError("lag must be non-negative")

    values = np.asarray(series, dtype="float64")
    n = values.size
    if n == 0 or n <= lag:
        return float("nan")

    mean = values.mean()
    demeaned = values - mean

    gamma_0 = float((demeaned * demeaned).sum() / n)
    if gamma_0 <= 0.0:
        return float("nan")

    long_run_var = gamma_0
    for k in range(1, lag + 1):
        weight = 1.0 - k / (lag + 1)
        gamma_k = float((demeaned[k:] * demeaned[:-k]).sum() / n)
        long_run_var += 2.0 * weight * gamma_k

    if long_run_var <= 0.0:
        return float("nan")

    std_error = (long_run_var / n) ** 0.5
    return float(mean / std_error)


def _bars_per_horizon(index: pd.MultiIndex, horizon: pd.Timedelta) -> int:
    """Convert a real-time ``horizon`` into a bar count for the NW ``lag``.

    ``_nw_tstat`` needs its lag in *bars* (sample-index steps), but a Forward
    Return horizon is real elapsed time. The bar interval is inferred from the
    panel cadence: per-symbol timestamp diffs (the mode), which is robust to
    isolated missing bars. Returns ``round(horizon / bar_interval)``.

    Per-symbol (not the flattened index) because different symbols interleave in
    time; a flattened diff would not reflect the true bar spacing. All symbols in
    a single panel must share one cadence -- a mismatch raises (a multi-frequency
    panel breaks the data contract; silently taking a global mode would hide it).

    Symbols with fewer than two timestamps carry no interval and are skipped;
    if none yield an interval, raises. NOTE (0.3 skeleton): cadence is read from
    the *panel* grid, which equals the evaluated-sample cadence only for clean,
    non-forward-filled factors. Survival-based cadence for coarse/filled factors
    is deferred to iteration 1.
    """
    if horizon <= pd.Timedelta(0):
        raise ValueError("horizon must be positive")

    frame = index.to_frame(index=False)
    intervals: set[pd.Timedelta] = set()
    for _symbol, group in frame.groupby("symbol", sort=False):
        timestamps = pd.to_datetime(group["timestamp"]).sort_values()
        diffs = timestamps.diff().dropna()
        if diffs.empty:
            continue
        intervals.add(diffs.mode().iloc[0])

    if not intervals:
        raise ValueError("cannot infer bar interval: need >= 2 timestamps per symbol")
    if len(intervals) > 1:
        raise ValueError(f"inconsistent bar intervals across symbols: {sorted(intervals)}")

    (bar_interval,) = intervals
    if bar_interval <= pd.Timedelta(0):
        raise ValueError("bar interval must be positive")

    return int(round(horizon / bar_interval))


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
