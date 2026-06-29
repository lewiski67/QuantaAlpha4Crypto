from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from hashlib import sha1
from typing import Any, Callable, Protocol

from quantaalpha_crypto.evaluation.factor import FactorCallable
from quantaalpha_crypto.evaluation.grid import EvaluationGridItem, PnlPanelInput
from quantaalpha_crypto.evaluation.panel import CryptoPanel
from quantaalpha_crypto.mining.batch_runner import (
    BatchFactorResult,
    BatchFactorRunResult,
    run_supplied_factor_callables,
)
from quantaalpha_crypto.mining.workspace import CryptoFactorWorkspace


@dataclass(frozen=True)
class FactorProposalCandidate:
    factor_name: str
    factor_callable_reference: str
    factor_callable: FactorCallable
    source_code: str | None = None


@dataclass(frozen=True)
class FactorProposalContext:
    run_id: str
    candidate_horizon: str
    evaluation_grid: list[EvaluationGridItem]
    walk_forward_settings: dict[str, Any]
    feature_data_dependencies: list[str]
    pnl_data_dependencies: list[str]
    input_lookback_window: str | None = None
    update_frequency: str | None = None
    rebalance_frequency: str | None = None
    research_direction: str | None = None
    available_columns: list[str] | None = None
    previous_round_feedback: dict[str, Any] | None = None


@dataclass(frozen=True)
class FactorProposalResult:
    provider_name: str
    prompt_context: dict[str, Any]
    candidates: list[FactorProposalCandidate]
    raw_response: str | dict[str, Any] | None = None
    parsed_response: dict[str, Any] | None = None


class FactorProposalProvider(Protocol):
    def propose(self, context: FactorProposalContext) -> FactorProposalResult: ...


@dataclass(frozen=True)
class FactorRepairContext:
    run_id: str
    original_candidate: FactorProposalCandidate
    diagnostic_reference: str
    diagnostic: dict[str, Any]
    attempt_number: int
    max_attempts: int
    candidate_horizon: str
    evaluation_grid: list[EvaluationGridItem]
    walk_forward_settings: dict[str, Any]
    feature_data_dependencies: list[str]
    pnl_data_dependencies: list[str]
    input_lookback_window: str | None = None
    update_frequency: str | None = None
    rebalance_frequency: str | None = None
    research_direction: str | None = None
    available_columns: list[str] | None = None
    previous_round_feedback: dict[str, Any] | None = None


@dataclass(frozen=True)
class FactorRepairResult:
    provider_name: str
    prompt_context: dict[str, Any]
    repaired_candidate: FactorProposalCandidate | None
    raw_response: str | dict[str, Any] | None = None
    parsed_response: dict[str, Any] | None = None


class FactorRepairProvider(Protocol):
    def repair(self, context: FactorRepairContext) -> FactorRepairResult: ...


