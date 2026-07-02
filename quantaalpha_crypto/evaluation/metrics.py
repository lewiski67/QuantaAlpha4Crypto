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


# Denominator floor for volatility normalization: guards exact zero volatility
# (degenerate/synthetic data) against division blowups. Deliberately a machine
# epsilon, never a substantive lower bound -- flooring real quiet-period sigma
# would rewrite labels (decision 2026-07-02, see HANDOFF).
_VOLATILITY_FLOOR = 1e-12


def _trailing_volatility(
    data: pd.DataFrame,
    window: pd.Timedelta,
    price_column: str = "close",
) -> pd.Series:
    """Per-symbol trailing volatility of per-bar returns, by timestamp window.

    Simple rolling std (pandas ddof=1) of simple per-bar returns on the panel's
    native cadence. The window is time-based -- ``(t - window, t]`` by
    timestamp -- so irregular gaps cannot smuggle stale bars in by count.
    Full-window warmup: bars with less than ``window`` of history since the
    symbol's first bar are NaN.
    """
    pieces = []
    for _symbol, symbol_data in data.sort_index().groupby(level="symbol", sort=False):
        close = symbol_data[price_column].astype("float64")
        timestamps = close.index.get_level_values("timestamp")
        per_bar = pd.Series(close.to_numpy(), index=timestamps)
        volatility = per_bar.pct_change().rolling(window).std()
        elapsed = timestamps - timestamps[0]
        volatility[np.asarray(elapsed < window)] = np.nan
        pieces.append(pd.Series(volatility.to_numpy(), index=close.index))
    if not pieces:
        return pd.Series(dtype="float64")
    return pd.concat(pieces).sort_index()


def _vol_norm_returns(
    data: pd.DataFrame,
    horizon: pd.Timedelta,
    price_column: str = "close",
    vol_window: str | pd.Timedelta = "7D",
    name: str = "vol_norm_return",
    execution_lag_bars: int = 1,
) -> pd.Series:
    """Volatility-normalized Forward Returns -- the V1 label (ADR-0014).

    ``_forward_returns`` divided by a per-symbol trailing volatility scaled to
    the horizon: ``sigma_h = sigma_bar * sqrt(bars per horizon)``. Measures each
    move in units of the symbol's own typical move so IC weighs every symbol and
    period equally instead of being dominated by high-volatility samples.

    Fixed conventions (decided 2026-07-02, evidence in HANDOFF; do not turn
    these into searchable parameters):
      * ``vol_window`` defaults to trailing **7D by timestamp** -- tracks crypto
        vol regimes, averages the weekly cycle, and stays a *baseline* during
        the very bursts event factors trade (an EWMA would inflate the
        denominator inside the event and dampen exactly the returns under
        measurement).
      * **Simple rolling std** on the panel's native bar cadence; the caller
        picks the cadence by resampling the panel (signal-frequency match).
      * **sqrt-h scaling** to the horizon: a horse race against direct h-scale
        estimation on real data was a statistical tie, and one per-bar sigma
        series serves the whole horizon grid.
      * **Full-window warmup** (leading ``vol_window`` per symbol is NaN) and an
        epsilon-only denominator floor.
    """
    horizon_delta = pd.Timedelta(horizon)
    window_delta = pd.Timedelta(vol_window)
    if window_delta <= pd.Timedelta(0):
        raise ValueError("vol_window must be positive")
    bars = _bars_per_horizon(data.index, horizon_delta)
    if bars < 1:
        raise ValueError(
            "horizon rounds to zero bars at this panel cadence; "
            "vol normalization needs a horizon of at least one bar"
        )
    forward = _forward_returns(
        data,
        horizon_delta,
        price_column=price_column,
        execution_lag_bars=execution_lag_bars,
    )
    volatility = _trailing_volatility(data, window_delta, price_column=price_column)
    denominator = (volatility * bars**0.5).clip(lower=_VOLATILITY_FLOOR)
    return (forward / denominator).rename(name)


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
