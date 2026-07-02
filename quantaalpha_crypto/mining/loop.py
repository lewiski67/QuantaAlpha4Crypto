"""Minimal end-to-end single-factor verdict (iteration 0.3 walking skeleton).

Glues the evaluation primitive into one runnable judgment: feed a feature panel
and a Factor Callable, get a full-sample IC + Newey-West significance and a
one-line verdict. This is deliberately thin -- all real statistics live in
``evaluation/``; this module only orchestrates and formats, respecting the
``mining/ -> evaluation/`` dependency direction (no LLM, no factor repair).

NOT a research verdict on its own: full-sample single-factor IC is only the
evaluation primitive. Non-stationarity (walk-forward, iteration 1) and
multiple-testing deflation (iteration 2) sit above this.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from quantaalpha_crypto.evaluation.factor import FactorCallable, evaluate_directional_factor
from quantaalpha_crypto.evaluation.panel import CryptoPanel


@dataclass(frozen=True)
class SingleFactorVerdict:
    horizon: pd.Timedelta
    ic: float
    rank_ic: float
    nw_tstat: float
    verdict: str


def judge_single_factor(
    feature_panel: CryptoPanel,
    factor: FactorCallable,
    horizon: str | pd.Timedelta,
    input_lookback_window: str | pd.Timedelta,
    t_threshold: float = 2.0,
    execution_lag_bars: int = 1,
) -> SingleFactorVerdict:
    """Evaluate one factor full-sample and label it by NW significance."""
    evaluation = evaluate_directional_factor(
        feature_panel,
        factor,
        horizon,
        input_lookback_window=input_lookback_window,
        execution_lag_bars=execution_lag_bars,
    )
    return SingleFactorVerdict(
        horizon=evaluation.horizon,
        ic=evaluation.ic,
        rank_ic=evaluation.rank_ic,
        nw_tstat=evaluation.nw_tstat,
        verdict=_verdict_label(evaluation.nw_tstat, t_threshold),
    )


def _verdict_label(nw_tstat: float, t_threshold: float) -> str:
    if math.isnan(nw_tstat):
        return "insufficient-data"
    if abs(nw_tstat) >= t_threshold:
        return "signal"
    return "indistinguishable-from-noise"


def format_verdict(verdict: SingleFactorVerdict) -> str:
    return (
        f"horizon={verdict.horizon}  IC={verdict.ic:+.4f}  "
        f"RankIC={verdict.rank_ic:+.4f}  NW_t={verdict.nw_tstat:+.2f}  "
        f"=>  {verdict.verdict}"
    )
