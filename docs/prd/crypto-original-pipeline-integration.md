# Crypto Integration Notes For Original QuantaAlpha Pipeline

Date: 2026-06-24
Status: Integration notes
Related PRD: `docs/prd/crypto-mining-automation.md`
Related ADRs: ADR-0006, ADR-0007, ADR-0008, ADR-0010, ADR-0011

## Purpose

These notes describe how the completed local crypto mining automation path should integrate back into the original QuantaAlpha architecture during Progressive In-place Replacement.

The target is a Binance Crypto Trading System. The intended migration is not a permanent parallel rewrite under `quantaalpha/crypto/`. The crypto module is a safety boundary for proving crypto-correct internals, then folding those internals back into original entry points, pipeline concepts, module names, and UI surfaces where doing so does not leak Qlib daily equity assumptions.

## Architecture References And Classification

| Original surface | Classification | Keep / change decision |
| --- | --- | --- |
| `quantaalpha/cli.py` | Direct reuse | Keep the top-level command registry. `crypto_mine` already proves the path can live beside `mine` and `backtest`; later prefer a coherent `mine --mode crypto` or equivalent rather than an unrelated CLI family. |
| `quantaalpha/pipeline/base.py` | Direct shape reuse | Preserve the `propose -> experiment/code -> run/evaluate -> feedback` loop concept. Replace Qlib-specific implementations behind the same workflow shape. |
| `quantaalpha/pipeline/loop.py` | Migration source | Keep the AlphaAgentLoop idea of one round with proposal, construction, execution, backtest/evaluation, feedback, trace, and library persistence. Replace Qlib factor expression execution and Qlib runner internals. |
| `quantaalpha/pipeline/factor_mining.py` | Migration source | Reuse its full-round orchestration concepts, logging roots, phase names, and evolution task metadata. Do not directly reuse multiprocessing/evolution control until crypto round artifacts are stable. |
| `quantaalpha/pipeline/settings.py` | Narrow modification | Keep class-path settings as a future extension point, but add crypto settings only after local provider interfaces are stable. Do not wire Qlib scenario/coder/runner classes into crypto runs. |
| `quantaalpha/pipeline/evolution/` | Migration source | Preserve original/mutation/crossover trajectory concepts for later crypto factor evolution. Do not use it before crypto candidates, diagnostics, and repair metadata have a stable round artifact contract. |
| `quantaalpha/factors/proposal.py` | Migration source | Reuse prompt-assembly and JSON parsing patterns. Do not directly reuse `QlibFactorExperiment`, `FactorTask`, or expression-focused output contracts for Python Factor Callables. |
| `quantaalpha/factors/coder/factor.py` | Migration source | Reuse execution-feedback ideas and bounded file-based execution patterns. Replace HDF output and `daily_pv.h5` assumptions with Crypto Panel / callable execution contracts. |
| `quantaalpha/factors/regulator/` | Migration source | Reuse consistency, complexity, redundancy, and correction-loop ideas. Adapt checks to Python callable safety, feature/PnL data separation, no-lookahead, and crypto-specific dependencies. |
| `quantaalpha/factors/library.py` | Narrow modification | Keep the idea of a unified factor library and provenance metadata. Replace Qlib expression, HDF cache, and experiment result assumptions with Candidate Factor Library report references and gate metadata. |
| `quantaalpha/factors/runner.py` | Unsuitable for direct reuse | It is tightly bound to Qlib factor data, `daily_pv.h5`, parquet layout, and Qlib backtest execution. Use only as a migration reference for result aggregation and provenance. |
| `quantaalpha/backtest/run_backtest.py` | Direct shape reuse | Keep argparse-style config loading, non-zero error exits, dry-run style checks, and clear progress output. Replace factor sources and Qlib backtest runner internals for Binance crypto. |
| `quantaalpha/backtest/runner.py` | Migration source | Reuse result-saving and command workflow ideas. Do not reuse Qlib dataset/model/backtest creation for Crypto Panel data. |
| `quantaalpha/backtest/factor_loader.py` | Narrow modification | Keep multi-source factor loading shape. Replace Qlib Alpha158/Alpha360 defaults with Candidate Factor Library and Factor Callable references. |
| `quantaalpha/app/utils/health_check.py` and `collect_info` | Direct reuse | Extend environment checks with Binance/API/data availability later. Keep the existing diagnostic command surface. |
| `quantaalpha/app/benchmark/` | Migration source | Reuse benchmark summarization and report presentation ideas. Replace benchmark data model with crypto reports, gates, diagnostics, and Candidate Factor Library entries. |

## Integration Boundaries

### `quantaalpha/pipeline/`

Preserve:

- Round workflow language: propose, construct, execute/evaluate, feedback.
- Session/trace concept.
- Evolution phase terms: original, mutation, crossover.
- Configurable runner/provider class-path direction once crypto provider interfaces stabilize.

Replace:

- Qlib scenario classes as the required scenario for crypto mining.
- Qlib factor expression construction as the only factor construction output.
- Qlib runner/backtest as the evaluation authority.

Crypto authority:

- `quantaalpha_crypto.evaluation` remains the acceptance authority for Factor Callables.
- `quantaalpha_crypto.mining` remains the safety-boundary implementation until it can be folded into original pipeline entry points without Qlib leakage.

### `quantaalpha/factors/`

Preserve:

- Factor proposal prompt organization ideas.
- Factor quality gate ideas.
- Unified library/provenance concepts.
- Repair/correction loop concepts.

Replace:

- `FactorTask` as the canonical generated artifact for crypto.
- Qlib expression parser as the mandatory factor interface.
- HDF factor-output cache as the execution contract.

Crypto authority:

- First-stage generated factors remain Python Factor Callables: `factor(panel) -> score Series[(timestamp, symbol)]`.
- Accepted factors are stored as research artifacts with report references and gate metadata, not production strategies.

### `quantaalpha/backtest/`

Preserve:

- CLI/config shape.
- Dry-run / load-only style checks.
- Clear progress reporting and saved result files.
- Multi-source factor loading concept.

Replace:

- Qlib provider URI, region, instruments, DatasetH, DataHandlerLP, LGBModel, and Qlib backtest.
- A-share daily equity assumptions.
- TopK/dropout portfolio strategy as the default crypto acceptance mechanism.

Crypto authority:

- Backtest/evaluation must use Crypto Panel, Binance spot/perpetual PnL Data, funding, fees, walk-forward validation, Research Gate intake, and Trading Gate tradability checks.

### UI And App Surfaces

Preserve:

- `quantaalpha health_check` and `collect_info` style diagnostic commands.
- Benchmark/report summarization ideas from `quantaalpha/app/benchmark/`.
- Any future existing UI shell should show crypto artifacts through the original UI surface rather than a separate product shell.

Replace:

- Benchmark assumptions that factor success is measured by Qlib expression implementation accuracy alone.
- Displays that imply Candidate Factor Library entries are production-ready live strategies.

Current note:

- `quantaalpha/cli.py` docstring mentions `ui`, but the current command registry exposes `mine`, `backtest`, `crypto_mine`, `health_check`, and `collect_info`. A future UI integration should first reconcile that command surface.

## Original Surfaces To Preserve During Replacement

- Top-level command family: `quantaalpha mine`, `quantaalpha backtest`, health/diagnostic commands, and the new `crypto_mine` proving command.
- Pipeline round shape: proposal, execution/evaluation, feedback, trace/history, artifact/library persistence.
- Evolution vocabulary: original, mutation, crossover, trajectory, parent trajectory.
- Factor library vocabulary: factor name, source/reference, provenance, experiment/round metadata, feedback, metrics.
- Report surfaces: generated factor reports, rejected diagnostics, candidate library summaries, and run manifests.

## Qlib Assumptions That Must Not Leak Into Crypto

- Daily stock calendar as the canonical time axis.
- Qlib provider URI and region as required data configuration.
- A-share instruments or market universe as the tradable universe.
- Qlib `DatasetH`, `DataHandlerLP`, `StaticDataLoader`, and model training as mandatory factor evaluation path.
- Qlib expression syntax as the only factor representation.
- `daily_pv.h5`, HDF output, and Qlib cache layout as mandatory execution artifacts.
- Alpha158/Alpha360 as default crypto factor sources.
- TopK/dropout portfolio logic as the first-stage acceptance gate.
- Single train/valid/test or random split assumptions instead of walk-forward validation.
- Generic transaction cost assumptions instead of Binance fees, funding, product-specific PnL Data, and slippage assumptions.
- Wording that treats research artifacts as deployable live strategies.

## Research / Deployment Boundary

ADR-0010 remains binding:

- Factor Evaluation Reports, Candidate Factor Library entries, rejected diagnostics, and local mining round artifacts are research artifacts.
- They are not live strategies.
- No local mining round should place Binance orders.
- A later deployment PRD must add separate paper trading, live shadow, risk controls, position sizing, kill switches, exchange credentials handling, and operational monitoring before live execution.

## Recommended Next PRD

After Crypto Mining Automation Task 8, the next PRD should be:

`docs/prd/binance-crypto-pipeline-replacement.md`

Scope:

- Define how to fold the proven `quantaalpha_crypto.mining` local round into the original `quantaalpha/pipeline/` and top-level CLI shape.
- Introduce crypto-specific pipeline settings beside current Qlib class-path settings.
- Define replacement adapters for factor proposal, factor execution, evaluation/backtest, factor library, and report display.
- Preserve original workflow concepts while replacing Qlib assumptions with Crypto Panel and Binance execution assumptions.
- Keep deterministic fake-provider tests for CI and defer real LLM/Binance network use behind explicit provider configuration.

Out of scope for that PRD:

- Live Binance order execution.
- Full portfolio construction across accepted factors.
- UI redesign.
