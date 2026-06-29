from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quantaalpha_crypto.evaluation.factor import FactorEvaluation
from quantaalpha_crypto.evaluation.gates import FactorGateResult
from quantaalpha_crypto.evaluation.grid import EvaluationGridTrial
from quantaalpha_crypto.evaluation.walk_forward import WalkForwardValidationResult, WalkForwardWindow


@dataclass(frozen=True)
class FactorEvaluationReport:
    factor_name: str
    feature_data_dependencies: list[str]
    pnl_data_dependencies: list[str]
    walk_forward_windows: list[dict]
    cost_summary: dict
    risk_summary: dict
    ic_stability: dict
    grouped_returns: list[dict]
    gate_outcome: dict
    limitations: list[str]
    live_strategy: bool
    summary: str
    symbol: str | None = None


def build_factor_evaluation_report(
    factor_name: str,
    factor_evaluation: FactorEvaluation,
    walk_forward_result: WalkForwardValidationResult,
    gate_result: FactorGateResult,
    feature_data_dependencies: list[str],
    pnl_data_dependencies: list[str],
    symbol: str | None = None,
) -> FactorEvaluationReport:
    """Build a machine-readable research report for one evaluated factor."""
    return FactorEvaluationReport(
        factor_name=factor_name,
        symbol=symbol,
        feature_data_dependencies=feature_data_dependencies,
        pnl_data_dependencies=pnl_data_dependencies,
        walk_forward_windows=[
            {
                "window": _window_summary(window_result.window),
                "train_trials": [
                    _trial_summary(trial)
                    for trial in window_result.train_result.trials
                ],
                "selected_parameters": _selected_parameters(
                    window_result.train_result.selected_trial
                ),
                "validation_metrics": _metrics(window_result.validation_result.trials),
                "test_metrics": _metrics(window_result.test_result.trials),
            }
            for window_result in walk_forward_result.windows
        ],
        cost_summary=_cost_summary(walk_forward_result),
        risk_summary=_risk_summary(walk_forward_result),
        ic_stability=_ic_stability(gate_result),
        grouped_returns=_grouped_returns(factor_evaluation, walk_forward_result),
        gate_outcome=_gate_outcome(gate_result),
        limitations=_limitations(walk_forward_result),
        live_strategy=False,
        summary="Research artifact for audited factor evaluation.",
    )


def _window_summary(window: WalkForwardWindow) -> dict:
    return {
        "train_start": str(window.train_start),
        "train_end": str(window.train_end),
        "validation_start": str(window.validation_start),
        "validation_end": str(window.validation_end),
        "test_start": str(window.test_start),
        "test_end": str(window.test_end),
    }


def _trial_summary(trial: EvaluationGridTrial) -> dict:
    return {
        "action": trial.action,
        "threshold_quantile": trial.threshold_quantile,
        "holding_horizon": str(trial.holding_horizon),
        "leverage": trial.leverage,
        "selected": trial.selected,
        "net_return": trial.net_return,
        "sharpe": trial.sharpe,
        "turnover": trial.turnover,
        "fee": trial.fee,
        "fee_rate": trial.fee_rate,
        "cost_source": trial.cost_source,
    }


def _selected_parameters(trial: EvaluationGridTrial | None) -> dict | None:
    if trial is None:
        return None
    return {
        "action": trial.action,
        "threshold_quantile": trial.threshold_quantile,
        "holding_horizon": str(trial.holding_horizon),
        "leverage": trial.leverage,
    }


def _metrics(trials: list[EvaluationGridTrial]) -> dict | None:
    if not trials:
        return None
    trial = trials[0]
    return {
        "net_return": trial.net_return,
        "sharpe": trial.sharpe,
    }


def _cost_summary(walk_forward_result: WalkForwardValidationResult) -> dict:
    trials = _oos_trials(walk_forward_result)
    return {
        "cost_sources": sorted({trial.cost_source for trial in trials}),
        "uses_cost_fallback": any(trial.uses_cost_fallback for trial in trials),
        "total_fee": sum(trial.fee for trial in trials),
        "total_turnover": sum(trial.turnover for trial in trials),
        "total_funding_return": sum(trial.funding_return for trial in trials),
    }


def _risk_summary(walk_forward_result: WalkForwardValidationResult) -> dict:
    returns = [trial.net_return for trial in _test_trials(walk_forward_result)]
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for net_return in returns:
        equity += net_return
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
    return {"test_max_drawdown": max_drawdown}


def _ic_stability(gate_result: FactorGateResult) -> dict:
    return {
        "ic_same_sign_rate": gate_result.ic_same_sign_rate,
        "mean_rank_ic": gate_result.mean_rank_ic,
        "abs_mean_rank_ic": gate_result.abs_mean_rank_ic,
    }


def _grouped_returns(
    factor_evaluation: FactorEvaluation,
    walk_forward_result: WalkForwardValidationResult,
    groups: int = 2,
) -> list[dict]:
    del factor_evaluation, groups
    values_by_group: dict[int, list[float]] = {}
    for window_result in walk_forward_result.windows:
        for trial in window_result.test_result.trials[:1]:
            for item in trial.grouped_returns:
                values_by_group.setdefault(int(item["group"]), []).append(
                    float(item["mean_forward_return"])
                )
    if not values_by_group:
        return []
    return [
        {
            "group": group,
            "mean_forward_return": float(pd.Series(values).mean()),
        }
        for group, values in sorted(values_by_group.items())
    ]


def _gate_outcome(gate_result: FactorGateResult) -> dict:
    return {
        "status": gate_result.status,
        "failure_reasons": gate_result.failure_reasons,
        "strong_failure_reasons": gate_result.strong_failure_reasons,
        "test_sharpe": gate_result.test_sharpe,
    }


def _limitations(walk_forward_result: WalkForwardValidationResult) -> list[str]:
    if any(trial.uses_cost_fallback for trial in _oos_trials(walk_forward_result)):
        return ["cost_source_fallback"]
    return []


def _oos_trials(walk_forward_result: WalkForwardValidationResult) -> list[EvaluationGridTrial]:
    return [
        trial
        for window_result in walk_forward_result.windows
        for trial in [
            *window_result.validation_result.trials,
            *window_result.test_result.trials,
        ]
    ]


def _test_trials(walk_forward_result: WalkForwardValidationResult) -> list[EvaluationGridTrial]:
    return [
        trial
        for window_result in walk_forward_result.windows
        for trial in window_result.test_result.trials
    ]
