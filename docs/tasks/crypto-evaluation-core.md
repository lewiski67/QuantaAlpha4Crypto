# Crypto Evaluation Core Local Tasks

Date: 2026-06-24
Status: Local task breakdown
Parent PRD: `docs/prd/crypto-evaluation-core.md`

These local tasks follow tracer bullet slicing. Each task should leave a narrow but complete path that can be verified end-to-end.

## Direction update: split research and trading gates

ADR-0011 changes the next evaluator direction. Tasks 1-7 record the completed initial evaluator. Tasks 8-10 are the next implementation tasks that split first-stage mining intake from formal tradability.

## 1. Build the minimal Crypto Panel path

Status: Done

## Parent

`docs/prd/crypto-evaluation-core.md`

## What to build

Create the first usable path from a small Crypto Data Universe fixture into a canonical Crypto Panel indexed by timestamp and symbol. The slice should make Feature Data and PnL Data explicit early, even if the initial fixture is small.

## Acceptance criteria

- [x] A deterministic crypto fixture can be loaded into a Crypto Panel.
- [x] The Crypto Panel preserves timestamp and symbol indexing.
- [x] Feature Data and PnL Data are distinguishable in the loaded representation.
- [x] A smoke check can validate panel shape, symbols, timestamps, and required columns.
- [x] No Qlib daily stock data assumptions are required for this path.

## Blocked by

None - can start immediately.

## User stories covered

1, 2, 20

## 2. Evaluate a baseline Factor Callable

Status: Done

## Parent

`docs/prd/crypto-evaluation-core.md`

## What to build

Add an end-to-end evaluation path for one deterministic Directional Factor implemented through the Factor Callable interface. It should read the Crypto Panel, return a timestamp-by-symbol score series, align scores with Forward Return targets, and report basic directionality metrics for at least one Candidate Horizon.

## Acceptance criteria

- [x] A baseline Factor Callable can run against the Crypto Panel from task 1.
- [x] The callable returns a continuous score indexed by timestamp and symbol.
- [x] Scores are aligned to Forward Return targets without lookahead.
- [x] At least one Candidate Horizon can be evaluated.
- [x] The output includes basic IC or Rank IC evidence for the baseline factor.

## Blocked by

- Task 1. Build the minimal Crypto Panel path

## User stories covered

3, 4, 5, 12

## 3. Add fixed Evaluation Grid scoring with Binance Trading Cost

Status: Done

## Parent

`docs/prd/crypto-evaluation-core.md`

## What to build

Extend the baseline evaluation path so a Directional Factor is converted into candidate Tradable Signals only through a fixed Evaluation Grid. The selected action, threshold, holding horizon, and leverage must come from the training set and must be scored after Binance Trading Cost.

## Acceptance criteria

- [x] The evaluator can search only the configured fixed Evaluation Grid.
- [x] Selected parameters are chosen on training data, not validation or test data.
- [x] Spot long, perpetual long, and perpetual short Allowed Trading Actions are represented.
- [x] Spot PnL uses Binance spot PnL Data.
- [x] Perpetual PnL uses Binance USD-margined futures or mark price PnL Data plus funding.
- [x] Cost Source Fallbacks are recorded when preferred Binance cost data is unavailable.
- [x] Cost-adjusted performance, turnover, fees, and funding are exposed in the result.

## Blocked by

- Task 2. Evaluate a baseline Factor Callable

## User stories covered

6, 9, 10, 11, 17

## 4. Run Walk-forward Validation

Status: Done

## Parent

`docs/prd/crypto-evaluation-core.md`

## What to build

Wrap fixed-grid evaluation in Walk-forward Validation. Each window should select parameters on training data and judge the selected strategy on validation and test periods, using the default 180d/30d/30d windows and 30d step unless explicitly configured otherwise.

## Acceptance criteria

- [x] The default walk-forward schedule uses 180d train, 30d validation, 30d test, and 30d step.
- [x] Each window is time ordered and never shuffles observations.
- [x] Evaluation Grid selection happens inside the training period for each window.
- [x] Validation and test metrics are computed out-of-sample for every completed window.
- [x] Results expose per-window performance and aggregate out-of-sample behavior.

## Blocked by

- Task 3. Add fixed Evaluation Grid scoring with Binance Trading Cost

## User stories covered

7, 8, 16

## 5. Apply legacy Candidate Factor Gate and Strong Factor Gate

Status: Done, superseded for new mining intake by Task 8

## Parent

`docs/prd/crypto-evaluation-core.md`

## What to build

Classify evaluated Directional Factors through the initial two-layer acceptance gates. This task remains a historical implementation record. New mining intake should use Research Gate and Trading Gate from Task 8.

## Acceptance criteria

- [x] Legacy Candidate Factor Gate requires stable out-of-sample directionality.
- [x] Legacy Candidate Factor Gate requires positive cost-adjusted trading performance.
- [x] Legacy Candidate Factor Gate requires decision-period annualized test Sharpe above 0.8.
- [x] Legacy Strong Factor Gate requires legacy Candidate Factor Gate pass, decision-period annualized test Sharpe above 1.2, and no obvious train-to-test collapse.
- [x] IC Stability is included as supporting evidence using same-sign rate and absolute mean Rank IC.
- [x] Rejected factors expose gate failure reasons.

## Blocked by

- Task 4. Run Walk-forward Validation