def run_factor_proposal_provider(
    workspace: CryptoFactorWorkspace,
    provider: FactorProposalProvider,
    feature_panel: CryptoPanel,
    pnl_panel: PnlPanelInput,
    candidate_horizon: str,
    evaluation_grid: list[EvaluationGridItem],
    walk_forward_settings: dict[str, Any],
    feature_data_dependencies: list[str],
    pnl_data_dependencies: list[str],
    input_lookback_window: str | None = None,
    update_frequency: str | None = None,
    rebalance_frequency: str | None = None,
    fee_rate: float = 0.0,
    cost_source: str = "fallback",
    research_direction: str | None = None,
    previous_round_feedback: dict[str, Any] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> BatchFactorRunResult:
    """Generate candidates from a provider and evaluate them through the crypto gates."""
    context = FactorProposalContext(
        run_id=workspace.root.name,
        candidate_horizon=candidate_horizon,
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
        feature_data_dependencies=feature_data_dependencies,
        pnl_data_dependencies=pnl_data_dependencies,
        input_lookback_window=input_lookback_window,
        update_frequency=update_frequency,
        rebalance_frequency=rebalance_frequency,
        research_direction=research_direction,
        available_columns=list(feature_panel.data.columns),
        previous_round_feedback=_redact_secrets(previous_round_feedback),
    )
    try:
        _progress(progress_callback, "proposal_start")
        proposal = provider.propose(context)
    except Exception as error:
        _progress(progress_callback, f"proposal_failed {type(error).__name__}")
        return _provider_failure_result(workspace, provider, error)
    _progress(progress_callback, f"proposal_done {len(proposal.candidates)}")
    artifact_references = _persist_factor_artifacts(workspace, proposal, context)
    _record_proposal_run(workspace, proposal, context, artifact_references)

    return run_supplied_factor_callables(
        workspace=workspace,
        feature_panel=feature_panel,
        pnl_panel=pnl_panel,
        factors=[
            (candidate.factor_name, candidate.factor_callable_reference, candidate.factor_callable)
            for candidate in proposal.candidates
        ],
        candidate_horizon=candidate_horizon,
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
        feature_data_dependencies=feature_data_dependencies,
        pnl_data_dependencies=pnl_data_dependencies,
        input_lookback_window=input_lookback_window,
        update_frequency=update_frequency,
        rebalance_frequency=rebalance_frequency,
        fee_rate=fee_rate,
        cost_source=cost_source,
        progress_callback=progress_callback,
    )


def run_factor_proposal_provider_with_repair(
    workspace: CryptoFactorWorkspace,
    provider: FactorProposalProvider,
    repair_provider: FactorRepairProvider,
    max_repair_attempts: int,
    feature_panel: CryptoPanel,
    pnl_panel: PnlPanelInput,
    candidate_horizon: str,
    evaluation_grid: list[EvaluationGridItem],
    walk_forward_settings: dict[str, Any],
    feature_data_dependencies: list[str],
    pnl_data_dependencies: list[str],
    input_lookback_window: str | None = None,
    update_frequency: str | None = None,
    rebalance_frequency: str | None = None,
    fee_rate: float = 0.0,
    cost_source: str = "fallback",
    research_direction: str | None = None,
    previous_round_feedback: dict[str, Any] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> BatchFactorRunResult:
    """Generate candidates, repair execution failures, and evaluate all attempts through gates."""
    if max_repair_attempts < 0:
        raise ValueError("max_repair_attempts must be non-negative.")

    context = FactorProposalContext(
        run_id=workspace.root.name,
        candidate_horizon=candidate_horizon,
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
        feature_data_dependencies=feature_data_dependencies,
        pnl_data_dependencies=pnl_data_dependencies,
        input_lookback_window=input_lookback_window,
        update_frequency=update_frequency,
        rebalance_frequency=rebalance_frequency,
        research_direction=research_direction,
        available_columns=list(feature_panel.data.columns),
        previous_round_feedback=_redact_secrets(previous_round_feedback),
    )
    try:
        _progress(progress_callback, "proposal_start")
        proposal = provider.propose(context)
    except Exception as error:
        _progress(progress_callback, f"proposal_failed {type(error).__name__}")
        return _provider_failure_result(workspace, provider, error)
    _progress(progress_callback, f"proposal_done {len(proposal.candidates)}")
    artifact_references = _persist_factor_artifacts(workspace, proposal, context)
    _record_proposal_run(workspace, proposal, context, artifact_references)

    results: list[BatchFactorResult] = []
    for candidate in proposal.candidates:
        current_candidate = candidate
        for attempt_number in range(max_repair_attempts + 1):
            _progress(progress_callback, f"candidate_evaluation_start {current_candidate.factor_name} attempt={attempt_number}")
            run_result = run_supplied_factor_callables(
                workspace=workspace,
                feature_panel=feature_panel,
                pnl_panel=pnl_panel,
                factors=[
                    (
                        current_candidate.factor_name,
                        current_candidate.factor_callable_reference,
                        current_candidate.factor_callable,
                    )
                ],
                candidate_horizon=candidate_horizon,
                evaluation_grid=evaluation_grid,
                walk_forward_settings=walk_forward_settings,
                feature_data_dependencies=feature_data_dependencies,
                pnl_data_dependencies=pnl_data_dependencies,
                input_lookback_window=input_lookback_window,
                update_frequency=update_frequency,
                rebalance_frequency=rebalance_frequency,
                fee_rate=fee_rate,
                cost_source=cost_source,
                progress_callback=progress_callback,
            )
            results.extend(run_result.factors)
            failed_result = next(
                (
                    result
                    for result in run_result.factors
                    if result.gate_status == "execution_failed"
                    and result.diagnostic_reference is not None
                ),
                None,
            )
            _progress(progress_callback, f"candidate_evaluation_done {current_candidate.factor_name}")
            if failed_result is None:
                break
            if attempt_number == max_repair_attempts:
                break

            diagnostic = _read_diagnostic(workspace, failed_result.diagnostic_reference)
            _progress(progress_callback, f"repair_start {current_candidate.factor_name} attempt={attempt_number + 1}")
            repair_result = repair_provider.repair(
                FactorRepairContext(
                    run_id=workspace.root.name,
                    original_candidate=current_candidate,
                    diagnostic_reference=failed_result.diagnostic_reference,
                    diagnostic=diagnostic,
                    attempt_number=attempt_number + 1,
                    max_attempts=max_repair_attempts,
                    candidate_horizon=candidate_horizon,
                    evaluation_grid=evaluation_grid,
                    walk_forward_settings=walk_forward_settings,
                    feature_data_dependencies=feature_data_dependencies,
                    pnl_data_dependencies=pnl_data_dependencies,
                    input_lookback_window=input_lookback_window,
                    update_frequency=update_frequency,
                    rebalance_frequency=rebalance_frequency,
                    research_direction=research_direction,
                    available_columns=list(feature_panel.data.columns),
                    previous_round_feedback=_redact_secrets(previous_round_feedback),
                )
            )
            _progress(
                progress_callback,
                f"repair_done {current_candidate.factor_name} {'repaired' if repair_result.repaired_candidate is not None else 'unrepaired'}",
            )
            repair_artifact_references = _persist_factor_artifacts(
                workspace,
                repair_result,
                context,
            )
            _record_repair_attempt(
                workspace=workspace,
                repair_result=repair_result,
                diagnostic_reference=failed_result.diagnostic_reference,
                attempt_number=attempt_number + 1,
                artifact_references=repair_artifact_references,
            )
            if repair_result.repaired_candidate is None:
                break
            current_candidate = repair_result.repaired_candidate

    return BatchFactorRunResult(factors=results)


def _progress(progress_callback: Callable[[str], None] | None, message: str) -> None:
    if progress_callback is not None:
        progress_callback(message)


def _record_proposal_run(
    workspace: CryptoFactorWorkspace,
    proposal: FactorProposalResult,
    context: FactorProposalContext,
    artifact_references: dict[int, str],
) -> None:
    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("proposal_runs", []).append(
        {
            "artifact_type": "factor_proposal_metadata",
            "provider_name": proposal.provider_name,
            "prompt_context": _redact_secrets(dict(proposal.prompt_context)),
            "context": _redact_secrets(asdict(context)),
            "candidate_count": len(proposal.candidates),
            "candidates": [
                _candidate_manifest_entry(candidate, artifact_references)
                for candidate in proposal.candidates
            ],
            "live_strategy": False,
        }
    )
    with workspace.manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, sort_keys=True)
        file.write("\n")


def _record_repair_attempt(
    workspace: CryptoFactorWorkspace,
    repair_result: FactorRepairResult,
    diagnostic_reference: str,
    attempt_number: int,
    artifact_references: dict[int, str],
) -> None:
    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    repair_runs = manifest.setdefault("repair_runs", [])
    if not repair_runs:
        repair_runs.append(
            {
                "artifact_type": "factor_repair_metadata",
                "attempts": [],
                "live_strategy": False,
            }
        )
    repaired_candidate = repair_result.repaired_candidate
    repair_runs[-1]["attempts"].append(
        {
            "provider_name": repair_result.provider_name,
            "prompt_context": _redact_secrets(dict(repair_result.prompt_context)),
            "attempt_number": attempt_number,
            "diagnostic_reference": diagnostic_reference,
            "status": "repaired" if repaired_candidate is not None else "unrepaired",
            "repaired_candidate": (
                _candidate_manifest_entry(repaired_candidate, artifact_references)
                if repaired_candidate is not None
                else None
            ),
            "live_strategy": False,
        }
    )
    with workspace.manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, sort_keys=True)
        file.write("\n")


