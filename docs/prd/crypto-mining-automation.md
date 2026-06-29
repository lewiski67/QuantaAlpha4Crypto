# Crypto Mining Automation PRD

Date: 2026-06-24
Status: Local PRD

## Problem Statement

The Crypto Evaluation Core under `quantaalpha/crypto/evaluation/` can now evaluate a supplied Factor Callable end to end: it builds or receives a Crypto Panel, computes Forward Returns, searches a fixed Evaluation Grid, runs Walk-forward Validation, produces a Factor Evaluation Report, and stores Research Gate passes in the Candidate Factor Library.

This is not yet equivalent to the original QuantaAlpha factor mining workflow. The current system still needs a crypto-native mining loop that can generate, execute, evaluate, repair, and iterate over Directional Factors automatically while preserving the research/deployment boundary established by ADR-0010.

## Solution

Build a thin Crypto Mining Automation module under `quantaalpha/crypto/mining/` beside the existing Qlib-oriented pipeline. This automation layer should use the completed Crypto Evaluation Core as the acceptance boundary and should avoid rewriting the original QuantaAlpha pipeline until a narrow local loop works.

The original QuantaAlpha code is not only a reference archive. It should be treated as reusable project surface: when original modules can be reused directly, adapted in place, or migrated with a narrow Binance crypto trading change, prefer that over building a parallel implementation. New crypto-native code is justified when original Qlib/A-share/daily-frequency assumptions would distort Binance spot/perpetual data, intraday horizons, Binance costs, or the research/deployment boundary.

The migration strategy is Progressive In-place Replacement. The crypto module may exist as a temporary safety boundary while behavior is being proven, but the intended direction is to preserve the original architecture shape, CLI/UI surfaces, pipeline concepts, and reusable module names where practical, then replace their internals with crypto-correct implementations over time.

The loop will start from a mining run configuration, create a Crypto Factor Workspace, load or generate Factor Callables, evaluate each candidate through the completed Crypto Evaluation Core, write Factor Evaluation Reports, append Research Gate passes to the Candidate Factor Library, and preserve rejected factor diagnostics for later feedback.

The mining loop should use Research Gate results for library intake and next-round proposal feedback. Trading Gate results belong to formal backtest and portfolio selection; they may be reported as diagnostics, but they must not be the only first-stage condition for retaining a factor with gross signal.

The first version should support deterministic local tests without requiring live LLM or Binance network access. LLM proposal and repair should be behind small interfaces that can be exercised with fake providers in tests and later wired to `quantaalpha/llm/`.

## User Stories

1. As a quant researcher, I want a Crypto Factor Workspace, so that a mining run has reproducible inputs, outputs, reports, logs, and library updates.
2. As a quant researcher, I want a batch runner for Factor Callables, so that I can evaluate multiple hand-written or generated Directional Factors through the same completed Research Gate and Trading Gate interfaces.
3. As a quant researcher, I want failed Factor Callables to produce structured diagnostics, so that invalid ideas are auditable without corrupting the Candidate Factor Library.
4. As a quant researcher, I want an LLM proposal interface for crypto Directional Factors, so that factor generation can be automated without coupling the evaluator to one model provider.
5. As a quant researcher, I want a repair loop for generated Factor Callables, so that syntax, import, index, and runtime errors can be fed back into generation.
6. As a quant researcher, I want Research Gate passes to be automatically reported and stored, so that successful mining runs produce reusable research artifacts without claiming tradability.
7. As a quant researcher, I want rejected factors and Trading Gate failures to remain visible with gate reasons and error diagnostics, so that failure information can guide the next mining round.
8. As a maintainer, I want the Crypto Mining Automation module built beside the original Qlib pipeline, so that the original project remains usable while the crypto path matures.
9. As a maintainer, I want deterministic tests for the mining loop, so that CI does not depend on LLM calls, Binance network access, or large market datasets.
10. As a maintainer, I want run manifests, so that a mined Candidate Factor can be traced back to the Crypto Data Universe inputs, Evaluation Grid, Walk-forward Validation settings, prompts, generated code reference, and report.
11. As a Binance crypto operator, I want reusable original QuantaAlpha modules to be adapted or migrated instead of duplicated, so that the project converges toward one maintainable trading system rather than two unrelated implementations.

