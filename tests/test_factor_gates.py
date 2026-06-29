import pandas as pd
import pytest

from quantaalpha_crypto import (
    EvaluationGridResult,
    EvaluationGridTrial,
    FactorEvaluation,
    WalkForwardValidationResult,
    WalkForwardWindow,
    WalkForwardWindowResult,
    evaluate_factor_gates,
)


def test_candidate_gate_rejects_unstable_out_of_sample_directionality():
    factor_evaluation = _factor_evaluation_with_test_rank_ics([1.0, -1.0])
    walk_forward_result = _walk_forward_result(
        test_sharpes=[1.0, 1.0],
        test_rank_ics=[1.0, -1.0],
    )

    result = evaluate_factor_gates(factor_evaluation, walk_forward_result)

    assert result.status == "rejected"
    assert "unstable_ic" in result.failure_reasons
    assert result.ic_same_sign_rate == 0.5
    assert result.mean_rank_ic == 0.0


def test_candidate_gate_rejects_non_positive_out_of_sample_net_return():
    factor_evaluation = _factor_evaluation_with_test_rank_ics([1.0, 1.0])
    walk_forward_result = _walk_forward_result(
        test_sharpes=[1.0, 1.0],
        test_net_returns=[0.1, -0.1],
    )

    result = evaluate_factor_gates(factor_evaluation, walk_forward_result)

    assert result.status == "rejected"
    assert "non_positive_oos_return" in result.failure_reasons


def test_candidate_gate_rejects_test_sharpe_not_above_point_eight():
    factor_evaluation = _factor_evaluation_with_test_rank_ics([1.0, 1.0])
    walk_forward_result = _walk_forward_result(test_sharpes=[0.8, 0.8])

    result = evaluate_factor_gates(factor_evaluation, walk_forward_result)

    assert result.status == "rejected"
    assert "low_test_sharpe" in result.failure_reasons
    assert result.test_sharpe == 0.8


def test_candidate_gate_rejects_incomplete_walk_forward_window():
    factor_evaluation = _factor_evaluation_with_test_rank_ics([1.0, 1.0])
    walk_forward_result = _walk_forward_result(test_sharpes=[1.0, 1.0])
    incomplete_window = walk_forward_result.windows[0]
    walk_forward_result = WalkForwardValidationResult(
        windows=[
            WalkForwardWindowResult(
                window=incomplete_window.window,
                train_result=EvaluationGridResult(trials=incomplete_window.train_result.trials),
                validation_result=EvaluationGridResult(trials=[]),
                test_result=EvaluationGridResult(trials=[]),
            ),
            walk_forward_result.windows[1],
        ],
        validation_net_return=0.1,
        test_net_return=0.1,
    )

    result = evaluate_factor_gates(factor_evaluation, walk_forward_result)

    assert result.status == "rejected"
    assert "incomplete_walk_forward_window" in result.failure_reasons


def test_strong_gate_passes_when_candidate_passes_with_high_test_sharpe_and_no_collapse():
    factor_evaluation = _factor_evaluation_with_test_rank_ics([1.0, 1.0])
    walk_forward_result = _walk_forward_result(test_sharpes=[1.3, 1.3])

    result = evaluate_factor_gates(factor_evaluation, walk_forward_result)

    assert result.status == "strong"
    assert result.failure_reasons == []


def test_strong_gate_does_not_pass_when_train_to_test_sharpe_collapses():
    factor_evaluation = _factor_evaluation_with_test_rank_ics([1.0, 1.0])
    walk_forward_result = _walk_forward_result(
        train_sharpes=[3.0, 3.0],
        test_sharpes=[1.3, 1.3],
    )

    result = evaluate_factor_gates(factor_evaluation, walk_forward_result)

    assert result.status == "candidate"
    assert "train_to_test_collapse" in result.strong_failure_reasons


