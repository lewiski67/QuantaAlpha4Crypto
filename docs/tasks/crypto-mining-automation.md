# Crypto Mining Automation Local Tasks

Date: 2026-06-24
Status: Local task breakdown
Parent PRD: `docs/prd/crypto-mining-automation.md`

These tasks follow tracer bullet slicing. Each task should leave a narrow but complete path that can be verified end to end without live LLM calls or live Binance network access.

## Direction update: Research Gate library intake

ADR-0011 changes the next mining-loop direction. Tasks 1-9 record the completed local and original-flow automation. Tasks 10-11 are the next implementation tasks that make the loop use Research Gate for library intake and use Trading Gate/cost diagnostics as feedback rather than first-stage deletion.

## 1. Build the minimal Crypto Factor Workspace

Status: Done

## Parent

`docs/prd/crypto-mining-automation.md`

## What to build

Create a local workspace boundary for one crypto mining run. The workspace should record run configuration, Crypto Data Universe references, Evaluation Grid settings, Walk-forward Validation settings, generated artifacts, reports, rejected diagnostics, and Candidate Factor Library path.

## Acceptance criteria

- [x] A mining run can create a deterministic Crypto Factor Workspace under a configured output directory.
- [x] The workspace records a run manifest with data references, Candidate Horizons, Evaluation Grid, Walk-forward Validation settings, and artifact paths.
- [x] The workspace has stable locations for Factor Evaluation Reports, rejected diagnostics, and Candidate Factor Library updates.
- [x] The workspace wording identifies outputs as research artifacts, not live strategies.
- [x] A smoke test can create the workspace without Qlib data, LLM calls, or Binance network access.

## Blocked by

None - can start immediately.

## User stories covered

1, 8, 9, 10

## 2. Run a batch of supplied Factor Callables through the crypto evaluation core

Status: Done

## Parent

`docs/prd/crypto-mining-automation.md`

## What to build

Add the first end-to-end mining runner path for explicitly supplied Factor Callables. The runner should evaluate multiple Directional Factors through the existing Crypto Panel, fixed Evaluation Grid, Walk-forward Validation, Factor Evaluation Report, gates, and Candidate Factor Library APIs.

## Acceptance criteria

- [x] A batch runner can load or receive multiple Factor Callable references.
- [x] Each Factor Callable is evaluated through the existing `quantaalpha_crypto` public APIs.
- [x] Candidate and strong factors produce Factor Evaluation Reports and Candidate Factor Library entries.
- [x] Rejected factors produce visible gate reasons and are not stored as accepted entries.
- [x] A deterministic test covers one candidate pass and one rejected factor in the same run.

## Blocked by

- Task 1. Build the minimal Crypto Factor Workspace

## User stories covered

2, 6, 7, 9, 10

## 3. Capture Factor Callable execution failures as rejected diagnostics

Status: Done

## Parent

`docs/prd/crypto-mining-automation.md`

## What to build

Extend the batch runner so invalid Factor Callables are handled as failed research candidates instead of crashing the whole mining run. Failures should preserve enough context for later LLM repair or human diagnosis.

## Acceptance criteria

- [x] Syntax, import, index, and runtime failures are captured as structured rejected diagnostics.
- [x] A failed Factor Callable does not stop unrelated candidates from being evaluated.
- [x] Failed candidates are not stored in the Candidate Factor Library.
- [x] Diagnostics include factor reference, error type, error message, and run artifact path.
- [x] A deterministic test covers one failed callable and one successful callable in the same run.

## Blocked by

- Task 2. Run a batch of supplied Factor Callables through the crypto evaluation core

## User stories covered

3, 7, 9, 10

## 4. Add an LLM Factor Proposal interface with deterministic fake-provider tests

Status: Done

## Parent

`docs/prd/crypto-mining-automation.md`

## What to build

Define the first crypto-native proposal interface for generating Directional Factor candidates. The interface should accept mining context and return candidate factor specifications or code references, while tests use a deterministic fake provider.

