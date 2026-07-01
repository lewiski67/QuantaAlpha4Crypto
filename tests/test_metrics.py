"""Tests for shared evaluation metric primitives (`evaluation/metrics.py`)."""

import math

import numpy as np
import pandas as pd
import pytest

from quantaalpha_crypto.evaluation.metrics import (
    _bars_per_horizon,
    _forward_returns,
    _nw_tstat,
)


def test_forward_returns_preserve_tz_aware_index():
    # Real Binance panels carry tz-aware (UTC) timestamps; the entry-timestamp
    # rebuild must keep the tz or reindex silently yields all-NaN forward returns.
    timestamps = pd.date_range("2024-01-01", periods=5, freq="1min", tz="UTC")
    close = [100.0, 101.0, 102.0, 103.0, 104.0]
    data = pd.DataFrame(
        {"close": close},
        index=pd.MultiIndex.from_arrays(
            [timestamps, ["BTCUSDT"] * 5], names=["timestamp", "symbol"]
        ),
    )
    fwd = _forward_returns(data, pd.Timedelta("1min"), execution_lag_bars=1)
    # t=0: entry@t1(101) exit@t2(102) -> +0.0099...; must not be all-NaN.
    assert fwd.notna().sum() >= 2
    assert fwd.iloc[0] == pytest.approx(102.0 / 101.0 - 1.0)


def _panel_index(
    symbols: list[str], n: int, freq: str = "5min", start: str = "2026-01-01"
) -> pd.MultiIndex:
    tuples = []
    for symbol in symbols:
        for timestamp in pd.date_range(start, periods=n, freq=freq):
            tuples.append((timestamp, symbol))
    return pd.MultiIndex.from_tuples(tuples, names=["timestamp", "symbol"])


def test_bars_per_horizon_basic():
    idx = _panel_index(["BTCUSDT"], n=20, freq="5min")
    assert _bars_per_horizon(idx, pd.Timedelta("15min")) == 3


def test_bars_per_horizon_rounds_to_nearest_bar():
    idx = _panel_index(["BTCUSDT"], n=20, freq="5min")
    assert _bars_per_horizon(idx, pd.Timedelta("12min")) == 2  # 2.4 -> 2


def test_bars_per_horizon_multi_symbol_consistent():
    idx = _panel_index(["BTCUSDT", "ETHUSDT"], n=20, freq="5min")
    assert _bars_per_horizon(idx, pd.Timedelta("30min")) == 6


def test_bars_per_horizon_sub_bar_horizon_rounds_to_zero():
    idx = _panel_index(["BTCUSDT"], n=20, freq="5min")
    assert _bars_per_horizon(idx, pd.Timedelta("2min")) == 0  # 0.4 -> 0


def test_bars_per_horizon_inconsistent_intervals_raises():
    idx = _panel_index(["BTCUSDT"], n=10, freq="5min").append(
        _panel_index(["ETHUSDT"], n=10, freq="1min")
    )
    with pytest.raises(ValueError):
        _bars_per_horizon(idx, pd.Timedelta("15min"))


def test_bars_per_horizon_insufficient_timestamps_raises():
    idx = pd.MultiIndex.from_tuples(
        [(pd.Timestamp("2026-01-01"), "BTCUSDT")], names=["timestamp", "symbol"]
    )
    with pytest.raises(ValueError):
        _bars_per_horizon(idx, pd.Timedelta("5min"))


def test_bars_per_horizon_non_positive_horizon_raises():
    idx = _panel_index(["BTCUSDT"], n=20, freq="5min")
    with pytest.raises(ValueError):
        _bars_per_horizon(idx, pd.Timedelta(0))


def _naive_tstat(x: pd.Series) -> float:
    n = len(x)
    std = x.std(ddof=0)
    return float(x.mean() / (std / math.sqrt(n)))


def _ar1(n: int, phi: float, mu: float, sigma: float, seed: int) -> pd.Series:
    """Deterministic AR(1) with positive autocorrelation when phi > 0."""
    rng = np.random.default_rng(seed)
    eps = rng.normal(0.0, sigma, size=n)
    out = np.empty(n)
    out[0] = mu + eps[0]
    for t in range(1, n):
        out[t] = mu + phi * (out[t - 1] - mu) + eps[t]
    return pd.Series(out)


def test_nw_tstat_deflates_positive_autocorrelation():
    # Overlapping-return-style positive autocorrelation must shrink the t-stat
    # relative to the naive (independence-assuming) estimate.
    x = _ar1(n=500, phi=0.8, mu=0.5, sigma=1.0, seed=7)
    naive = _naive_tstat(x)
    nw = _nw_tstat(x, lag=10)

    # NW only rescales the standard error, never flips the sign of the estimate.
    assert math.copysign(1.0, nw) == math.copysign(1.0, naive)
    # Positive autocorrelation inflates the naive significance; NW shrinks it.
    assert abs(nw) < abs(naive)


def test_nw_tstat_lag_zero_equals_naive():
    # lag=0 applies no autocorrelation correction: exact naive t-stat.
    x = _ar1(n=300, phi=0.6, mu=0.3, sigma=1.0, seed=3)
    assert _nw_tstat(x, lag=0) == pytest.approx(_naive_tstat(x), rel=1e-9)


def test_nw_tstat_uncorrelated_series_close_to_naive():
    # White noise has ~zero autocovariance, so NW ≈ naive even with lag > 0.
    rng = np.random.default_rng(11)
    x = pd.Series(rng.normal(0.4, 1.0, size=2000))
    naive = _naive_tstat(x)
    nw = _nw_tstat(x, lag=10)
    assert 0.85 < nw / naive < 1.15


def test_nw_tstat_empty_series_is_nan():
    assert math.isnan(_nw_tstat(pd.Series(dtype="float64"), lag=5))


def test_nw_tstat_too_few_samples_is_nan():
    assert math.isnan(_nw_tstat(pd.Series([1.0, 2.0, 3.0]), lag=5))


def test_nw_tstat_zero_variance_is_nan():
    assert math.isnan(_nw_tstat(pd.Series([2.0, 2.0, 2.0, 2.0, 2.0]), lag=2))
