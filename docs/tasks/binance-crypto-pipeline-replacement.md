# Binance Crypto Pipeline Replacement Tasks

Date: 2026-06-24
Status: Draft plan for approval
Parent PRD: `docs/prd/binance-crypto-pipeline-replacement.md`

These tasks continue Progressive In-place Replacement. Each task should leave a narrow, verifiable slice and avoid broad rewrites of the original pipeline.

## 1. Add Binance Data Adapter Into Crypto Panel

Status: Done

## What to build

Load local Binance historical data into Feature Data and PnL Data `CryptoPanel` objects for configured symbols, time range, frequency, and product type.

## Acceptance criteria

- [x] A config can select local Binance data references, symbols, frequency, and time range.
- [x] The adapter returns Feature Data and PnL Data `CryptoPanel` objects.
- [x] The adapter records data dependencies for manifests and reports.
- [x] Tests use local fixture files, not live Binance network access.
- [x] No Qlib provider URI, Qlib region, A-share instrument, or daily stock calendar is required.

## Implementation notes

- Public interface: `BinanceLocalDataConfig`, `BinanceCryptoPanelData`, `load_binance_crypto_panel_data`.
- Supported input formats: local CSV files, Binance spot candle JSONL under `candles/<SYMBOL>/<frequency>.jsonl`, and Binance USD-M futures JSONL under `external/binance/futures/<SYMBOL>/`.
- `data_path` accepts one CSV path, a list of CSV paths, or a Binance data root for JSONL formats.
- Current product paths verified by tests: `spot` and `futures`.
- Futures JSONL ingestion keeps mark close, premium close, and funding-rate columns where available.
- Live Binance downloads remain out of scope for this task.

## 2. Persist LLM Factor Artifacts

Status: Done

## What to build

Persist every LLM-generated factor as an auditable artifact before evaluation.

## Acceptance criteria

- [x] Store prompt context, provider name, model, raw response, parsed JSON, generated source, source hash, and compile status.
- [x] Store factor timing semantics: `input_lookback_window`, `update_frequency`, and declared candidate horizon.
- [x] Manifest records artifact references for each proposed and repaired candidate.
- [x] No API keys or secrets are written to artifacts.
- [x] Failed parsing/compilation is captured as rejected diagnostics.
- [x] Tests use injected fake completion clients.

## Implementation notes

- Workspace now has `factor_artifacts/` and records it in manifest `artifact_paths.factor_artifacts_dir`.
- `FactorProposalCandidate` can carry `source_code`.
- `FactorProposalResult` and `FactorRepairResult` can carry `raw_response` and `parsed_response`.
- Proposal and repair artifacts are written before evaluation or repaired candidate evaluation.
- Artifact payloads include provider, model, prompt context, raw response, parsed response, generated source, SHA-1 source hash, compile status, timing metadata, and `live_strategy: false`.
- Manifest candidate entries include `factor_artifact_reference` when an artifact exists.
- Provider parse/compile failures before candidate evaluation are converted into rejected diagnostics instead of crashing the whole round.
- This task does not implement lookback slicing, update scheduling, rebalance scheduling, or portfolio backtesting.

## 3. Define Original-flow Crypto Mining Run Config

Status: Done

## What to build

Introduce one config schema that describes data, provider, repair, evaluation, and artifact settings for Original-flow Crypto Mining.

## Acceptance criteria

- [x] Config includes data adapter settings, symbol universe, frequency, time range, provider, repair provider, Evaluation Grid, Walk-forward settings, `input_lookback_window`, `update_frequency`, and `rebalance_frequency`.
- [x] Config can include optional `research_direction` to steer proposal and repair prompts.
- [x] Config can run with fake providers in CI.
- [x] Config can select `provider="anthropic"` and model `claude-opus-4-8` for manual runs.
- [x] Invalid configs fail before starting a mining round.
- [x] Config validation rejects ambiguous runs that omit timing semantics needed by backtest interpretation.

## Implementation notes