## Acceptance criteria

- [x] A proposal provider interface can produce one or more candidate Directional Factor specifications.
- [x] The interface records prompt/context metadata in the run manifest.
- [x] The runner can evaluate candidates returned by a fake proposal provider.
- [x] Provider output must not bypass the existing evaluation gates.
- [x] Tests do not require real LLM API calls.

## Reuse notes

- Direct reuse target: `quantaalpha.llm.client.APIBackend` and `robust_json_parse` for future real LLM providers.
- Narrow modification target: `quantaalpha.core.proposal` style of provider/conversion interfaces.
- Migration source: `quantaalpha.factors.proposal` prompt and JSON parsing patterns.
- Unsuitable for direct Task 4 reuse: Qlib-bound `FactorTask`, `QlibFactorExperiment`, and full `quantaalpha.pipeline.factor_mining` evolution loop.

## Blocked by

- Task 3. Capture Factor Callable execution failures as rejected diagnostics

## User stories covered

4, 8, 9, 10

## 5. Add a bounded repair loop for generated Factor Callables

Status: Done

## Parent

`docs/prd/crypto-mining-automation.md`

## What to build

Add a small repair loop around generated Factor Callables. When a candidate fails execution, the loop should pass structured diagnostics to a repair provider, retry within a configured attempt limit, and preserve both failed and repaired artifacts.

## Acceptance criteria

- [x] The repair loop has a configurable maximum attempt count.
- [x] Repair attempts receive structured diagnostics from failed Factor Callable execution.
- [x] A repaired Factor Callable can proceed through evaluation and gates.
- [x] Unrepaired failures remain rejected diagnostics and are not stored as accepted entries.
- [x] Tests use a fake repair provider and cover both repaired and unrepaired candidates.

## Reuse notes

- Migration source: `quantaalpha.factors.regulator.consistency_checker.FactorConsistencyChecker.check_and_correct` for bounded correction attempts.
- Migration source: `quantaalpha.factors.coder.factor.FactorFBWorkspace` for execution feedback capture.
- Migration source: `quantaalpha.pipeline.loop.AlphaAgentLoop` for proposal -> execution -> feedback loop shape.
- Unsuitable for direct Task 5 reuse: Qlib expression repair, `FactorTask`, HDF output execution, and full evolution loop, because generated crypto Factor Callables use `factor(panel) -> score Series[(timestamp, symbol)]`.

## Blocked by

- Task 4. Add an LLM Factor Proposal interface with deterministic fake-provider tests

## User stories covered

5, 7, 9, 10

## 6. Produce a full local crypto mining round artifact

Status: Done

## Parent

`docs/prd/crypto-mining-automation.md`

## What to build

Wire the workspace, batch runner, proposal provider, repair loop, evaluation reports, rejected diagnostics, and Candidate Factor Library updates into one local mining round that can be run from a single programmatic entry point.

## Acceptance criteria

- [x] One call can run a complete local crypto mining round against deterministic fixture data.
- [x] The run writes a manifest, reports, rejected diagnostics, and Candidate Factor Library entries.
- [x] The run includes at least one generated candidate, one repaired candidate, one rejected factor, and one accepted factor in tests.
- [x] The output is reproducible from the manifest and does not require Qlib data.
- [x] The output remains a research artifact and does not imply live trading readiness.

## Reuse notes

- Direct shape reuse: `quantaalpha.pipeline.base.RDLoop` and `quantaalpha.pipeline.loop.AlphaAgentLoop` establish the propose -> execute/evaluate -> feedback/artifact workflow shape.
- Migration source: `quantaalpha.pipeline.factor_mining` shows how a full round records run/task metadata around one local execution.
- Unsuitable for direct Task 6 reuse: dynamic Qlib class-path settings, multiprocessing evolution orchestration, Qlib runner/coder, and session pickle behavior.
- Progressive in-place replacement note: `run_local_crypto_mining_round(...)` is a crypto-correct proving-ground entry point that should later inform how the original pipeline entry points are folded into Binance crypto behavior.