def _read_diagnostic(workspace: CryptoFactorWorkspace, diagnostic_reference: str) -> dict[str, Any]:
    return json.loads((workspace.root / diagnostic_reference).read_text(encoding="utf-8"))


def _candidate_manifest_entry(
    candidate: FactorProposalCandidate,
    artifact_references: dict[int, str],
) -> dict[str, Any]:
    entry = {
        "factor_name": candidate.factor_name,
        "factor_callable_reference": candidate.factor_callable_reference,
    }
    artifact_reference = artifact_references.get(id(candidate))
    if artifact_reference is not None:
        entry["factor_artifact_reference"] = artifact_reference
    return entry


def _provider_failure_result(
    workspace: CryptoFactorWorkspace,
    provider: FactorProposalProvider,
    error: Exception,
) -> BatchFactorRunResult:
    diagnostic_reference = _rejected_reference(workspace, "provider_proposal")
    diagnostic = {
        "artifact_type": "rejected_factor_diagnostic",
        "factor_name": "provider_proposal",
        "factor_callable_reference": type(provider).__name__,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "artifact_path": diagnostic_reference,
        "live_strategy": False,
    }
    with (workspace.root / diagnostic_reference).open("w", encoding="utf-8") as file:
        json.dump(diagnostic, file, indent=2, sort_keys=True)
        file.write("\n")
    return BatchFactorRunResult(
        factors=[
            BatchFactorResult(
                factor_name="provider_proposal",
                factor_callable_reference=type(provider).__name__,
                report_reference=None,
                gate_status="execution_failed",
                failure_reasons=["factor_proposal_failed"],
                library_entry_stored=False,
                diagnostic_reference=diagnostic_reference,
            )
        ]
    )


