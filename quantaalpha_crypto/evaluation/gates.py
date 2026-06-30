from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


GateStatus = Literal["rejected", "candidate", "strong"]


@dataclass(frozen=True)
class FactorGateResult:
    status: GateStatus
    failure_reasons: list[str]
    strong_failure_reasons: list[str]
    ic_same_sign_rate: float
    mean_rank_ic: float
    abs_mean_rank_ic: float
    test_sharpe: float