## Blocked by

- Task 5. Add a bounded repair loop for generated Factor Callables

## User stories covered

1, 2, 3, 4, 5, 6, 7, 9, 10

## 7. Add a thin CLI entry point for local crypto mining runs

Status: Done

## Parent

`docs/prd/crypto-mining-automation.md`

## What to build

Expose the completed local mining round through a small CLI entry point. The CLI should accept a config path and output directory, run the deterministic local loop or configured providers, and print where artifacts were written.

## Acceptance criteria

- [x] A CLI command can run a local crypto mining round from a config file.
- [x] The command writes artifacts into the configured Crypto Factor Workspace.
- [x] The command exits non-zero on invalid config and prints actionable errors.
- [x] The command does not require live LLM calls unless configured to use a real provider.
- [x] A CLI smoke test runs with fake providers and deterministic fixture data.

## Reuse notes

- Direct shape reuse: existing `quantaalpha/cli.py` command registry now exposes `crypto_mine` beside `mine` and `backtest`.
- Migration source: `quantaalpha.backtest.run_backtest` for argparse-style config validation and non-zero error exits.
- Current safety-boundary entry point: `python -m quantaalpha_crypto.mining.cli`.
- Progressive in-place replacement note: the CLI keeps the original top-level command surface available while proving the crypto local round behind a thin command.

## Blocked by

- Task 6. Produce a full local crypto mining round artifact

## User stories covered

1, 2, 6, 8, 9, 10

## 8. Prepare integration notes for the original QuantaAlpha pipeline and UI

Status: Done

## Parent

`docs/prd/crypto-mining-automation.md`

## Deliverable

`docs/prd/crypto-original-pipeline-integration.md`

## What to build

Document how the local crypto mining round should later integrate with the original QuantaAlpha pipeline and UI. This should identify reusable original-project patterns without forcing Crypto Panel data into Qlib daily equity assumptions.

## Acceptance criteria

- [x] The notes identify original QuantaAlpha modules that can serve as architecture references.
- [x] The notes classify original QuantaAlpha modules as direct reuse, narrow modification, migration source, or unsuitable for the Binance crypto trading path.
- [x] The notes identify integration boundaries for `quantaalpha/pipeline/`, `quantaalpha/factors/`, `quantaalpha/backtest/`, and UI.
- [x] The notes identify which original entry points, pipeline concepts, module names, and UI surfaces should be preserved during Progressive In-place Replacement.
- [x] The notes state which original Qlib assumptions must not leak into the crypto-native path.
- [x] The notes preserve the research/deployment boundary from ADR-0010.
- [x] The notes propose the next PRD after local crypto mining automation is complete.

## Blocked by

- Task 7. Add a thin CLI entry point for local crypto mining runs

## User stories covered

8, 10, 11

## 9. Connect a real Anthropic Claude provider to crypto mining

Status: Done

## Parent

`docs/prd/crypto-mining-automation.md`

## What to build

Add a real Claude-backed provider that satisfies the existing crypto mining proposal and repair interfaces without changing the mining round workflow. The provider should use Anthropic Claude Opus 4.8 by default, parse JSON factor specifications, compile research Factor Callables, and leave all Research Gate and Trading Gate decisions to the Crypto Evaluation Core.

## Acceptance criteria

- [x] A real provider can satisfy `FactorProposalProvider` and return generated `FactorProposalCandidate` objects.
- [x] A real repair provider can satisfy `FactorRepairProvider` and return repaired candidates or `None`.
- [x] The default Anthropic model is the API-verified Opus 4.8 id: `claude-opus-4-8`.
- [x] The provider omits `temperature` by default because Anthropic reports `temperature` as deprecated for `claude-opus-4-8`.
- [x] The provider reads `ANTHROPIC_API_KEY` only at call time through the Anthropic client and never records secrets in manifests.
- [x] LLM JSON output is parsed into candidate metadata plus Python code defining `factor(data)`.
- [x] Generated callables still go through execution diagnostics, walk-forward validation, gates, reports, and the Candidate Factor Library.
- [x] CLI config can choose `provider="anthropic"` and `repair_provider="anthropic"` while preserving the deterministic `fake` provider path.
- [x] Automated tests use injected fake completion clients and do not require live Anthropic network access.