def _persist_factor_artifacts(
    workspace: CryptoFactorWorkspace,
    provider_result: FactorProposalResult | FactorRepairResult,
    context: FactorProposalContext | FactorRepairContext,
) -> dict[int, str]:
    references = {}
    candidates = (
        provider_result.candidates
        if isinstance(provider_result, FactorProposalResult)
        else (
            [provider_result.repaired_candidate]
            if provider_result.repaired_candidate is not None
            else []
        )
    )
    for candidate in candidates:
        if candidate.source_code is None and provider_result.raw_response is None and provider_result.parsed_response is None:
            continue
        reference = _artifact_reference(workspace, candidate.factor_name)
        source_code = candidate.source_code or ""
        payload = {
            "artifact_type": "llm_factor_artifact",
            "provider_name": provider_result.provider_name,
            "model": _redact_secrets(provider_result.prompt_context.get("model")),
            "prompt_context": _redact_secrets(dict(provider_result.prompt_context)),
            "raw_response": _redact_secrets(provider_result.raw_response),
            "parsed_response": _redact_secrets(provider_result.parsed_response),
            "factor_name": candidate.factor_name,
            "factor_callable_reference": candidate.factor_callable_reference,
            "generated_source": candidate.source_code,
            "source_hash": sha1(source_code.encode("utf-8")).hexdigest(),
            "compile_status": "compiled" if candidate.source_code is not None else "not_recorded",
            "timing": {
                "input_lookback_window": context.input_lookback_window,
                "update_frequency": context.update_frequency,
                "rebalance_frequency": context.rebalance_frequency,
                "candidate_horizon": context.candidate_horizon,
            },
            "artifact_path": reference,
            "live_strategy": False,
        }
        with (workspace.root / reference).open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, sort_keys=True)
            file.write("\n")
        references[id(candidate)] = reference
    return references


def _redact_secrets(value: Any) -> Any:
    sensitive_key_pattern = re.compile(
        r"(api[_-]?key|secret|token|password|authorization)",
        re.IGNORECASE,
    )
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if sensitive_key_pattern.search(str(key))
                else _redact_secrets(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    if isinstance(value, str):
        return re.sub(
            r'(?i)("?(?:api[_-]?key|secret|token|password|authorization)"?\s*[:=]\s*)(".*?"|[^,\s}]+)',
            r"\1[REDACTED]",
            value,
        )
    return value


def _artifact_reference(workspace: CryptoFactorWorkspace, factor_name: str) -> str:
    artifact_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", factor_name).strip("._-")
    if not artifact_stem:
        artifact_stem = "factor"
    if artifact_stem != factor_name:
        artifact_stem = f"{artifact_stem}_{sha1(factor_name.encode('utf-8')).hexdigest()[:8]}"
    reference = f"factor_artifacts/{artifact_stem}.json"
    suffix = 2
    while (workspace.root / reference).exists():
        reference = f"factor_artifacts/{artifact_stem}_{suffix}.json"
        suffix += 1
    return reference


def _rejected_reference(workspace: CryptoFactorWorkspace, factor_name: str) -> str:
    artifact_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", factor_name).strip("._-") or "factor"
    reference = f"rejected/{artifact_stem}.json"
    suffix = 2
    while (workspace.root / reference).exists():
        reference = f"rejected/{artifact_stem}_{suffix}.json"
        suffix += 1
    return reference