- Public interface: `OriginalFlowCryptoMiningRunConfig`, `FactorTimingConfig`, `ProviderConfig`, `parse_original_flow_crypto_mining_run_config`.
- The parser validates required fields before execution starts.
- The parser rejects missing timing semantics such as omitted `rebalance_frequency`.
- The parser accepts `provider="fake"` / `repair_provider="fake"` for deterministic CI paths.
- The parser accepts `provider="anthropic"` / `repair_provider="anthropic"` and defaults Anthropic model to `claude-opus-4-8` when no model is supplied.
- Optional `research_direction` is validated as non-empty when provided, forwarded into proposal/repair contexts, and recorded in manifests for provenance.
- The recommended `research_direction` structure is documented in `quantaalpha/crypto/README.md`.
- Current original-flow config has one `symbols` list, so loaded symbols are both Feature Data symbols and PnL/tradable symbols. To use broad crypto market data as context while trading only BTCUSDT/SOLUSDT, add an explicit `feature_universe` / `tradable_universe` split before loading non-tradable symbols into mining runs.
- `OriginalFlowCryptoMiningRunConfig.to_local_round_config()` converts the parsed original-flow config into the existing local crypto mining round config without starting execution.
- Task 2 is complete; this task defines run-level config and does not itself write LLM artifacts.

## 4. Add Crypto Runner For Factor Callable Execution

Status: Done

## What to build

Create the crypto execution runner that replaces Qlib factor execution assumptions while preserving the original run/evaluate workflow role.

## Acceptance criteria

- [x] Runner executes `factor(data)` against Feature Data `CryptoPanel`.
- [x] Runtime, index, type, import, and compile failures become rejected diagnostics.
- [x] Successful outputs flow into the existing Crypto Evaluation Core.
- [x] Runner does not require Qlib `daily_pv.h5`, HDF cache, or Qlib expression syntax.

## Implementation notes

- Public interface: `CryptoFactorSource` and `run_crypto_factor_sources`.
- The runner compiles source code that defines `factor(data)`.
- Successfully compiled factors are passed into the existing batch runner and Crypto Evaluation Core.
- Compile and import failures are captured before evaluation.
- Runtime, index, and return-type failures are captured by the existing batch runner during evaluation.
- The runner uses `CryptoPanel` inputs and does not import or require Qlib.

## 5. Feed Round Results Back Into Proposal Context

Status: Done

## What to build

Make generated, failed, repaired, accepted, and rejected results available as structured context for later proposal and repair rounds.

## Acceptance criteria

- [x] Round metadata summarizes candidate lifecycle states.
- [x] Repair context can include prior diagnostics and failed source references.
- [x] Next-round proposal context can include accepted/rejected summaries without leaking secrets.
- [x] Next-round proposal context includes cost-aware mining feedback, separating gross signal, net return, turnover, and cost drag when those metrics are available.
- [x] Tests cover one follow-up proposal round using previous-round metadata.

## Implementation notes

- Public interface: `build_round_feedback_context`.
- `FactorProposalContext` and `FactorRepairContext` now carry optional `previous_round_feedback`.
- `run_local_crypto_mining_round` accepts optional `previous_round_feedback` and forwards it into proposal and repair contexts.
- Feedback summarizes accepted, rejected, and execution-failed factors from the prior round manifest.
- Feedback reads reports and diagnostics to include gate outcomes, diagnostics, gross signal, net return, turnover, and cost-adjusted metric summaries.
- Feedback marks outputs as research artifacts and must not treat cost-adjusted failure alone as deletion-worthy when Research Gate evidence exists.
- Previous-round feedback is redacted before provider access and before manifest persistence.

## 6. Fold Crypto Mining Into Original CLI/Pipeline Shape

Status: Done

## What to build

Expose the Original-flow Crypto Mining run through an original-project-style command path while preserving the existing deterministic `crypto_mine` proving command.

## Acceptance criteria

