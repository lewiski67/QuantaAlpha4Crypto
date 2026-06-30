import json

import pytest

from quantaalpha_crypto import (
    FactorEvaluationReport,
    FactorGateResult,
    append_candidate_factor_library_entry,
    load_candidate_factor_library,
)


def test_candidate_factor_library_stores_candidate_gate_pass_with_report_and_gate_metadata(tmp_path):
    library_path = tmp_path / "candidate_factors.json"

    entry = append_candidate_factor_library_entry(
        library_path=library_path,
        factor_callable_reference="tests.factors.close_momentum",
        report_reference="reports/close_momentum.json",
        report=_report(gate_status="candidate"),
        gate_result=_gate_result(status="candidate", test_sharpe=0.9),
    )

    assert entry is not None
    assert entry.factor_name == "close_momentum"
    assert entry.symbol is None
    assert entry.gate_status == "candidate"
    assert entry.report_reference == "reports/close_momentum.json"
    assert entry.gate_metadata == {
        "status": "candidate",
        "failure_reasons": [],
        "strong_failure_reasons": ["low_strong_test_sharpe"],
        "ic_same_sign_rate": 1.0,
        "mean_rank_ic": 1.0,
        "abs_mean_rank_ic": 1.0,
        "test_sharpe": 0.9,
    }

    stored = load_candidate_factor_library(library_path)
    assert stored["artifact_type"] == "candidate_factor_library"
    assert stored["live_strategy"] is False
    assert stored["entries"][0]["factor_callable_reference"] == "tests.factors.close_momentum"
    assert stored["entries"][0]["report_reference"] == "reports/close_momentum.json"
    assert stored["entries"][0]["gate_status"] == "candidate"
    assert stored["entries"][0]["feature_data_dependencies"] == ["binance_spot_1m_ohlcv"]
    assert stored["entries"][0]["pnl_data_dependencies"] == ["binance_spot_1m_ohlcv"]
    assert stored["entries"][0]["live_strategy"] is False
    assert "live strategy" not in json.dumps(stored).lower()


def test_candidate_factor_library_marks_strong_gate_pass_distinctly(tmp_path):
    library_path = tmp_path / "candidate_factors.json"

    entry = append_candidate_factor_library_entry(
        library_path=library_path,
        factor_callable_reference="tests.factors.close_momentum",
        report_reference="reports/close_momentum.json",
        report=_report(gate_status="strong"),
        gate_result=_gate_result(status="strong", test_sharpe=1.3),
    )

    assert entry is not None
    assert entry.gate_status == "strong"
    assert load_candidate_factor_library(library_path)["entries"][0]["gate_status"] == "strong"


def test_candidate_factor_library_rejects_rejected_gate_results(tmp_path):
    library_path = tmp_path / "candidate_factors.json"

    with pytest.raises(ValueError, match="rejected factors cannot be stored"):
        append_candidate_factor_library_entry(
            library_path=library_path,
            factor_callable_reference="tests.factors.close_momentum",
            report_reference="reports/close_momentum.json",
            report=_report(gate_status="rejected"),
            gate_result=_gate_result(status="rejected", test_sharpe=0.2),
        )

    assert load_candidate_factor_library(library_path)["entries"] == []


def _report(gate_status: str) -> FactorEvaluationReport:
    return FactorEvaluationReport(
        factor_name="close_momentum",
        symbol=None,
        feature_data_dependencies=["binance_spot_1m_ohlcv"],
        pnl_data_dependencies=["binance_spot_1m_ohlcv"],
        walk_forward_windows=[],
        cost_summary={},
        risk_summary={},
        ic_stability={},
        grouped_returns=[],
        gate_outcome={"status": gate_status},
        limitations=[],
        live_strategy=False,
        summary="Research artifact for audited factor evaluation.",
    )


def _gate_result(status: str, test_sharpe: float) -> FactorGateResult:
    return FactorGateResult(
        status=status,
        failure_reasons=[] if status != "rejected" else ["low_test_sharpe"],
        strong_failure_reasons=[] if status == "strong" else ["low_strong_test_sharpe"],
        ic_same_sign_rate=1.0,
        mean_rank_ic=1.0,
        abs_mean_rank_ic=1.0,
        test_sharpe=test_sharpe,
    )
