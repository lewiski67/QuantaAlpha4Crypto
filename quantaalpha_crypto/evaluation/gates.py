from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from quantaalpha_crypto.evaluation.factor import FactorEvaluation
from quantaalpha_crypto.evaluation.walk_forward import WalkForwardValidationResult


GateStatus = Literal["rejected", "candidate", "strong"]


@dataclass(frozen=True)
class FactorGateResult:
    status: GateStatus
    failure_reasons: list[str]
    strong_failure_reasons: list[str]
    ic_same_sign_rate: float
    mean_rank_ic: float
    abs_mean_rank_ic: float
    test_sharpe: float


def evaluate_factor_gates(
    factor_evaluation: FactorEvaluation,
    walk_forward_result: WalkForwardValidationResult,
) -> FactorGateResult:
    """Classify a Directional Factor using first-stage acceptance gates."""
    rank_ics = _test_window_rank_ics(factor_evaluation, walk_forward_result)
    ic_same_sign_rate = _same_sign_rate(rank_ics)
    mean_rank_ic = float(pd.Series(rank_ics, dtype="float64").mean())
    abs_mean_rank_ic = abs(mean_rank_ic)
    test_sharpe = _mean_test_sharpe(walk_forward_result)
    train_sharpe = _mean_train_sharpe(walk_forward_result)

    failure_reasons = []
    if _has_incomplete_window(walk_forward_result):
        failure_reasons.append("incomplete_walk_forward_window")
    if ic_same_sign_rate < 0.6 or abs_mean_rank_ic < 0.01:
        failure_reasons.append("unstable_ic")
    if walk_forward_result.test_net_return <= 0:
        failure_reasons.append("non_positive_oos_return")
    if pd.isna(test_sharpe) or test_sharpe <= 0.8:
        failure_reasons.append("low_test_sharpe")

    if failure_reasons:
        return FactorGateResult(
            status="rejected",
            failure_reasons=failure_reasons,
            strong_failure_reasons=[],
            ic_same_sign_rate=ic_same_sign_rate,
            mean_rank_ic=mean_rank_ic,
            abs_mean_rank_ic=abs_mean_rank_ic,
            test_sharpe=test_sharpe,
        )

    strong_failure_reasons = []
    if test_sharpe <= 1.2:
        strong_failure_reasons.append("low_strong_test_sharpe")
    if _has_train_to_test_collapse(train_sharpe=train_sharpe, test_sharpe=test_sharpe):
        strong_failure_reasons.append("train_to_test_collapse")
    return FactorGateResult(
        status="strong" if not strong_failure_reasons else "candidate",
        failure_reasons=[],
        strong_failure_reasons=strong_failure_reasons,
        ic_same_sign_rate=ic_same_sign_rate,
        mean_rank_ic=mean_rank_ic,
        abs_mean_rank_ic=abs_mean_rank_ic,
        test_sharpe=test_sharpe,
    )


def _test_window_rank_ics(
    factor_evaluation: FactorEvaluation,
    walk_forward_result: WalkForwardValidationResult,
) -> list[float]:
    del factor_evaluation
    return [
        trial.rank_ic
        for window_result in walk_forward_result.windows
        for trial in window_result.test_result.trials[:1]
        if pd.notna(trial.rank_ic)
    ]


def _same_sign_rate(values: list[float]) -> float:
    clean = [value for value in values if pd.notna(value) and value != 0]
    if not clean:
        return 0.0
    positive = sum(value > 0 for value in clean)
    negative = len(clean) - positive
    return max(positive, negative) / len(clean)


def _has_incomplete_window(walk_forward_result: WalkForwardValidationResult) -> bool:
    return any(
        window_result.train_result.selected_trial is None
        or not window_result.validation_result.trials
        or not window_result.test_result.trials
        for window_result in walk_forward_result.windows
    )


def _mean_test_sharpe(walk_forward_result: WalkForwardValidationResult) -> float:
    sharpes = [
        result.test_result.trials[0].sharpe
        for result in walk_forward_result.windows
        if result.test_result.trials
    ]
    if not sharpes:
        return float("nan")
    return float(pd.Series(sharpes, dtype="float64").mean())


def _mean_train_sharpe(walk_forward_result: WalkForwardValidationResult) -> float:
    sharpes = [
        result.train_result.selected_trial.sharpe
        for result in walk_forward_result.windows
        if result.train_result.selected_trial is not None
    ]
    if not sharpes:
        return float("nan")
    return float(pd.Series(sharpes, dtype="float64").mean())


def _has_train_to_test_collapse(train_sharpe: float, test_sharpe: float) -> bool:
    if pd.isna(train_sharpe) or train_sharpe <= 0:
        return False
    if pd.isna(test_sharpe):
        return True
    return test_sharpe < train_sharpe * 0.5