- [x] There is a documented command path for Original-flow Crypto Mining.
- [x] The command uses the new run config and data adapter.
- [x] Fake-provider smoke runs in CI.
- [x] Real Claude/Binance use remains opt-in.
- [x] The command output points to manifest, reports, rejected diagnostics, and Candidate Factor Library.

## Implementation notes

- Command path: `quantaalpha crypto_mine_original --config <original-flow-config.json>`.
- Programmatic entry point: `quantaalpha_crypto.mining.cli.original_flow_main`.
- The command parses `OriginalFlowCryptoMiningRunConfig`, loads local Binance data through `load_binance_crypto_panel_data`, then runs `run_local_crypto_mining_round`.
- Existing deterministic proving command `crypto_mine` remains available and fixture-based.
- Top-level `quantaalpha/cli.py` now lazily imports original Qlib/rdagent commands so crypto commands are not blocked by optional legacy dependencies.
- Real Anthropic/Binance use remains opt-in through config; fake-provider smoke is covered by tests.

## 7. Add Crypto-native Portfolio Backtest Layer

Status: Done

## What to build

Extend beyond single-factor evaluation toward portfolio-level backtesting for Research Gate candidate factors.

## Acceptance criteria

- [x] Backtest supports multiple Research Gate candidates or selected factor signals.
- [x] Backtest accounts for Binance fees, slippage, turnover, and funding where applicable.
- [x] Results include equity curve, drawdown, Sharpe, turnover, and cost decomposition.
- [x] Cost-adjusted portfolio metrics are written into mining feedback inputs for later proposal and repair rounds, not only saved as post-hoc backtest artifacts.
- [x] Backtest uses `rebalance_frequency` for position adjustment cadence and does not treat `holding_horizon` as rebalance cadence.
- [x] Backtest records `input_lookback_window`, `update_frequency`, `rebalance_frequency`, and `holding_horizon` in reports.
- [x] Outputs remain research artifacts, not live strategies.

## Implementation notes

- Public interfaces: `PortfolioBacktestConfig`, `PortfolioBacktestResult`, `run_crypto_portfolio_backtest`, and `write_portfolio_backtest_result`.
- The backtest combines one or more factor score series into a portfolio score, rebalances positions on `rebalance_frequency`, and keeps `holding_horizon` only as a recorded evaluation horizon.
- Cost-adjusted PnL includes fees, slippage, turnover, and perpetual funding where applicable.
- Result artifacts include equity curve, metrics, timing semantics, and cost breakdown.
- `write_portfolio_backtest_result` writes `portfolio_backtests/*.json` and records a manifest reference.
- `build_round_feedback_context` includes portfolio backtest metrics without embedding the full equity curve.

## 8. Add Real End-to-end Smoke

Status: Done

## What to build

Run one manual smoke path with real local Binance data and real Claude Opus 4.8 provider.

## Acceptance criteria

- [x] Smoke run uses local Binance data, not fixture panel data.
- [x] Smoke run uses `provider="anthropic"` and `repair_provider="anthropic"`.
- [x] At least one generated factor reaches evaluation or rejected diagnostics.
- [x] Manifest, factor artifacts, reports, diagnostics, and library paths are written.
- [x] The smoke command is documented but not required for CI.

## Implementation notes

- Manual command path: `quantaalpha crypto_mine_real_smoke --config configs/crypto_original_flow_smoke.example.json --allow-live-llm`.
- Programmatic entry point: `quantaalpha_crypto.mining.cli.real_smoke_main`.
- The smoke path reuses Original-flow Crypto Mining and requires `provider="anthropic"` and `repair_provider="anthropic"` before any live call is attempted.
- The command refuses to run unless `--allow-live-llm` is explicitly provided.
- The example config uses local Binance JSONL data through the data adapter and Opus 4.8 model id `claude-opus-4-8`.
- CI tests cover command validation and wiring without live Anthropic or Binance network access.

## Initial Implementation Recommendation

Start with Task 1 and Task 2. Do not fold into the original pipeline until real data and auditable factor artifacts are stable.