## Implementation Decisions

- The next phase will not replace the existing Qlib factor mining pipeline.
- The first automation layer will live in `quantaalpha/crypto/mining/` beside the existing Crypto Evaluation Core and call public `quantaalpha_crypto.evaluation` or top-level `quantaalpha_crypto` APIs.
- Prefer direct reuse, narrow modification, or migration of original QuantaAlpha modules when their assumptions match the Binance crypto trading path.
- Add new crypto-native implementation only where original Qlib/A-share/daily-frequency assumptions conflict with Binance spot/perpetual trading, intraday horizons, Binance costs, or audit requirements.
- Treat new crypto-native modules as proving grounds for later in-place replacement, not as a permanent second architecture.
- Preserve original entry points, pipeline concepts, and UI surfaces where practical while replacing their internals with Binance crypto trading behavior.
- A Crypto Factor Workspace will be the local run boundary for generated candidates, run manifests, reports, rejected diagnostics, and Candidate Factor Library updates.
- Factor Callables will initially be referenced by importable Python module path or explicitly supplied callable reference strings.
- Generated Factor Callables must still obey ADR-0008: `factor(panel) -> score Series[(timestamp, symbol)]`.
- Batch evaluation will treat each Directional Factor independently; cross-factor portfolio construction is out of scope for this phase.
- LLM generation and repair will use provider interfaces that can be faked in tests.
- The evaluator remains the authority for Research Gate and Trading Gate decisions. LLM self-rating must not bypass Walk-forward Validation, Binance Trading Cost diagnostics, Research Gate, or Trading Gate.
- The mining loop uses Research Gate for Candidate Factor Library intake. It should pass gross return, net return, cost drag, turnover, trade count, break-even fee, threshold, and horizon diagnostics into LLM feedback.
- Trading Gate is reserved for formal backtest and portfolio selection. A Trading Gate failure can guide LLM feedback, but it should not automatically delete a Research Gate pass from the research library.
- The mining loop will write auditable research artifacts, not live strategies.
- The original Qlib backtest system and surrounding pipeline may be used as architecture reference, direct reuse target, or migration source, but the crypto path must not force Crypto Panel data into Qlib daily equity assumptions.

## Testing Decisions

- Tests should cover public run-level behavior, not private prompt formatting.
- Tests should use small deterministic Crypto Panel fixtures.
- LLM proposal and repair tests should use fake providers.
- Batch evaluation tests should include at least one passing candidate, one rejected candidate, and one callable execution failure.
- Workspace tests should verify reports, manifests, rejected diagnostics, and Candidate Factor Library updates.
- Tests should prove rejected, failed, and Research Gate-failed factors are not stored as Candidate Factor Library entries.
- Tests should prove Trading Gate failures can still be reported for Research Gate passes without labeling them production-ready.
- Tests should verify that generated artifacts do not describe factors as live strategies.

## Out of Scope

- Live Binance order execution.
- Paper trading or live shadow trading.
- Full crypto portfolio construction across multiple accepted factors.
- A self-contained exchange matching engine.
- Migrating the entire original Qlib pipeline in one step.
- Requiring real LLM API calls in tests.
- Requiring live Binance data downloads in tests.
- Treating Candidate Factor Library entries as production-ready strategies or Trading Gate passes.

## Further Notes

This PRD follows the completed `docs/prd/crypto-evaluation-core.md` and starts after its Task 1-7 acceptance criteria are complete. The next phase should deepen Crypto Mining Automation around the completed Crypto Evaluation Core rather than broadening the evaluator itself.
