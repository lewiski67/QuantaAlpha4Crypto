from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from quantaalpha_crypto.evaluation.panel import CryptoPanel
from quantaalpha_crypto.mining._utils import _progress, _redact_secrets
from quantaalpha_crypto.mining.batch_runner import BatchFactorRunResult
from quantaalpha_crypto.mining.proposal import (
    FactorProposalProvider,
    FactorRepairProvider,
    run_factor_proposal_provider_with_repair,
)
from quantaalpha_crypto.mining.workspace import CryptoFactorWorkspace, create_crypto_factor_workspace


@dataclass(frozen=True)
class CryptoMiningRoundConfig:
    output_dir: str | Path
    run_id: str
    crypto_data_universe: dict[str, Any]
    candidate_horizon: str
    feature_data_dependencies: list[str]
    pnl_data_dependencies: list[str]
    max_repair_attempts: int
    input_lookback_window: str | None = None
    research_direction: str | None = None


@dataclass(frozen=True)
class CryptoMiningRoundResult:
    workspace: CryptoFactorWorkspace
    batch_result: BatchFactorRunResult


def run_local_crypto_mining_round(
    config: CryptoMiningRoundConfig,
    proposal_provider: FactorProposalProvider,
    repair_provider: FactorRepairProvider,
    feature_panel: CryptoPanel,
    previous_round_feedback: dict[str, Any] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> CryptoMiningRoundResult:
    """Run one deterministic local crypto mining round and write research artifacts."""
    workspace = create_crypto_factor_workspace(
        output_dir=config.output_dir,
        run_id=config.run_id,
        crypto_data_universe=config.crypto_data_universe,
    )
    _progress(progress_callback, f"workspace_created {workspace.root}")
    batch_result = run_factor_proposal_provider_with_repair(
        workspace=workspace,
        provider=proposal_provider,
        repair_provider=repair_provider,
        max_repair_attempts=config.max_repair_attempts,
        feature_panel=feature_panel,
        candidate_horizon=config.candidate_horizon,
        feature_data_dependencies=config.feature_data_dependencies,
        pnl_data_dependencies=config.pnl_data_dependencies,
        input_lookback_window=config.input_lookback_window,
        research_direction=config.research_direction,
        previous_round_feedback=previous_round_feedback,
        progress_callback=progress_callback,
    )
    _record_mining_round(workspace, batch_result)
    _progress(progress_callback, "mining_round_recorded")
    return CryptoMiningRoundResult(workspace=workspace, batch_result=batch_result)


def _record_mining_round(
    workspace: CryptoFactorWorkspace,
    batch_result: BatchFactorRunResult,
) -> None:
    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    factor_results = [
        {
            "factor_name": factor.factor_name,
            "symbol": factor.symbol,
            "factor_callable_reference": factor.factor_callable_reference,
            "gate_status": factor.gate_status,
            "failure_reasons": list(factor.failure_reasons),
            "report_reference": factor.report_reference,
            "diagnostic_reference": factor.diagnostic_reference,
            "library_entry_stored": factor.library_entry_stored,
            "timing": dict(factor.timing or {}),
        }
        for factor in batch_result.factors
    ]
    accepted_count = sum(1 for factor in batch_result.factors if factor.library_entry_stored)
    rejected_count = sum(1 for factor in batch_result.factors if factor.gate_status == "rejected")
    execution_failed_count = sum(
        1 for factor in batch_result.factors if factor.gate_status == "execution_failed"
    )
    manifest["mining_round"] = {
        "artifact_type": "local_crypto_mining_round",
        "status": "completed",
        "summary": "Research artifact for one local crypto factor mining round.",
        "workflow_steps": [
            "create_workspace",
            "propose_candidates",
            "evaluate_candidates",
            "repair_execution_failures",
            "write_reports_and_library",
        ],
        "result_counts": {
            "accepted": accepted_count,
            "execution_failed": execution_failed_count,
            "rejected": rejected_count,
            "total": len(batch_result.factors),
        },
        "timing": _batch_timing_summary(batch_result),
        "factor_results": factor_results,
        "live_strategy": False,
    }
    with workspace.manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, sort_keys=True)
        file.write("\n")


