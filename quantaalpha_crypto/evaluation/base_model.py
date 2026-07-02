"""V1 Base Factor Model (ADR-0014): a fixed, non-searched reference used to
measure a candidate factor's *incremental* significance.

Design (2026-07-02, evidence in HANDOFF):
  * The base model is one family -- trailing return at two fixed window
    points -- not two separately-signed "momentum" and "reversal" factors.
    Real-data testing (BTC/ETH/SOL USD-M futures, split-sample robust across
    both halves of history) found the momentum/reversal sign itself is
    symbol-dependent (BTC/SOL: short-horizon reversal; ETH: longer-horizon
    momentum), so the sign is not pre-committed. Each raw trailing-return
    stream is used as a spanning regressor; its fitted coefficient (sign and
    magnitude) is discovered per candidate/symbol by OLS, not declared upfront.
  * SHORT_WINDOW = 2min, LONG_WINDOW = 4h: the only two window points that
    showed NW-significant, split-sample-robust behavior for all three symbols
    (short) or for the symbol where the effect genuinely exists (long, ETH).
    1min was avoided for the short window despite slightly higher raw
    significance -- it is more exposed to bid-ask-bounce microstructure noise.
  * Volatility and funding-rate benchmarks were evaluated and dropped for V1:
    volatility has no natural directional score at this scale (BAB/low-vol is
    a cross-sectional construct, degenerate at N=2-3; the leverage-effect
    time-series alternative is unverified on crypto; volatility risk premium
    needs options data this project's data pipeline does not have). Funding
    rate (raw level, multiple averaging windows, z-score, and extreme-quantile
    constructs) showed no significant directional relationship with the
    vol-norm label at any V1 horizon on real futures data.
  * Both windows are shared across all symbols (no per-symbol tuning) per the
    project's zero-free-parameter/fixed-convention discipline; cross-symbol
    heterogeneity is absorbed by the regression coefficients in
    ``_incremental_significance``, not by choosing different windows per
    symbol.

Data source: this project is scoped to Binance USD-M futures only for now
(spot excluded; fee economics). Callers should pass a futures panel.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantaalpha_crypto.evaluation.metrics import _nw_tstat

SHORT_WINDOW = pd.Timedelta("2min")
LONG_WINDOW = pd.Timedelta("4h")


def _trailing_return(
    data: pd.DataFrame,
    window: str | pd.Timedelta,
    price_column: str = "close",
    name: str = "trailing_return",
) -> pd.Series:
    """Backward-looking ``close(t) / close(t - window) - 1``, per symbol.

    Looked up by timestamp, not bar count, so gaps cannot silently reference
    the wrong bar (same discipline as purge in ``walk_forward.py`` and the
    trailing-volatility window in ``_vol_norm_returns``): if no bar exists
    exactly ``window`` in the past, the result is NaN rather than falling back
    to the nearest available bar.
    """
    window_delta = pd.Timedelta(window)
    if window_delta <= pd.Timedelta(0):
        raise ValueError("window must be positive")

    pieces = []
    for symbol, symbol_data in data.sort_index().groupby(level="symbol", sort=False):
        close = symbol_data[price_column].astype("float64")
        timestamps = close.index.get_level_values("timestamp")
        lookback_index = pd.MultiIndex.from_arrays(
            [timestamps - window_delta, [symbol] * len(timestamps)],
            names=["timestamp", "symbol"],
        )
        lookback_close = close.reindex(lookback_index)
        lookback_close.index = close.index
        pieces.append(close / lookback_close - 1.0)

    if not pieces:
        return pd.Series(dtype="float64", name=name)
    return pd.concat(pieces).sort_index().rename(name)


def base_factor_scores(
    data: pd.DataFrame, price_column: str = "close"
) -> dict[str, pd.Series]:
    """The V1 Base Factor Model's fixed benchmark *scores* (ADR-0014).

    Raw trailing-return values, not yet Factor Return Streams -- a score has
    no notion of "incremental information" on its own; it must be paired with
    a label (via ``_factor_return_stream``) at the same horizon as whatever
    candidate it is being compared against.
    """
    return {
        "trailing_return_short": _trailing_return(data, SHORT_WINDOW, price_column),
        "trailing_return_long": _trailing_return(data, LONG_WINDOW, price_column),
    }


def _factor_return_stream(score: pd.Series, label: pd.Series) -> pd.Series:
    """``sign(score) x label`` -- the Factor Return Stream convention (design
    doc §3.7): the one parameter-free construction allowed for orthogonality /
    incremental-IC evidence, so a score's own scale never matters, only its
    sign each period.
    """
    aligned = pd.concat(
        [score.rename("score"), label.rename("label")], axis=1, join="inner"
    ).dropna()
    return (np.sign(aligned["score"]) * aligned["label"]).rename("stream")


def incremental_significance(
    candidate_score: pd.Series,
    label: pd.Series,
    data: pd.DataFrame,
    lag: int,
    price_column: str = "close",
) -> IncrementalSignificance:
    """Candidate's incremental significance over the V1 Base Factor Model.

    Builds the candidate's and each benchmark's Factor Return Stream from the
    *same* ``label`` (so they are directly comparable) and the *same*
    ``sign(score) x label`` construction (so an exact clone of a benchmark
    produces an exact clone of its stream, and residualizes to ~0) before
    delegating to ``_incremental_significance``.
    """
    candidate_stream = _factor_return_stream(candidate_score, label)
    benchmark_streams = {
        name: _factor_return_stream(score, label)
        for name, score in base_factor_scores(data, price_column).items()
    }
    return _incremental_significance(candidate_stream, benchmark_streams, lag)


@dataclass(frozen=True)
class IncrementalSignificance:
    residual: pd.Series
    nw_tstat: float
    coefficients: dict[str, float]


def _incremental_significance(
    candidate_stream: pd.Series,
    benchmark_streams: dict[str, pd.Series],
    lag: int,
) -> IncrementalSignificance:
    """How much of a candidate's factor return stream survives the base model.

    Regresses ``candidate_stream`` (a parameter-free ``sign(score) x
    forward_return`` stream, per the Factor Return Stream convention) on the
    benchmark streams with an implicit intercept (Fama-French-style spanning
    regression), and reports the NW t-stat of that intercept -- the average
    payoff the benchmarks cannot explain. A candidate that is just a
    repackaged benchmark spans to an intercept of ~0; genuine incremental
    information leaves a significant intercept.

    Implementation note: the intercept is recovered via the Frisch-Waugh-Lovell
    theorem rather than adding a constant column directly, because an OLS
    residual from a regression *with* an explicit intercept has mean exactly
    zero by construction -- testing that residual's mean would trivially
    always yield ~0, never the intercept's significance. FWL gives the same
    slope coefficients from a mean-centered, intercept-free regression; the
    intercept is then the mean of (original candidate minus fitted slopes on
    original benchmarks), on which ``_nw_tstat`` correctly tests significance.

    In-sample fit (no train/test split): the walk-forward wiring that fits
    coefficients on train and applies them on test is deferred to iteration
    1.5, same as ``_vol_norm_returns`` in 1.2.
    """
    columns = {"candidate": candidate_stream, **benchmark_streams}
    aligned = pd.concat(
        [series.rename(name) for name, series in columns.items()], axis=1, join="inner"
    ).dropna()

    y = aligned["candidate"].to_numpy()
    benchmark_names = list(benchmark_streams)
    design = np.column_stack([aligned[name].to_numpy() for name in benchmark_names])

    slopes, *_ = np.linalg.lstsq(design - design.mean(axis=0), y - y.mean(), rcond=None)
    residual = pd.Series(y - design @ slopes, index=aligned.index)  # mean == intercept

    coefficients = dict(zip(benchmark_names, slopes))
    coefficients["const"] = float(residual.mean())

    # A residual variance that is a floating-point-noise sliver of the
    # candidate's own variance means "no information left" (an exact or
    # near-exact clone) -- not a spurious NW t-stat from dividing two
    # machine-epsilon-scale numbers (observed on real 1.29M-row data: an
    # exact clone's residual carries ~1e-16-scale rounding noise from the
    # lstsq solve, which produced a meaningless |t|=3.6 before this guard).
    candidate_variance = float(np.var(y))
    if candidate_variance <= 0.0 or residual.var(ddof=0) <= 1e-8 * candidate_variance:
        nw_tstat = float("nan")
    else:
        nw_tstat = _nw_tstat(residual, lag)

    return IncrementalSignificance(
        residual=residual,
        nw_tstat=nw_tstat,
        coefficients=coefficients,
    )
