from __future__ import annotations

from dataclasses import dataclass


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