def _batch_timing_summary(batch_result: BatchFactorRunResult) -> dict[str, float]:
    totals: dict[str, float] = {}
    for factor in batch_result.factors:
        for name, value in (factor.timing or {}).items():
            totals[name] = totals.get(name, 0.0) + float(value)
    return {name: round(value, 6) for name, value in sorted(totals.items())}


def build_round_feedback_context(workspace: CryptoFactorWorkspace) -> dict[str, Any]:
    """Build secret-safe Mining Feedback for a later proposal round."""
    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    mining_round = manifest.get("mining_round", {})
    factor_results = mining_round.get("factor_results", [])
    feedback = {
        "artifact_type": "mining_feedback",
        "source_run_id": workspace.root.name,
        "result_counts": dict(mining_round.get("result_counts", {})),
        "lifecycle_counts": _lifecycle_counts(manifest),
        "accepted": [],
        "rejected": [],
        "execution_failed": [],
        "portfolio_backtests": [
            _portfolio_feedback_item(workspace, item)
            for item in manifest.get("portfolio_backtests", [])
        ],
        "live_strategy": False,
    }
    for result in factor_results:
        item = _factor_feedback_item(workspace, result)
        if result.get("library_entry_stored"):
            feedback["accepted"].append(item)
        elif result.get("gate_status") == "execution_failed":
            feedback["execution_failed"].append(item)
        else:
            feedback["rejected"].append(item)
    return _redact_secrets(feedback)


def _lifecycle_counts(manifest: dict[str, Any]) -> dict[str, int]:
    generated = sum(run.get("candidate_count", 0) for run in manifest.get("proposal_runs", []))
    repaired = sum(
        1
        for repair_run in manifest.get("repair_runs", [])
        for attempt in repair_run.get("attempts", [])
        if attempt.get("status") == "repaired"
    )
    unrepaired = sum(
        1
        for repair_run in manifest.get("repair_runs", [])
        for attempt in repair_run.get("attempts", [])
        if attempt.get("status") == "unrepaired"
    )
    return {"generated": generated, "repaired": repaired, "unrepaired": unrepaired}


def _factor_feedback_item(
    workspace: CryptoFactorWorkspace,
    result: dict[str, Any],
) -> dict[str, Any]:
    item = {
        "factor_name": result.get("factor_name"),
        "symbol": result.get("symbol"),
        "factor_callable_reference": result.get("factor_callable_reference"),
        "gate_status": result.get("gate_status"),
        "failure_reasons": list(result.get("failure_reasons", [])),
        "report_reference": result.get("report_reference"),
        "diagnostic_reference": result.get("diagnostic_reference"),
        "library_entry_stored": result.get("library_entry_stored", False),
    }
    report_reference = result.get("report_reference")
    if report_reference is not None:
        report = json.loads((workspace.root / report_reference).read_text(encoding="utf-8"))
        item["ic_metrics"] = {
            "ic": report.get("ic"),
            "rank_ic": report.get("rank_ic"),
            "horizon": report.get("horizon"),
        }
        item["gate_outcome"] = report.get("gate_outcome", {})
    diagnostic_reference = result.get("diagnostic_reference")
    if diagnostic_reference is not None:
        item["diagnostic"] = json.loads(
            (workspace.root / diagnostic_reference).read_text(encoding="utf-8")
        )
    return item


def _portfolio_feedback_item(
    workspace: CryptoFactorWorkspace,
    item: dict[str, Any],
) -> dict[str, Any]:
    reference = item.get("artifact_path")
    payload = {}
    if reference is not None:
        payload = json.loads((workspace.root / reference).read_text(encoding="utf-8"))
    return {
        "artifact_path": reference,
        "metrics": dict(item.get("metrics", {})),
        "timing": dict(item.get("timing", {})),
        "cost_breakdown": payload.get("cost_breakdown", {}),
        "live_strategy": False,
    }