def test_gate_evidence_includes_same_sign_rate_and_absolute_mean_rank_ic():
    factor_evaluation = _factor_evaluation_with_test_rank_ics([-1.0, -1.0])
    walk_forward_result = _walk_forward_result(
        test_sharpes=[1.0, 1.0],
        test_rank_ics=[-1.0, -1.0],
    )

    result = evaluate_factor_gates(factor_evaluation, walk_forward_result)

    assert result.status == "candidate"
    assert result.ic_same_sign_rate == 1.0
    assert result.mean_rank_ic == pytest.approx(-1.0)
    assert result.abs_mean_rank_ic == pytest.approx(1.0)


def test_candidate_gate_uses_selected_trial_holding_horizon_rank_ic():
    factor_evaluation = _factor_evaluation_with_test_rank_ics([1.0, -1.0])
    walk_forward_result = _walk_forward_result(
        test_sharpes=[1.0, 1.0],
        test_rank_ics=[1.0, 1.0],
    )

    result = evaluate_factor_gates(factor_evaluation, walk_forward_result)

    assert result.status == "candidate"
    assert result.ic_same_sign_rate == 1.0
    assert result.mean_rank_ic == pytest.approx(1.0)


def _factor_evaluation_with_test_rank_ics(rank_ics: list[float]) -> FactorEvaluation:
    rows = []
    for window_idx, rank_ic in enumerate(rank_ics):
        timestamp = pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=window_idx)
        if rank_ic > 0:
            returns = [0.01, 0.02]
        else:
            returns = [0.02, 0.01]
        rows.extend(
            [
                (timestamp, "BTCUSDT", 1.0, returns[0]),
                (timestamp, "ETHUSDT", 2.0, returns[1]),
            ]
        )

    index = pd.MultiIndex.from_tuples(
        [(timestamp, symbol) for timestamp, symbol, _, _ in rows],
        names=["timestamp", "symbol"],
    )
    scores = pd.Series([score for _, _, score, _ in rows], index=index)
    forward_returns = pd.Series([ret for _, _, _, ret in rows], index=index)
    return FactorEvaluation(
        horizon=pd.Timedelta("1min"),
        scores=scores,
        forward_returns=forward_returns,
        ic=float("nan"),
        rank_ic=float("nan"),
    )


def _walk_forward_result(
    test_sharpes: list[float],
    test_net_returns: list[float] | None = None,
    train_sharpes: list[float] | None = None,
    test_rank_ics: list[float] | None = None,
) -> WalkForwardValidationResult:
    if test_net_returns is None:
        test_net_returns = [0.1] * len(test_sharpes)
    if train_sharpes is None:
        train_sharpes = [1.5] * len(test_sharpes)
    if test_rank_ics is None:
        test_rank_ics = test_sharpes

    windows = []
    for window_idx, test_sharpe in enumerate(test_sharpes):
        test_start = pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=window_idx)
        windows.append(
            WalkForwardWindowResult(
                window=WalkForwardWindow(
                    train_start=test_start - pd.Timedelta(minutes=2),
                    train_end=test_start - pd.Timedelta(minutes=1),
                    validation_start=test_start - pd.Timedelta(minutes=1),
                    validation_end=test_start,
                    test_start=test_start,
                    test_end=test_start + pd.Timedelta(minutes=1),
                ),
                train_result=_grid_result(net_return=0.1, sharpe=train_sharpes[window_idx]),
                validation_result=_grid_result(net_return=0.1, sharpe=1.0),
                test_result=_grid_result(
                    net_return=test_net_returns[window_idx],
                    sharpe=test_sharpe,
                    rank_ic=test_rank_ics[window_idx],
                ),
            )
        )
    return WalkForwardValidationResult(
        windows=windows,
        validation_net_return=sum(
            window.validation_result.trials[0].net_return for window in windows
        ),
        test_net_return=sum(window.test_result.trials[0].net_return for window in windows),
    )


def _grid_result(net_return: float, sharpe: float, rank_ic: float = 1.0) -> EvaluationGridResult:
    trial = EvaluationGridTrial(
        action="spot_long",
        threshold_quantile=0.8,
        holding_horizon=pd.Timedelta("1min"),
        leverage=1.0,
        trade_count=1,
        net_return=net_return,
        sharpe=sharpe,
        rank_ic=rank_ic,
    )
    return EvaluationGridResult(trials=[trial], selected_trial=trial)
