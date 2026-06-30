"""Crypto-native factor evaluation core.

This module evaluates supplied Directional Factors. It does not generate
factors, call LLMs, or orchestrate mining rounds.
"""

from quantaalpha_crypto.evaluation.factor import FactorEvaluation, evaluate_directional_factor
from quantaalpha_crypto.evaluation.gates import FactorGateResult, GateStatus
from quantaalpha_crypto.evaluation.library import (
    CandidateFactorLibraryEntry,
    append_candidate_factor_library_entry,
    load_candidate_factor_library,
)
from quantaalpha_crypto.evaluation.panel import CryptoPanel, build_crypto_panel
from quantaalpha_crypto.evaluation.portfolio import (
    PortfolioBacktestConfig,
    PortfolioBacktestResult,
    portfolio_backtest_result_to_dict,
    run_crypto_portfolio_backtest,
)
from quantaalpha_crypto.evaluation.report import FactorEvaluationReport
from quantaalpha_crypto.evaluation.walk_forward import (
    WalkForwardWindow,
    build_walk_forward_windows,
)

__all__ = [
    "CryptoPanel",
    "FactorEvaluation",
    "FactorEvaluationReport",
    "FactorGateResult",
    "GateStatus",
    "PortfolioBacktestConfig",
    "PortfolioBacktestResult",
    "portfolio_backtest_result_to_dict",
    "CandidateFactorLibraryEntry",
    "WalkForwardWindow",
    "append_candidate_factor_library_entry",
    "build_crypto_panel",
    "build_walk_forward_windows",
    "evaluate_directional_factor",
    "run_crypto_portfolio_backtest",
    "load_candidate_factor_library",
]
