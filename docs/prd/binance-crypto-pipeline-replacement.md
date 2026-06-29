# Binance Crypto Pipeline Replacement PRD

Date: 2026-06-24
Status: Draft plan for approval
Related docs:

- `CONTEXT.md`
- `docs/prd/crypto-mining-automation.md`
- `docs/prd/crypto-original-pipeline-integration.md`
- `docs/adr/0006-use-crypto-native-panel-instead-of-qlib-data.md`
- `docs/adr/0007-build-crypto-native-subsystem-beside-qlib-modules.md`
- `docs/adr/0008-use-python-callables-as-first-stage-factor-interface.md`
- `docs/adr/0010-output-auditable-factor-reports-not-live-strategies.md`
- `docs/adr/0011-split-research-and-trading-gates.md`

## Purpose

Move from the completed local crypto mining loop toward Original-flow Crypto Mining: a Binance crypto factor mining workflow that keeps the original QuantaAlpha flow shape while replacing Qlib, A-share, and daily-frequency internals with crypto-correct implementations.

The intended flow remains:

`mine/propose -> code artifact -> execute -> feedback/repair -> evaluate/backtest -> library/report -> next round`

## Current State

Already available:

- Crypto Evaluation Core for Directional Factor evaluation, fixed Evaluation Grid, walk-forward validation, Research Gate and Trading Gate decisions, reports, and Candidate Factor Library.
- Crypto Mining Automation for workspaces, batch execution, rejected diagnostics, bounded repair, local mining rounds, and CLI.
- Real Anthropic Claude provider using model id `claude-opus-4-8`.
- Local Binance data adapter into `CryptoPanel` for CSV, spot candle JSONL, and USD-M futures JSONL research data.
- Persistent factor artifacts for proposed and repaired LLM-generated factors.
- Deterministic fake providers for tests.
- Integration notes classifying original QuantaAlpha modules for reuse, narrow modification, migration, or rejection.

Not yet available:

- Original-flow crypto mining config and run interface.
- Crypto runner folded into original pipeline shape.
- Round/task feedback metadata usable by the next proposal round.
- Crypto-native portfolio/backtest layer beyond current single-factor Trading Gate diagnostics.
- End-to-end smoke with real Binance data and real Claude provider.

## Goals

- Preserve the original QuantaAlpha workflow shape where practical.
- Add Binance data ingestion as an adapter into `CryptoPanel`.
- Make every LLM-generated factor auditable from prompt to source to evaluation result.
- Replace Qlib factor execution assumptions with Crypto Panel Factor Callable execution.
- Feed diagnostics, repairs, and evaluation outcomes back into round metadata.
- Keep live trading out of scope.
- Keep automated tests deterministic by default.

## Non-goals

- Live Binance order placement.
- Paper trading or production risk controls.
- Full UI redesign.
- Immediate rewrite of all `quantaalpha/pipeline/` internals.
- Reintroducing Qlib data structures as a crypto compatibility layer.

## Required Interfaces

### Binance Data Adapter

Input:

- Local Binance historical data references.
- Symbol universe.
- Frequency.
- Time range.
- Product type: spot or perpetual where available.

Output:

- Feature Data `CryptoPanel`.
- PnL Data `CryptoPanel`.
- Data dependency metadata for reports and manifests.

Acceptance boundary:

- The adapter must not require Qlib provider URI, Qlib region, or daily stock calendars.

### Factor Artifact Store

Input:

- Provider name and model.
- Prompt context.
- Raw LLM response.
- Parsed JSON.
- Generated Python source.
- Factor timing semantics: Input Lookback Window, Update Frequency, and any declared Candidate Horizon.
- Compile status.

Output:

- Stable artifact references in the Crypto Factor Workspace manifest.
- Source hash for reproducibility.
- No API keys or secrets.

Acceptance boundary:

- Artifact storage does not imply factor acceptance. Research Candidate intake belongs to the Research Gate, and tradability belongs to the Trading Gate plus portfolio/backtest validation.

### Original-flow Crypto Mining Run

Input:

- Run config.
- Data adapter config.
- Proposal provider config.
- Repair provider config.
- Optional Research Direction for steering first-round proposal and repair behavior.
- Factor timing config: Input Lookback Window, Update Frequency, and Rebalance Frequency.
- Evaluation Grid.
- Walk-forward settings.

`research_direction` should follow the testable mechanism template documented in `quantaalpha/crypto/README.md`; generic requests such as "find profitable factors" are not specific enough for directed mining.

Output:

- Workspace manifest.
- Factor artifacts.
- Reports.
- Rejected diagnostics.
- Candidate Factor Library updates.
- Round metadata usable by later proposal rounds.

Acceptance boundary:

- The run remains a research artifact and must not place Binance orders.

## Migration Strategy

1. Keep the proven `quantaalpha_crypto.mining` loop as the implementation authority while adding missing adapters and artifacts.
2. Introduce the original-flow run interface after real data and artifact persistence exist.
3. Fold the run interface into the original CLI/pipeline shape only after it can run deterministic tests.
4. Add crypto portfolio/backtest only after single-factor evaluation and metadata are stable.

## User Stories

1. As a researcher, I can run factor mining on local Binance historical data instead of fixture data.
2. As a researcher, I can inspect every generated factor's prompt, raw response, parsed JSON, source code, and compile result.
3. As a researcher, I can distinguish Input Lookback Window, Update Frequency, Rebalance Frequency, and Holding Horizon in every factor run.
4. As a researcher, I can run Claude proposal and repair through the same evaluation gates as fake providers.
5. As a maintainer, I can see generated, failed, repaired, accepted, and rejected factors in one round manifest.
6. As a maintainer, I can keep the original QuantaAlpha workflow language while using Crypto Panel internals.
7. As a maintainer, I can run CI without live Binance or live Claude calls.
8. As a researcher, I can feed gross signal, cost drag, turnover, threshold, and cost-adjusted portfolio/backtest results into later proposal rounds instead of treating costs as a final-only report.
9. As a future operator, I can trust that research artifacts are not mislabeled as live strategies.

## Risks

- Folding back into the original pipeline too early can reintroduce Qlib assumptions.
- LLM-generated code is executable Python and is not a security sandbox.
- Real Binance data may have product-specific gaps, symbol changes, funding cadence, or timestamp alignment issues.
- If Input Lookback Window, Update Frequency, Rebalance Frequency, and Holding Horizon are not recorded separately, backtest results will be ambiguous and hard to reproduce.
- If gross signal and cost-drag diagnostics are only saved after mining instead of passed back into proposal context, the system can keep generating high-turnover factors that look good before fees, slippage, and funding.
- A portfolio/backtest layer built before factor artifacts are auditable will hide diagnosis problems.

## Proposed Execution Order

1. Binance data adapter into `CryptoPanel`.
2. LLM factor artifact persistence.
3. Original-flow crypto mining config and run interface.
4. Crypto runner replacing Qlib factor execution assumptions.
5. Round feedback metadata for repair and next-round proposals, including Research Gate outcomes, Trading Gate diagnostics, and cost-aware mining feedback from available evaluation/backtest metrics.
6. Original CLI/pipeline integration.
7. Crypto portfolio/backtest layer, with cost-adjusted outputs wired back into mining feedback.
8. Real end-to-end smoke.

## Approval Checkpoint

Implementation should not begin until this PRD and `docs/tasks/binance-crypto-pipeline-replacement.md` are reviewed and accepted.
