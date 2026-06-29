from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quantaalpha_crypto.evaluation.factor import FactorEvaluation
from quantaalpha_crypto.evaluation.grid import (
    EvaluationGridItem,
    EvaluationGridResult,
    EvaluationGridTrial,
    PnlPanelInput,
    evaluate_fixed_grid,
)


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


@dataclass(frozen=True)
class WalkForwardWindowResult:
    window: WalkForwardWindow
    train_result: EvaluationGridResult
    validation_result: EvaluationGridResult
    test_result: EvaluationGridResult


@dataclass(frozen=True)
class WalkForwardValidationResult:
    windows: list[WalkForwardWindowResult]
    validation_net_return: float = 0.0
    test_net_return: float = 0.0


def build_walk_forward_windows(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    train_window: str = "180D",
    validation_window: str = "30D",
    test_window: str = "30D",
    step: str = "30D",
) -> list[WalkForwardWindow]:
    """Build right-open, time-ordered walk-forward windows."""
    start_at = pd.Timestamp(start)
    end_at = pd.Timestamp(end)
    train_delta = pd.Timedelta(train_window)
    validation_delta = pd.Timedelta(validation_window)
    test_delta = pd.Timedelta(test_window)
    step_delta = pd.Timedelta(step)
    if any(
        delta <= pd.Timedelta(0)
        for delta in (train_delta, validation_delta, test_delta, step_delta)
    ):
        raise ValueError("walk-forward windows and step must be positive")

    windows: list[WalkForwardWindow] = []
    train_start = start_at
    while True:
        train_end = train_start + train_delta
        validation_end = train_end + validation_delta
        test_end = validation_end + test_delta
        if test_end > end_at:
            break
        windows.append(
            WalkForwardWindow(
                train_start=train_start,
                train_end=train_end,
                validation_start=train_end,
                validation_end=validation_end,
                test_start=validation_end,
                test_end=test_end,
            )
        )
        train_start = train_start + step_delta

    return windows


def evaluate_walk_forward(
    factor_evaluation: FactorEvaluation,
    pnl_panel: PnlPanelInput,
    grid: list[EvaluationGridItem],
    windows: list[WalkForwardWindow],
    fee_rate: float = 0.0,
    cost_source: str = "fallback",
) -> WalkForwardValidationResult:
    """Evaluate fixed-grid choices across time-ordered walk-forward windows."""
    window_results = []
    return_cache = {}
    for window in windows:
        _validate_window(window)
        train_result = evaluate_fixed_grid(
            factor_evaluation,
            pnl_panel=pnl_panel,
            grid=grid,
            train_start=window.train_start,
            train_end=window.train_end,
            fee_rate=fee_rate,
            cost_source=cost_source,
            return_cache=return_cache,
        )
        if train_result.selected_trial is None:
            window_results.append(
                WalkForwardWindowResult(
                    window=window,
                    train_result=train_result,
                    validation_result=EvaluationGridResult(trials=[]),
                    test_result=EvaluationGridResult(trials=[]),
                )
            )
            continue

        selected_grid = [_trial_to_grid_item(train_result.selected_trial)]
        validation_result = evaluate_fixed_grid(
            factor_evaluation,
            pnl_panel=pnl_panel,
            grid=selected_grid,
            train_start=window.validation_start,
            train_end=window.validation_end,
            fee_rate=fee_rate,
            cost_source=cost_source,
            return_cache=return_cache,
        )
        test_result = evaluate_fixed_grid(
            factor_evaluation,
            pnl_panel=pnl_panel,
            grid=selected_grid,
            train_start=window.test_start,
            train_end=window.test_end,
            fee_rate=fee_rate,
            cost_source=cost_source,
            return_cache=return_cache,
        )
        window_results.append(
            WalkForwardWindowResult(
                window=window,
                train_result=train_result,
                validation_result=validation_result,
                test_result=test_result,
            )
        )

    return WalkForwardValidationResult(
        windows=window_results,
        validation_net_return=_sum_net_return(
            [result.validation_result for result in window_results]
        ),
        test_net_return=_sum_net_return(
            [result.test_result for result in window_results]
        ),
    )


def _validate_window(window: WalkForwardWindow) -> None:
    if not (
        window.train_start < window.train_end
        <= window.validation_start
        < window.validation_end
        <= window.test_start
        < window.test_end
    ):
        raise ValueError("walk-forward windows must be time ordered")


def _trial_to_grid_item(trial: EvaluationGridTrial) -> EvaluationGridItem:
    item: EvaluationGridItem = {
        "action": trial.action,
        "threshold_quantile": trial.threshold_quantile,
        "holding_horizon": str(trial.holding_horizon),
        "leverage": trial.leverage,
    }
    if trial.update_frequency is not None:
        item["update_frequency"] = str(trial.update_frequency)
    if trial.rebalance_frequency is not None:
        item["rebalance_frequency"] = str(trial.rebalance_frequency)
    if trial.score_threshold is not None:
        item["score_threshold"] = trial.score_threshold
    return item


def _sum_net_return(results: list[EvaluationGridResult]) -> float:
    total = 0.0
    for result in results:
        if result.trials:
            total += result.trials[0].net_return
    return float(total)