## User stories covered

12, 13, 14, 15, 19

## 6. Produce Factor Evaluation Reports

Status: Done

## Parent

`docs/prd/crypto-evaluation-core.md`

## What to build

Generate an auditable Factor Evaluation Report for each evaluated Directional Factor. The report should include data dependencies, all Evaluation Grid trials, selected parameters, walk-forward metrics, costs, funding, drawdown, turnover, IC Stability, grouped returns, and gate results.

## Acceptance criteria

- [x] The report records Feature Data and PnL Data dependencies.
- [x] The report includes all Evaluation Grid trials, not only the selected trial.
- [x] The report includes selected trading parameters for each walk-forward window.
- [x] The report includes validation and test metrics.
- [x] The report includes Binance Trading Cost, funding, turnover, drawdown, IC Stability, grouped returns, and gate outcomes.
- [x] The report clearly records Cost Source Fallback usage as a limitation.
- [x] The report does not describe the factor as a live strategy.

## Blocked by

- Task 5. Apply legacy Candidate Factor Gate and Strong Factor Gate

## User stories covered

16, 17, 19

## 7. Maintain the legacy Candidate Factor Library

Status: Done, superseded for new mining intake by Task 10

## Parent

`docs/prd/crypto-evaluation-core.md`

## What to build

Persist factors that pass the initial Candidate Factor Gate or Strong Factor Gate into a Candidate Factor Library with enough metadata to reproduce the acceptance decision. This task remains a historical implementation record. New library intake should store Research Gate passes from Task 10.

## Acceptance criteria

- [x] Legacy Candidate Factor Gate passes can be stored with report references and gate metadata.
- [x] Legacy Strong Factor Gate passes are marked distinctly from ordinary candidate factors.
- [x] Rejected factors are not stored as accepted library entries.
- [x] Library entries retain enough metadata to trace the Factor Callable, Crypto Data Universe inputs, Candidate Horizons, Evaluation Grid, Walk-forward Validation settings, and gate decision.
- [x] Library wording does not imply live trading readiness.

## Blocked by

- Task 6. Produce Factor Evaluation Reports

## User stories covered

18, 20

## 8. Split Research Gate and Trading Gate

Status: Pending

## Parent

`docs/prd/crypto-evaluation-core.md`

## What to build

Replace the single mining acceptance decision with two explicit gate outputs. Research Gate is the first-stage discovery gate used for Candidate Factor Library intake. Trading Gate is the formal strategy-stage gate used by crypto backtest and portfolio selection.

## Acceptance criteria

- [ ] Evaluation output includes a Research Gate decision with explicit pass/fail reasons.
- [ ] Research Gate can pass a factor with stable gross signal even when configured Binance costs make net return negative.
- [ ] Research Gate still fails leakage, insufficient coverage, unstable directionality, train-to-test collapse, and no-gross-signal cases.
- [ ] Evaluation output includes a Trading Gate decision with explicit pass/fail reasons.
- [ ] Trading Gate requires cost-adjusted net performance and acceptable turnover/drawdown diagnostics.
- [ ] Legacy Candidate Factor Gate and Strong Factor Gate fields remain readable for older reports or are mapped to the new gate fields without ambiguity.
- [ ] Tests cover a gross-positive cost-crushed factor that passes Research Gate and fails Trading Gate.

## Blocked by

- Task 7. Maintain the legacy Candidate Factor Library

## User stories covered

14, 15, 18, 19

## 9. Add gross and cost-crush diagnostics to reports

Status: Pending

## Parent

`docs/prd/crypto-evaluation-core.md`

## What to build

Extend Factor Evaluation Reports so every grid trial, selected window, and aggregate summary can show whether a factor has gross signal, whether costs destroy it, and how much fee capacity it has before the edge disappears.

## Acceptance criteria

- [ ] Reports include `gross_return`.
- [ ] Reports include `net_return`.
- [ ] Reports include `turnover`.
- [ ] Reports include `trade_count`.
- [ ] Reports include `break_even_fee`.
- [ ] Reports expose cost drag as a separate diagnostic from gross signal.
- [ ] Reports make threshold and holding-horizon sensitivity visible enough for LLM feedback.
- [ ] Tests verify the new fields for at least one selected trial and one aggregate summary.

## Blocked by

- Task 8. Split Research Gate and Trading Gate

## User stories covered

16, 17, 19

## 10. Store Research Gate passes in the Candidate Factor Library

Status: Pending

## Parent

`docs/prd/crypto-evaluation-core.md`

## What to build

Change Candidate Factor Library intake so it stores Research Gate passes, records Trading Gate status as metadata, and never implies that a stored factor is ready for live trading.

## Acceptance criteria

- [ ] Research Gate passes are stored as Research Candidate entries.
- [ ] Research Gate failures are not stored as Candidate Factor Library entries.
- [ ] Trading Gate pass/fail status is recorded as metadata when available.
- [ ] A Research Gate pass that fails Trading Gate remains clearly labeled as not tradable.
- [ ] Library entries include report references, gate metadata, timing semantics, Evaluation Grid, Walk-forward Validation settings, and data dependencies.
- [ ] Tests cover Research Gate pass plus Trading Gate fail library persistence.

## Blocked by

- Task 8. Split Research Gate and Trading Gate
- Task 9. Add gross and cost-crush diagnostics to reports

## User stories covered

18, 20
