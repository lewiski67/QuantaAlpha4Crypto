"""Tests for shared evaluation metric primitives (`evaluation/metrics.py`)."""

import math

import numpy as np
import pandas as pd
import pytest

from quantaalpha_crypto.evaluation.metrics import (
    _bars_per_horizon,
    _forward_returns,
    _nw_tstat,
    _vol_norm_returns,
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


def _close_frame(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    """rows = [(timestamp, symbol, close), ...] -> panel-shaped DataFrame."""
    index = pd.MultiIndex.from_tuples(
        [(pd.Timestamp(ts), symbol) for ts, symbol, _ in rows],
        names=["timestamp", "symbol"],
    )
    return pd.DataFrame({"close": [close for _, _, close in rows]}, index=index)


def _daily_alternating(n: int, symbol: str = "BTCUSDT") -> pd.DataFrame:
    # closes alternate +10% / -10%: 100, 110, 99, 108.9, 98.01, ...
    closes, price = [], 100.0
    for i in range(n):
        closes.append(price)
        price *= 1.10 if i % 2 == 0 else 0.90
    return _close_frame(
        [
            (str(pd.Timestamp("2026-01-01") + pd.Timedelta(days=i)), symbol, c)
            for i, c in enumerate(closes)
        ]
    )


def test_vol_norm_returns_divides_by_trailing_std():
    # Daily bars, horizon=1D (1 bar -> sqrt-scale 1), vol_window=2D, lag=0.
    # At day2 the (day0, day2] window holds returns [+0.10, -0.10]:
    # std(ddof=1)=sqrt(0.02); fwd(day2)=+0.10 -> label=0.10/sqrt(0.02).
    data = _daily_alternating(6)
    labels = _vol_norm_returns(
        data, pd.Timedelta("1D"), vol_window="2D", execution_lag_bars=0
    )
    day2 = (pd.Timestamp("2026-01-03"), "BTCUSDT")
    day3 = (pd.Timestamp("2026-01-04"), "BTCUSDT")
    assert labels.loc[day2] == pytest.approx(0.10 / math.sqrt(0.02))
    assert labels.loc[day3] == pytest.approx(-0.10 / math.sqrt(0.02))


def test_vol_norm_returns_scales_sigma_by_sqrt_horizon_bars():
    # horizon=2D on daily bars -> 2 bars -> denominator = std * sqrt(2).
    # At day2: fwd_2D = 98.01/99-1 = -0.01; denom = sqrt(0.02)*sqrt(2) = 0.2
    # -> label = -0.05 exactly.
    data = _daily_alternating(6)
    labels = _vol_norm_returns(
        data, pd.Timedelta("2D"), vol_window="2D", execution_lag_bars=0
    )
    day2 = (pd.Timestamp("2026-01-03"), "BTCUSDT")
    assert labels.loc[day2] == pytest.approx(-0.05)


def test_vol_norm_window_is_by_timestamp_across_a_gap():
    # Bars at day0..day3 then a gap to day10..day13. At day11 the (day8, day11]
    # window holds only the returns stamped day10 and day11; a 3-bar-count
    # window would wrongly reach back across the gap to day3's return.
    rows = [
        ("2026-01-01", "BTCUSDT", 100.0),
        ("2026-01-02", "BTCUSDT", 101.0),
        ("2026-01-03", "BTCUSDT", 102.0),
        ("2026-01-04", "BTCUSDT", 103.0),
        ("2026-01-11", "BTCUSDT", 100.0),
        ("2026-01-12", "BTCUSDT", 105.0),
        ("2026-01-13", "BTCUSDT", 110.0),
        ("2026-01-14", "BTCUSDT", 121.0),
    ]
    data = _close_frame(rows)
    labels = _vol_norm_returns(
        data, pd.Timedelta("1D"), vol_window="3D", execution_lag_bars=0
    )
    r_gap = 100.0 / 103.0 - 1.0   # stamped 01-11 (spans the gap)
    r_12 = 105.0 / 100.0 - 1.0
    expected_std = pd.Series([r_gap, r_12]).std()  # ddof=1, exactly these two
    fwd_12 = 110.0 / 105.0 - 1.0
    day12 = (pd.Timestamp("2026-01-12"), "BTCUSDT")
    assert labels.loc[day12] == pytest.approx(fwd_12 / expected_std)


def test_vol_norm_default_window_is_7d_with_full_window_warmup():
    # Default vol_window="7D": bars with < 7D of history are NaN. With 10 daily
    # bars, lag=0, horizon=1D: days 0-6 are warmup-NaN; day 9 has no exit;
    # exactly days 7 and 8 carry labels.
    data = _daily_alternating(10)
    labels = _vol_norm_returns(data, pd.Timedelta("1D"), execution_lag_bars=0)
    stamps = labels.dropna().index.get_level_values("timestamp")
    assert list(stamps) == [
        pd.Timestamp("2026-01-08"),
        pd.Timestamp("2026-01-09"),
    ]


def test_vol_norm_zero_volatility_is_floored_not_inf():
    # Constant prices: sigma=0 and fwd=0 -> labels are 0.0 (not inf/NaN blowups).
    rows = [
        (str(pd.Timestamp("2026-01-01") + pd.Timedelta(days=i)), "BTCUSDT", 100.0)
        for i in range(8)
    ]
    data = _close_frame(rows)
    labels = _vol_norm_returns(
        data, pd.Timedelta("1D"), vol_window="2D", execution_lag_bars=0
    )
    valid = labels.dropna()
    assert len(valid) > 0
    assert np.isfinite(valid).all()
    assert (valid == 0.0).all()


def test_vol_norm_normalizes_each_symbol_by_its_own_volatility():
    # Same alternating-return pattern at 10x different amplitude: after
    # self-normalization the labels are identical -- volatility scale is gone.
    calm, wild, price_a, price_b = [], [], 100.0, 100.0
    start = pd.Timestamp("2026-01-01")
    for i in range(6):
        calm.append((str(start + pd.Timedelta(days=i)), "AAAUSDT", price_a))
        wild.append((str(start + pd.Timedelta(days=i)), "BBBUSDT", price_b))
        up = i % 2 == 0
        price_a *= 1.01 if up else 0.99
        price_b *= 1.10 if up else 0.90
    data = _close_frame(calm + wild)
    labels = _vol_norm_returns(
        data, pd.Timedelta("1D"), vol_window="2D", execution_lag_bars=0
    )
    day2 = pd.Timestamp("2026-01-03")
    assert labels.loc[(day2, "AAAUSDT")] == pytest.approx(
        labels.loc[(day2, "BBBUSDT")]
    )


def test_vol_norm_works_on_minute_bars():
    # Frequency-agnostic: sigma estimated on the panel's native cadence and
    # sqrt-scaled by bars-per-horizon (2min on 1m bars -> sqrt(2)).
    closes, price = [], 100.0
    for i in range(8):
        closes.append(price)
        price *= 1.10 if i % 2 == 0 else 0.90
    rows = [
        (str(pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=i)), "BTCUSDT", c)
        for i, c in enumerate(closes)
    ]
    data = _close_frame(rows)
    labels = _vol_norm_returns(
        data, pd.Timedelta("2min"), vol_window="4min", execution_lag_bars=0
    )
    # At t=4min: window (0,4] holds returns [+.1,-.1,+.1,-.1] -> std=sqrt(0.04/3);
    # fwd_2min = 1.1*0.9-1 = -0.01; denom = std*sqrt(2).
    t4 = (pd.Timestamp("2026-01-01 00:04:00"), "BTCUSDT")
    expected = -0.01 / (math.sqrt(0.04 / 3) * math.sqrt(2))
    assert labels.loc[t4] == pytest.approx(expected)


def test_vol_norm_sub_bar_horizon_raises():
    # A horizon that rounds to zero bars cannot be sqrt-scaled meaningfully.
    data = _daily_alternating(6)
    with pytest.raises(ValueError):
        _vol_norm_returns(data, pd.Timedelta("1h"), vol_window="2D")


def test_vol_norm_non_positive_window_raises():
    data = _daily_alternating(6)
    with pytest.raises(ValueError):
        _vol_norm_returns(data, pd.Timedelta("1D"), vol_window="0D")