## Reuse notes

- Direct reuse where practical: the provider uses the existing `FactorProposalProvider` / `FactorRepairProvider` seams and reuses the original `robust_json_parse` when `quantaalpha.llm.client` can be imported.
- Compatibility fallback: because importing the original LLM client currently requires optional dependencies such as `tiktoken`, the provider includes a local JSON parsing fallback instead of forcing the whole original LLM stack into the crypto mining path.
- Narrow custom adapter: direct Anthropic `/v1/messages` support is implemented separately because the original `APIBackend` is OpenAI-compatible and does not natively consume `ANTHROPIC_API_KEY`.
- Live smoke result: a manual Anthropic call with `claude-opus-4-8` generated five parseable/compilable research candidates without writing artifacts.
- Safety boundary: generated factor code is a research artifact and is not a security sandbox or live trading strategy.

## Blocked by

- Task 8. Prepare integration notes for the original QuantaAlpha pipeline and UI

## User stories covered

4, 5, 7, 8, 9, 10

## 10. Use Research Gate for mining library intake

Status: Pending

## Parent

`docs/prd/crypto-mining-automation.md`

## What to build

Update the mining runner so Candidate Factor Library intake uses Research Gate results. Trading Gate results should remain visible in reports, manifests, and feedback, but should not be the sole reason to discard a factor with stable gross signal.

## Acceptance criteria

- [ ] The mining loop stores Research Gate passes as Research Candidate entries.
- [ ] The mining loop does not store Research Gate failures.
- [ ] Trading Gate pass/fail status is preserved in manifest and library metadata when available.
- [ ] A Research Gate pass plus Trading Gate fail is treated as a retained research candidate, not as a production-ready factor.
- [ ] Rejected diagnostics distinguish no-gross-signal rejection from gross-signal-cost-crushed rejection.
- [ ] Tests cover one factor that passes Research Gate, fails Trading Gate, and is retained as a research candidate.

## Blocked by

- `docs/tasks/crypto-evaluation-core.md` Task 8. Split Research Gate and Trading Gate
- `docs/tasks/crypto-evaluation-core.md` Task 10. Store Research Gate passes in the Candidate Factor Library

## User stories covered

2, 6, 7, 10

## 11. Add cost and threshold diagnostics to LLM feedback

Status: Pending

## Parent

`docs/prd/crypto-mining-automation.md`

## What to build

Update next-round proposal and repair feedback so the LLM receives explicit diagnosis from evaluator reports: whether gross signal exists, whether net return is destroyed by costs, whether turnover is too high, and whether thresholds or holding horizons should be adjusted.

## Acceptance criteria

- [ ] Feedback includes `gross_return`, `net_return`, `turnover`, `trade_count`, and `break_even_fee` when present.
- [ ] Feedback summarizes cost drag separately from gross signal.
- [ ] Feedback tells the provider when a candidate likely needs lower turnover.
- [ ] Feedback tells the provider when a candidate likely needs stricter thresholding.
- [ ] Feedback tells the provider when a mechanism has no gross signal and should be abandoned.
- [ ] Feedback remains secret-redacted and does not include API keys or private environment values.
- [ ] Tests cover feedback text/metadata for gross-positive cost-crushed and no-gross-signal cases using fake providers.

## Blocked by

- `docs/tasks/crypto-evaluation-core.md` Task 9. Add gross and cost-crush diagnostics to reports
- Task 10. Use Research Gate for mining library intake

## User stories covered

4, 5, 7, 10
