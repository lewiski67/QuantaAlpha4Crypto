from __future__ import annotations

import json
import re
from hashlib import sha1
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from quantaalpha_crypto.evaluation.factor import FactorCallable, evaluate_directional_factor
from quantaalpha_crypto.evaluation.gates import evaluate_factor_gates
from quantaalpha_crypto.evaluation.grid import EvaluationGridItem, PnlPanelInput
from quantaalpha_crypto.evaluation.library import append_candidate_factor_library_entry
from quantaalpha_crypto.evaluation.panel import CryptoPanel
from quantaalpha_crypto.evaluation.report import FactorEvaluationReport, build_factor_evaluation_report
from quantaalpha_crypto.evaluation.walk_forward import (
    build_walk_forward_windows,
    evaluate_walk_forward,
)
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
    pnl_panel: PnlPanelInput,
    factors: list[SuppliedFactorCallable],
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
    progress_callback: Callable[[str], None] | None = None,
) -> BatchFactorRunResult:
    """Evaluate supplied Directional Factors through the crypto evaluation core."""
    results = []
    evaluation_grid = _grid_with_timing(
        evaluation_grid,
        update_frequency=update_frequency,
        rebalance_frequency=rebalance_frequency,
    )
    start, end = _panel_time_bounds(feature_panel)
    windows = build_walk_forward_windows(
        start=start,
        end=end,
        train_window=walk_forward_settings["train_window"],
        validation_window=walk_forward_settings["validation_window"],
        test_window=walk_forward_settings["test_window"],
        step=walk_forward_settings["step"],
    )

    for factor_name, factor_reference, factor in factors:
        for symbol in _panel_symbols(feature_panel):
            _progress(progress_callback, f"factor_start {factor_name} symbol={symbol}")
            factor_started_at = perf_counter()
            timing: dict[str, float] = {}
            symbol_feature_panel = _slice_crypto_panel(feature_panel, symbol)
            symbol_pnl_panel = _slice_pnl_panel(pnl_panel, symbol)
            try:
                stage_started_at = perf_counter()
                factor_evaluation = evaluate_directional_factor(
                    symbol_feature_panel,
                    factor,
                    horizon=candidate_horizon,
                    input_lookback_window=input_lookback_window,
                )
                timing["factor_execution_seconds"] = _elapsed_seconds(stage_started_at)
                _progress(progress_callback, f"factor_execution_done {factor_name} symbol={symbol} {timing['factor_execution_seconds']}s")
                stage_started_at = perf_counter()
                _progress(progress_callback, f"walk_forward_start {factor_name} symbol={symbol}")
                walk_forward_result = evaluate_walk_forward(
                    factor_evaluation=factor_evaluation,
                    pnl_panel=symbol_pnl_panel,
                    grid=evaluation_grid,
                    windows=windows,
                    fee_rate=fee_rate,
                    cost_source=cost_source,
                )
                timing["walk_forward_evaluation_seconds"] = _elapsed_seconds(stage_started_at)
                _progress(progress_callback, f"walk_forward_done {factor_name} symbol={symbol} {timing['walk_forward_evaluation_seconds']}s")
                stage_started_at = perf_counter()
                gate_result = evaluate_factor_gates(
                    factor_evaluation=factor_evaluation,
                    walk_forward_result=walk_forward_result,
                )
                report = build_factor_evaluation_report(
                    factor_name=factor_name,
                    factor_evaluation=factor_evaluation,
                    walk_forward_result=walk_forward_result,
                    gate_result=gate_result,
                    feature_data_dependencies=feature_data_dependencies,
                    pnl_data_dependencies=pnl_data_dependencies,
                    symbol=symbol,
                )
                report_reference = _artifact_reference(workspace, "reports", f"{factor_name}__{symbol}")
                _write_report(workspace.root / report_reference, report)
                timing["report_and_library_seconds"] = _elapsed_seconds(stage_started_at)
            except Exception as error:
                timing["total_seconds"] = _elapsed_seconds(factor_started_at)
                _progress(progress_callback, f"factor_failed {factor_name} symbol={symbol} {type(error).__name__}")
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

            library_entry_stored = False
            if gate_result.status != "rejected":
                stage_started_at = perf_counter()
                append_candidate_factor_library_entry(
                    library_path=workspace.candidate_library_path,
                    factor_callable_reference=factor_reference,
                    report_reference=report_reference,
                    report=report,
                    gate_result=gate_result,
                    candidate_horizons=[candidate_horizon],
                    evaluation_grid=evaluation_grid,
                    walk_forward_settings=walk_forward_settings,
                )
                timing["report_and_library_seconds"] += _elapsed_seconds(stage_started_at)
                library_entry_stored = True

            timing["total_seconds"] = _elapsed_seconds(factor_started_at)
            _progress(progress_callback, f"factor_done {factor_name} symbol={symbol} {gate_result.status} {timing['total_seconds']}s")
            results.append(
                BatchFactorResult(
                    factor_name=factor_name,
                    factor_callable_reference=factor_reference,
                    report_reference=report_reference,
                    gate_status=gate_result.status,
                    failure_reasons=list(gate_result.failure_reasons),
                    library_entry_stored=library_entry_stored,
                    symbol=symbol,
                    diagnostic_reference=None,
                    timing=timing,
                )
            )

    return BatchFactorRunResult(factors=results)


def _grid_with_timing(
    evaluation_grid: list[EvaluationGridItem],
    update_frequency: str | None,
    rebalance_frequency: str | None,
) -> list[EvaluationGridItem]:
    timed_grid = []
    for item in evaluation_grid:
        timed_item: EvaluationGridItem = dict(item)
        if update_frequency is not None and "update_frequency" not in timed_item:
            timed_item["update_frequency"] = update_frequency
        if rebalance_frequency is not None and "rebalance_frequency" not in timed_item:
            timed_item["rebalance_frequency"] = rebalance_frequency
        timed_grid.append(timed_item)
    return timed_grid


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


def _slice_pnl_panel(pnl_panel: PnlPanelInput, symbol: str) -> PnlPanelInput:
    if isinstance(pnl_panel, CryptoPanel):
        return _slice_crypto_panel(pnl_panel, symbol)
    return {
        product: _slice_crypto_panel(product_panel, symbol)
        for product, product_panel in pnl_panel.items()
    }


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


def _write_report(path: Path, report: FactorEvaluationReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(asdict(report), file, indent=2, sort_keys=True)
        file.write("\n")


def _write_diagnostic(path: Path, diagnostic: RejectedFactorDiagnostic) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(asdict(diagnostic), file, indent=2, sort_keys=True)
        file.write("\n")


def _elapsed_seconds(started_at: float) -> float:
    return round(perf_counter() - started_at, 6)
