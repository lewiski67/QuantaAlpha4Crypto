"""Tests for the V1 Base Factor Model (`evaluation/base_model.py`, ADR-0014).

The base model is a fixed, non-searched reference used to compute each
candidate factor's *incremental* significance: regress the candidate's factor
return stream on the base model's benchmark streams, and test whether the
residual still carries a significant (NW-corrected) mean. A candidate that is
just a repackaged benchmark should residualize away to noise.

V1 scope (2026-07-02, evidence in HANDOFF): only the trailing-return family
survived real-data validation (short=2min, long=4h, split-sample robust on
real BTC/ETH/SOL futures across both halves of history); volatility and
funding-rate benchmarks were tested and dropped for lack of signal.
"""

import math

import numpy as np
import pandas as pd
import pytest

from quantaalpha_crypto.evaluation.base_model import (
    LONG_WINDOW,
    SHORT_WINDOW,
    IncrementalSignificance,
    _factor_return_stream,
    _incremental_significance,
    _trailing_return,
    base_factor_scores,
    incremental_significance,
)


def _panel(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    index = pd.MultiIndex.from_tuples(
        [(pd.Timestamp(ts), symbol) for ts, symbol, _ in rows],
        names=["timestamp", "symbol"],
    )
    return pd.DataFrame({"close": [c for _, _, c in rows]}, index=index)


def _minute_panel(closes: list[float], symbol: str = "BTCUSDT", start: str = "2026-01-01") -> pd.DataFrame:
    rows = [
        (str(pd.Timestamp(start) + pd.Timedelta(minutes=i)), symbol, c)
        for i, c in enumerate(closes)
    ]
    return _panel(rows)


def test_trailing_return_basic():
    # close(t) / close(t-2min) - 1, per bar.
    panel = _minute_panel([100.0, 101.0, 103.0, 100.0])
    result = _trailing_return(panel, "2min")
    t2 = (pd.Timestamp("2026-01-01 00:02:00"), "BTCUSDT")
    t3 = (pd.Timestamp("2026-01-01 00:03:00"), "BTCUSDT")
    assert result.loc[t2] == pytest.approx(103.0 / 100.0 - 1.0)
    assert result.loc[t3] == pytest.approx(100.0 / 101.0 - 1.0)
    # First two bars have no bar 2min in the past -> NaN.
    t0 = (pd.Timestamp("2026-01-01 00:00:00"), "BTCUSDT")
    assert math.isnan(result.loc[t0])


def test_trailing_return_is_by_timestamp_not_bar_count():
    # Gap between 00:01 and 00:10. At 00:10, "2min ago" (00:08) does not
    # exist as a bar -> NaN. A bar-count implementation would wrongly use
    # 00:01 (2 bars back) as the reference price.
    rows = [
        ("2026-01-01 00:00:00", "BTCUSDT", 100.0),
        ("2026-01-01 00:01:00", "BTCUSDT", 50.0),
        ("2026-01-01 00:10:00", "BTCUSDT", 200.0),
        ("2026-01-01 00:12:00", "BTCUSDT", 220.0),
    ]
    panel = _panel(rows)
    result = _trailing_return(panel, "2min")
    at_0010 = (pd.Timestamp("2026-01-01 00:10:00"), "BTCUSDT")
    at_0012 = (pd.Timestamp("2026-01-01 00:12:00"), "BTCUSDT")
    assert math.isnan(result.loc[at_0010])
    assert result.loc[at_0012] == pytest.approx(220.0 / 200.0 - 1.0)


def test_trailing_return_per_symbol_independent():
    rows = [
        ("2026-01-01 00:00:00", "BTCUSDT", 100.0),
        ("2026-01-01 00:01:00", "BTCUSDT", 110.0),
        ("2026-01-01 00:00:00", "ETHUSDT", 100.0),
        ("2026-01-01 00:01:00", "ETHUSDT", 90.0),
    ]
    panel = _panel(rows)
    result = _trailing_return(panel, "1min")
    btc = (pd.Timestamp("2026-01-01 00:01:00"), "BTCUSDT")
    eth = (pd.Timestamp("2026-01-01 00:01:00"), "ETHUSDT")
    assert result.loc[btc] == pytest.approx(0.10)
    assert result.loc[eth] == pytest.approx(-0.10)


def test_trailing_return_non_positive_window_raises():
    panel = _minute_panel([100.0, 101.0])
    with pytest.raises(ValueError):
        _trailing_return(panel, "0min")


def test_base_factor_scores_returns_short_and_long_windows():
    panel = _minute_panel([100.0] * 300)
    scores = base_factor_scores(panel)
    assert set(scores) == {"trailing_return_short", "trailing_return_long"}
    # Fixed conventions per ADR-0014 / HANDOFF split-sample validation.
    assert SHORT_WINDOW == pd.Timedelta("2min")
    assert LONG_WINDOW == pd.Timedelta("4h")


def test_factor_return_stream_is_sign_of_score_times_label():
    score = pd.Series([2.0, -1.0, 0.5, -3.0], index=[0, 1, 2, 3])
    label = pd.Series([1.5, 2.0, -0.5, 4.0], index=[0, 1, 2, 3])
    stream = _factor_return_stream(score, label)
    assert stream.tolist() == pytest.approx([1.5, -2.0, -0.5, -4.0])


def test_factor_return_stream_ignores_score_scale():
    # Scaling the score by any positive constant must not change the stream:
    # only the sign carries information (design doc §3.7).
    score = pd.Series([2.0, -1.0, 0.5])
    label = pd.Series([1.0, 1.0, 1.0])
    assert _factor_return_stream(score, label).tolist() == _factor_return_stream(
        score * 100.0, label
    ).tolist()


def test_incremental_significance_public_api_zeroes_out_an_exact_clone():
    # A candidate whose score IS one of the base model's own trailing-return
    # scores is an exact clone: its Factor Return Stream is identical to that
    # benchmark's, so it must residualize to ~0, regardless of the label used.
    panel = _minute_panel(
        [100.0 * (1.01 if i % 3 else 0.985) for i in range(2000)]
    )
    label = pd.Series(
        np.random.default_rng(5).normal(0.0, 1.0, size=2000),
        index=panel.index,
    )
    clone_score = base_factor_scores(panel)["trailing_return_long"]
    result = incremental_significance(clone_score, label, panel, lag=5)
    # Residual is exactly zero (perfect fit against itself), so NW is NaN
    # (zero-variance case, per _nw_tstat's own tested convention) -- an even
    # stronger confirmation than a merely-small nonzero t-stat would be.
    assert math.isnan(result.nw_tstat)
    assert (result.residual.abs() < 1e-9).all()


def test_incremental_significance_residualizes_away_a_perfect_clone():
    # Candidate is exactly 3x a benchmark stream (plus tiny noise): after
    # regressing it out, nothing should remain -> NW collapses toward 0/NaN.
    rng = np.random.default_rng(0)
    n = 2000
    benchmark = pd.Series(rng.normal(0.0, 1.0, size=n))
    noise = rng.normal(0.0, 1e-6, size=n)
    candidate = 3.0 * benchmark + noise
    result = _incremental_significance(candidate, {"bench": benchmark}, lag=5)
    assert isinstance(result, IncrementalSignificance)
    # Residual variance is a noise-floor sliver of the candidate's own
    # variance -> the relative-variance guard reports NaN (no incremental
    # signal), not a numerically fragile small-but-nonzero t-stat.
    assert math.isnan(result.nw_tstat)
    assert result.residual.std() < 1e-3


def test_incremental_significance_survives_when_independent_of_benchmark():
    # Candidate has a real, independent mean-shifted signal; benchmark is
    # unrelated noise. Residualizing should barely change the significance.
    rng = np.random.default_rng(1)
    n = 2000
    benchmark = pd.Series(rng.normal(0.0, 1.0, size=n))
    candidate = pd.Series(rng.normal(0.5, 1.0, size=n))  # independent, real mean
    result = _incremental_significance(candidate, {"bench": benchmark}, lag=5)
    assert result.nw_tstat > 5.0  # strong, unexplained-by-benchmark signal survives


def test_incremental_significance_perfect_fit_on_large_sample_is_nan_not_spurious():
    # Regression test for a real bug found on 1.29M-row real data: an exact
    # clone's residual is theoretically 0 but carries ~1e-16-scale lstsq
    # rounding noise at this sample size, which produced a meaningless
    # |NW|=3.6 before the relative-variance guard was added. Reproduce at
    # comparable scale (large n) so the floating-point noise floor is real,
    # not synthesized directly.
    rng = np.random.default_rng(3)
    n = 500_000
    benchmark = pd.Series(rng.normal(0.0, 1.0, size=n))
    candidate = benchmark * 1.0  # exact clone, no injected noise at all
    result = _incremental_significance(candidate, {"bench": benchmark}, lag=5)
    assert math.isnan(result.nw_tstat)


def test_incremental_significance_handles_multiple_benchmarks():
    rng = np.random.default_rng(2)
    n = 2000
    bench_short = pd.Series(rng.normal(0.0, 1.0, size=n))
    bench_long = pd.Series(rng.normal(0.0, 1.0, size=n))
    candidate = 2.0 * bench_short - 1.0 * bench_long + rng.normal(0.5, 0.1, size=n)
    result = _incremental_significance(
        candidate, {"short": bench_short, "long": bench_long}, lag=5
    )
    # Real leftover mean (~0.5) should still show up as significant.
    assert result.nw_tstat > 5.0
    assert result.coefficients["short"] == pytest.approx(2.0, abs=0.2)
    assert result.coefficients["long"] == pytest.approx(-1.0, abs=0.2)


def test_incremental_significance_aligns_on_intersection_and_drops_na():
    candidate = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=[0, 1, 2, 3, 4])
    benchmark = pd.Series([1.0, np.nan, 3.0, 4.0, 5.0], index=[0, 1, 2, 3, 4])
    result = _incremental_significance(candidate, {"bench": benchmark}, lag=0)
    assert len(result.residual) == 4  # index 1 dropped (NaN benchmark)
