from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quantaalpha_crypto.evaluation.grid import EvaluationGridItem, PnlPanelInput
from quantaalpha_crypto.evaluation.panel import CryptoPanel
from quantaalpha_crypto.mining.batch_runner import (
    BatchFactorResult,
    BatchFactorRunResult,
    RejectedFactorDiagnostic,
    run_supplied_factor_callables,
)
from quantaalpha_crypto.mining.workspace import CryptoFactorWorkspace


@dataclass(frozen=True)
class CryptoFactorSource:
    factor_name: str
    factor_callable_reference: str
    source_code: str


def run_crypto_factor_sources(
    workspace: CryptoFactorWorkspace,
    feature_panel: CryptoPanel,
    pnl_panel: PnlPanelInput,
    factor_sources: list[CryptoFactorSource],
    candidate_horizon: str,
    evaluation_grid: list[EvaluationGridItem],
    walk_forward_settings: dict[str, Any],
    feature_data_dependencies: list[str],
    pnl_data_dependencies: list[str],
    input_lookback_window: str | None = None,
) -> BatchFactorRunResult:
    """Compile crypto factor sources and evaluate them through the Crypto Evaluation Core."""
    results: list[BatchFactorResult] = []
    for source in factor_sources:
        try:
            factor = _compile_factor_callable(source.source_code)
        except Exception as error:
            results.append(_write_source_diagnostic(workspace, source, error))
            continue

        run_result = run_supplied_factor_callables(
            workspace=workspace,
            feature_panel=feature_panel,
            pnl_panel=pnl_panel,
            factors=[(source.factor_name, source.factor_callable_reference, factor)],
            candidate_horizon=candidate_horizon,
            evaluation_grid=evaluation_grid,
            walk_forward_settings=walk_forward_settings,
            feature_data_dependencies=feature_data_dependencies,
            pnl_data_dependencies=pnl_data_dependencies,
            input_lookback_window=input_lookback_window,
        )
        results.extend(run_result.factors)

    return BatchFactorRunResult(factors=results)


def _compile_factor_callable(source_code: str):
    namespace: dict[str, Any] = {
        "__builtins__": {
            "abs": abs,
            "bool": bool,
            "float": float,
            "int": int,
            "len": len,
            "max": max,
            "min": min,
            "pow": pow,
            "range": range,
            "sum": sum,
            "Exception": Exception,
            "RuntimeError": RuntimeError,
            "ValueError": ValueError,
        },
        "np": np,
        "pd": pd,
    }
    exec(compile(source_code, "<crypto_factor_source>", "exec"), namespace)  # noqa: S102
    factor = namespace.get("factor")
    if not callable(factor):
        raise ValueError("factor source must define callable function `factor(data)`.")
    return factor


def _write_source_diagnostic(
    workspace: CryptoFactorWorkspace,
    source: CryptoFactorSource,
    error: Exception,
) -> BatchFactorResult:
    diagnostic_reference = _artifact_reference(workspace, "rejected", source.factor_name)
    _write_diagnostic(
        workspace.root / diagnostic_reference,
        RejectedFactorDiagnostic(
            artifact_type="rejected_factor_diagnostic",
            factor_name=source.factor_name,
            factor_callable_reference=source.factor_callable_reference,
            error_type=type(error).__name__,
            error_message=str(error),
            artifact_path=diagnostic_reference,
            live_strategy=False,
        ),
    )
    return BatchFactorResult(
        factor_name=source.factor_name,
        factor_callable_reference=source.factor_callable_reference,
        report_reference=None,
        gate_status="execution_failed",
        failure_reasons=["factor_execution_failed"],
        library_entry_stored=False,
        diagnostic_reference=diagnostic_reference,
    )


def _artifact_reference(workspace: CryptoFactorWorkspace, directory: str, factor_name: str) -> str:
    artifact_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", factor_name).strip("._-")
    if not artifact_stem:
        artifact_stem = "factor"
    if artifact_stem != factor_name:
        artifact_stem = f"{artifact_stem}_{sha1(factor_name.encode('utf-8')).hexdigest()[:8]}"
    reference = f"{directory}/{artifact_stem}.json"
    suffix = 2
    while (workspace.root / reference).exists():
        reference = f"{directory}/{artifact_stem}_{suffix}.json"
        suffix += 1
    return reference


def _write_diagnostic(path: Path, diagnostic: RejectedFactorDiagnostic) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(diagnostic.__dict__, file, indent=2, sort_keys=True)
        file.write("\n")
