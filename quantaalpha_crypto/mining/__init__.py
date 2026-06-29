"""Crypto-native factor mining automation.

This module orchestrates mining runs around the evaluation core.
"""

from quantaalpha_crypto.mining.batch_runner import (
    BatchFactorResult,
    BatchFactorRunResult,
    RejectedFactorDiagnostic,
    run_supplied_factor_callables,
)
from quantaalpha_crypto.mining.llm_provider import (
    AnthropicCompletionClient,
    AnthropicCryptoFactorProposalProvider,
    AnthropicCryptoFactorRepairProvider,
    DEFAULT_ANTHROPIC_MODEL,
)
from quantaalpha_crypto.mining.config import (
    FactorTimingConfig,
    OriginalFlowCryptoMiningRunConfig,
    ProviderConfig,
    parse_original_flow_crypto_mining_run_config,
)
from quantaalpha_crypto.mining.proposal import (
    FactorProposalCandidate,
    FactorProposalContext,
    FactorProposalProvider,
    FactorProposalResult,
    FactorRepairContext,
    FactorRepairProvider,
    FactorRepairResult,
    run_factor_proposal_provider,
    run_factor_proposal_provider_with_repair,
)
from quantaalpha_crypto.mining.portfolio import write_portfolio_backtest_result
from quantaalpha_crypto.mining.round import (
    build_round_feedback_context,
    CryptoMiningRoundConfig,
    CryptoMiningRoundResult,
    run_local_crypto_mining_round,
)
from quantaalpha_crypto.mining.runner import (
    CryptoFactorSource,
    run_crypto_factor_sources,
)
from quantaalpha_crypto.mining.workspace import (
    CryptoFactorWorkspace,
    create_crypto_factor_workspace,
)

__all__ = [
    "BatchFactorResult",
    "BatchFactorRunResult",
    "AnthropicCompletionClient",
    "AnthropicCryptoFactorProposalProvider",
    "AnthropicCryptoFactorRepairProvider",
    "CryptoFactorWorkspace",
    "CryptoFactorSource",
    "CryptoMiningRoundConfig",
    "CryptoMiningRoundResult",
    "DEFAULT_ANTHROPIC_MODEL",
    "FactorProposalCandidate",
    "FactorProposalContext",
    "FactorProposalProvider",
    "FactorProposalResult",
    "FactorRepairContext",
    "FactorRepairProvider",
    "FactorRepairResult",
    "FactorTimingConfig",
    "OriginalFlowCryptoMiningRunConfig",
    "ProviderConfig",
    "RejectedFactorDiagnostic",
    "create_crypto_factor_workspace",
    "build_round_feedback_context",
    "run_factor_proposal_provider",
    "run_factor_proposal_provider_with_repair",
    "run_local_crypto_mining_round",
    "run_crypto_factor_sources",
    "run_supplied_factor_callables",
    "write_portfolio_backtest_result",
    "parse_original_flow_crypto_mining_run_config",
]
