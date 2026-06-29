from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from quantaalpha_crypto.evaluation.gates import FactorGateResult
from quantaalpha_crypto.evaluation.report import FactorEvaluationReport


@dataclass(frozen=True)
class CandidateFactorLibraryEntry:
    factor_name: str
    symbol: str | None
    factor_callable_reference: str
    report_reference: str
    gate_status: str
    gate_metadata: dict[str, Any]
    feature_data_dependencies: list[str]
    pnl_data_dependencies: list[str]
    candidate_horizons: list[str]
    evaluation_grid: list[dict[str, Any]]
    walk_forward_settings: dict[str, Any]
    live_strategy: bool = False
    artifact_type: str = "candidate_factor_library_entry"


def append_candidate_factor_library_entry(
    library_path: str | Path,
    factor_callable_reference: str,
    report_reference: str,
    report: FactorEvaluationReport,
    gate_result: FactorGateResult,
    candidate_horizons: list[str],
    evaluation_grid: list[dict[str, Any]],
    walk_forward_settings: dict[str, Any],
) -> CandidateFactorLibraryEntry:
    """Append an accepted factor evaluation to the research Candidate Factor Library."""
    if gate_result.status == "rejected":
        raise ValueError("rejected factors cannot be stored as accepted library entries")
    if report.live_strategy:
        raise ValueError("Candidate Factor Library only stores research artifacts")

    entry = CandidateFactorLibraryEntry(
        factor_name=report.factor_name,
        symbol=report.symbol,
        factor_callable_reference=factor_callable_reference,
        report_reference=report_reference,
        gate_status=gate_result.status,
        gate_metadata=_gate_metadata(gate_result),
        feature_data_dependencies=list(report.feature_data_dependencies),
        pnl_data_dependencies=list(report.pnl_data_dependencies),
        candidate_horizons=list(candidate_horizons),
        evaluation_grid=list(evaluation_grid),
        walk_forward_settings=dict(walk_forward_settings),
    )

    library = load_candidate_factor_library(library_path)
    library["entries"].append(asdict(entry))
    _write_candidate_factor_library(library_path, library)
    return entry


def load_candidate_factor_library(library_path: str | Path) -> dict[str, Any]:
    path = Path(library_path)
    if not path.exists():
        return _empty_library()
    with path.open("r", encoding="utf-8") as file:
        library = json.load(file)
    if "entries" not in library:
        library["entries"] = []
    return library


def _write_candidate_factor_library(
    library_path: str | Path,
    library: dict[str, Any],
) -> None:
    path = Path(library_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(library, file, indent=2, sort_keys=True)
        file.write("\n")


def _empty_library() -> dict[str, Any]:
    return {
        "artifact_type": "candidate_factor_library",
        "live_strategy": False,
        "entries": [],
    }


def _gate_metadata(gate_result: FactorGateResult) -> dict[str, Any]:
    return {
        "status": gate_result.status,
        "failure_reasons": list(gate_result.failure_reasons),
        "strong_failure_reasons": list(gate_result.strong_failure_reasons),
        "ic_same_sign_rate": gate_result.ic_same_sign_rate,
        "mean_rank_ic": gate_result.mean_rank_ic,
        "abs_mean_rank_ic": gate_result.abs_mean_rank_ic,
        "test_sharpe": gate_result.test_sharpe,
    }
