"""Crypto-native factor evaluation core.

This module evaluates supplied Directional Factors. It does not generate
factors, call LLMs, or orchestrate mining rounds.
"""

from quantaalpha_crypto.evaluation.factor import FactorEvaluation, evaluate_directional_factor
from quantaalpha_crypto.evaluation.gates import FactorGateResult, evaluate_factor_gates
from quantaalpha_crypto.evaluation.grid import (
    EvaluationGridResult,
    EvaluationGridTrial,
    build_default_evaluation_grid,
    evaluate_fixed_grid,
)
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
from quantaalpha_crypto.evaluation.report import (
    FactorEvaluationReport,
    build_factor_evaluation_report,
)
from quantaalpha_crypto.evaluation.walk_forward import (
    WalkForwardValidationResult,
    WalkForwardWindow,
    WalkForwardWindowResult,
    build_walk_forward_windows,
    evaluate_walk_forward,
)

__all__ = [
    "CryptoPanel",
    "EvaluationGridResult",
    "EvaluationGridTrial",
    "FactorEvaluation",
    "FactorEvaluationReport",
    "FactorGateResult",
    "PortfolioBacktestConfig",
    "PortfolioBacktestResult",
    "portfolio_backtest_result_to_dict",
    "CandidateFactorLibraryEntry",
    "WalkForwardValidationResult",
    "WalkForwardWindow",
    "WalkForwardWindowResult",
    "build_default_evaluation_grid",
    "build_factor_evaluation_report",
    "build_crypto_panel",
    "build_walk_forward_windows",
    "evaluate_directional_factor",
    "evaluate_factor_gates",
    "evaluate_fixed_grid",
    "evaluate_walk_forward",
    "run_crypto_portfolio_backtest",
    "append_candidate_factor_library_entry",
    "load_candidate_factor_library",
]
