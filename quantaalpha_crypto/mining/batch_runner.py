from __future__ import annotations

import json
import re
from hashlib import sha1
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from quantaalpha_crypto.evaluation.factor import FactorCallable, evaluate_directional_factor
from quantaalpha_crypto.evaluation.panel import CryptoPanel
from quantaalpha_crypto.mining._utils import _progress
from quantaalpha_crypto.mining.workspace import CryptoFactorWorkspace


SuppliedFactorCallable = tuple[str, str, FactorCallable]


@dataclass(frozen=True)
class BatchFactorResult:
    factor_name: str
    factor_callable_reference: str
    report_reference: str | None
    gate_status: str
    failure_reasons: list[str]
    library_entry_stored: bool
    symbol: str | None = None
    diagnostic_reference: str | None = None
    timing: dict[str, float] | None = None


@dataclass(frozen=True)
class BatchFactorRunResult:
    factors: list[BatchFactorResult]


@dataclass(frozen=True)
class RejectedFactorDiagnostic:
    artifact_type: str
    factor_name: str
    factor_callable_reference: str
    error_type: str
    error_message: str
    artifact_path: str
    live_strategy: bool


def run_supplied_factor_callables(
    workspace: CryptoFactorWorkspace,
    feature_panel: CryptoPanel,
    factors: list[SuppliedFactorCallable],
    candidate_horizon: str,
    feature_data_dependencies: list[str],
    pnl_data_dependencies: list[str],
    input_lookback_window: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> BatchFactorRunResult:
    """Evaluate supplied Directional Factors through the crypto evaluation core."""
    results = []

    for factor_name, factor_reference, factor in factors:
        for symbol in _panel_symbols(feature_panel):
            _progress(progress_callback, f"factor_start {factor_name} symbol={symbol}")
            factor_started_at = perf_counter()
            timing: dict[str, float] = {}
            symbol_feature_panel = _slice_crypto_panel(feature_panel, symbol)
            try:
                stage_started_at = perf_counter()
                factor_evaluation = evaluate_directional_factor(
                    symbol_feature_panel,
                    factor,
                    horizon=candidate_horizon,
                    input_lookback_window=input_lookback_window,
                )
                timing["factor_execution_seconds"] = _elapsed_seconds(stage_started_at)
                _progress(
                    progress_callback,
                    f"factor_execution_done {factor_name} symbol={symbol} {timing['factor_execution_seconds']}s",
                )
                stage_started_at = perf_counter()
                report_reference = _artifact_reference(workspace, "reports", f"{factor_name}__{symbol}")
                _write_report(
                    workspace.root / report_reference,
                    {
                        "artifact_type": "factor_evaluation_report",
                        "factor_name": factor_name,
                        "symbol": symbol,
                        "horizon": str(factor_evaluation.horizon),
                        "ic": float(factor_evaluation.ic),
                        "rank_ic": float(factor_evaluation.rank_ic),
                        "feature_data_dependencies": list(feature_data_dependencies),
                        "pnl_data_dependencies": list(pnl_data_dependencies),
                        "gate_outcome": {"status": "candidate"},
                        "live_strategy": False,
                    },
                )
                timing["report_and_library_seconds"] = _elapsed_seconds(stage_started_at)
            except Exception as error:
                timing["total_seconds"] = _elapsed_seconds(factor_started_at)
                _progress(
                    progress_callback,
                    f"factor_failed {factor_name} symbol={symbol} {type(error).__name__}",
                )
                diagnostic_reference = _artifact_reference(workspace, "rejected", f"{factor_name}__{symbol}")
                _write_diagnostic(
                    workspace.root / diagnostic_reference,
                    RejectedFactorDiagnostic(
                        artifact_type="rejected_factor_diagnostic",
                        factor_name=factor_name,
                        factor_callable_reference=factor_reference,
                        error_type=type(error).__name__,
                        error_message=str(error),
                        artifact_path=diagnostic_reference,
                        live_strategy=False,
                    ),
                )
                results.append(
                    BatchFactorResult(
                        factor_name=factor_name,
                        factor_callable_reference=factor_reference,
                        report_reference=None,
                        gate_status="execution_failed",
                        failure_reasons=["factor_execution_failed"],
                        library_entry_stored=False,
                        symbol=symbol,
                        diagnostic_reference=diagnostic_reference,
                        timing=timing,
                    )
                )
                continue

            timing["total_seconds"] = _elapsed_seconds(factor_started_at)
            _progress(
                progress_callback,
                f"factor_done {factor_name} symbol={symbol} candidate {timing['total_seconds']}s",
            )
            results.append(
                BatchFactorResult(
                    factor_name=factor_name,
                    factor_callable_reference=factor_reference,
                    report_reference=report_reference,
                    gate_status="candidate",
                    failure_reasons=[],
                    library_entry_stored=False,
                    symbol=symbol,
                    diagnostic_reference=None,
                    timing=timing,
                )
            )

    return BatchFactorRunResult(factors=results)


def _panel_time_bounds(panel: CryptoPanel) -> tuple[Any, Any]:
    timestamps = panel.data.index.get_level_values("timestamp")
    return timestamps.min(), timestamps.max()


def _panel_symbols(panel: CryptoPanel) -> list[str]:
    symbols = panel.data.index.get_level_values("symbol").unique()
    return [str(symbol) for symbol in sorted(symbols)]


def _slice_crypto_panel(panel: CryptoPanel, symbol: str) -> CryptoPanel:
    symbols = panel.data.index.get_level_values("symbol")
    data = panel.data[symbols == symbol]
    return CryptoPanel(
        data=data,
        data_role=panel.data_role,
        data_product=panel.data_product,
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


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, sort_keys=True)
        file.write("\n")


def _write_diagnostic(path: Path, diagnostic: RejectedFactorDiagnostic) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(diagnostic.__dict__, file, indent=2, sort_keys=True)
        file.write("\n")


def _elapsed_seconds(started_at: float) -> float:
    return round(perf_counter() - started_at, 6)
