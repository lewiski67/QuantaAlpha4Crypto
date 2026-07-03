# Factor Scorecard: lineage-labeled metric set; compute-first, role-assignment deferred

Date: 2026-07-03
Status: Accepted
Amends: ADR-0015 (its metric enumeration is expanded into the full Scorecard
below; its role assignments — kill switch / ranking / diagnostics — are
retained as the working hypothesis, not final wiring; its "IC / Rank IC as
diagnostics" wording is corrected — the rank form has no single-asset
time-series pedigree). Re-scopes PLAN iteration 1.4/1.5.

## Context

A product-owner-driven audit (2026-07-03, same session that produced
ADR-0015's implementation plan) asked: *what does industry actually use to
statistically evaluate a single-asset time-series factor?* — item by item,
with web verification, refusing appeal to our own documents as authority.
Findings:

1. **A canonical practitioner catalog exists**: López de Prado, *Advances in
   Financial Machine Learning* Ch. 14 "Backtest Statistics" (implemented
   verbatim by mlfinlab) — Sharpe/PSR/DSR, bet counting, drawdown & time
   under water, HHI return concentration, average holding period,
   correlation to underlying, ratio of longs. Cross-checked against the
   time-series replication tradition (MOP 2012, Lempérière 2014 subsample /
   cross-instrument tables) and directional-forecast econometrics
   (Henriksson-Merton 1981, Cumby-Modest 1987, Pesaran-Timmermann 1992).

2. **Two vocabulary leaks from the cross-sectional lineage were found and
   removed**:
   - **"IC / Rank IC" has no citable basis for a single-asset time-series
     factor.** Its definition domain is a per-period cross-section (Grinold-
     Kahn). The academic single-asset analog is the predictive-regression
     slope / OOS R² (Campbell-Thompson lineage — frozen together with
     bar-level NW, ADR-0015); the practitioner scorecard simply has no such
     row. A per-symbol score-vs-label correlation over time *may* be
     computed, but it is a self-constructed diagnostic and must be named
     **time-series predictive correlation (Pearson/Spearman)** — never
     "IC" / "Rank IC", which would keep asserting a false industry pedigree
     in docs and in mining feedback prompts.
   - **Naive hit rate is biased under drift** (an always-long candidate
     scores high hit rate in a bull sample — same disease as long-bias).
     The citable form is the conditional directional test: hit rates
     conditioned on up/down outcomes, HM/PT contingency form. Literature
     warns these tests are **oversized under serial correlation** — same
     disease, same medicine as the kill switch: evaluate on the
     daily-aggregated stream.

3. **One genuine omission surfaced under audit**: gross edge per bet
   (bp/trade) — the practitioner's first feasibility number for
   short-horizon signals (the numerator of every breakeven-cost comparison;
   exactly the 17.7bp-vs-9bp arithmetic used manually in the SOL reversal
   study). Pre-cost, hence statistical-layer computable.

4. **Sequencing decision (product owner)**: implement the *computation* of
   the full scorecard first; assign programmatic roles (veto / rank /
   diagnostic) second, after real scorecards have been produced on real
   data. Computing the full set is cheap; role debates should happen over
   real numbers.

## Decision

### 1. The Factor Scorecard (13 rows + one curve)

Every factor evaluation emits all rows. All stream rows are computed on the
Factor Return Stream (`sign(score) × vol-norm label`, per symbol × horizon;
OOS once 1.5 wires walk-forward). Lineage labels: **A** = multi-lineage
industry standard; **B** = citable single lineage (AFML/López de Prado);
**C** = academic-literature practice, not a practitioner scorecard row;
**D** = self-constructed calibration, must not be presented as industry.

| # | Row | Lineage | Anchor |
|---|-----|---------|--------|
| 1 | Gross stream Sharpe (annualized), per symbol × horizon — **computed on the UTC-daily aggregated stream** (the bar-level stream is overlapping-sampled plumbing whose std does not scale cleanly; the daily number is literally a CTA's daily-PnL Sharpe, √365) | A | MOP 2012 / Lempérière 2014 / CTA scorecards |
| 2 | Stream-mean t on the same UTC-daily aggregated stream (= daily Sharpe significance; t and row 1 differ by √T) | form A, daily-block calibration D | t on strategy stream is universal; the UTC-day blocking is our regime fix (ADR-0015) |
| 3 | PSR; DSR once the Trial Registry exists | B | Bailey–López de Prado; academic counterpart White RC / SPA |
| 4 | Bet count (position flips/flattenings; event triggers) | A | institutional "≥30 trades" checklists; mlfinlab |
| 5 | Gross edge per bet (bp) = gross PnL / bet count | A | breakeven-cost numerator; pre-cost |
| 6 | Sub-period Sharpe table + sign counts across symbols × windows | A | subsample tables everywhere; MOP 58/58 replication. Replication, **not** cross-sectional: each run is single-asset; aggregation is binomial counting; co-moving symbols count as ~1 bet |
| 7 | Correlation to baseline streams + incremental alpha t (FWL intercept) | A | regression vs trend/base benchmarks; = `incremental_significance` (1.3) |
| 8 | Conditional directional accuracy: hit rate conditioned on up/down + payoff ratio (HM/PT contingency form, daily-blocked) | A | Henriksson-Merton 1981, Cumby-Modest 1987, Pesaran-Timmermann 1992; serial-correlation oversize noted in the literature |
| 9 | Max drawdown, Calmar, time under water | A | CTA due diligence; AFML Ch.14 |
| 10 | Skewness, kurtosis of the stream (feed PSR) | A | trend-following positive-skew convention; PSR inputs |
| 11 | Return concentration, HHI form, positive and negative streams separately | concept A, HHI form B | "top trades/days share" is universal due diligence; HHI algorithm is AFML |
| 12 | Turnover / average holding period / signal half-life; lag sensitivity (entry +1/+2/+3 bars) | A / A− | AFML general characteristics; academic skip-period convention |
| 13 | Market-exposure trio: correlation to **own-symbol** buy-and-hold, alpha t after market control, ratio of longs | A | AFML "correlation to underlying" + "ratio of longs"; MOP market regressions. Kills disguised always-long candidates that pass trend-baseline spanning |
| + | Decay curve: row 1 swept over `V1_HORIZON_GRID` | A | lookback×holding grid convention of the momentum literature |
| (opt) | Time-series predictive correlation (Pearson/Spearman), score vs label | D | self-constructed magnitude diagnostic; **never named IC/Rank IC** |

### 2. Implementation red lines

- **Market benchmark = same-symbol buy-and-hold only** (row 13). Regressing
  an ETH factor stream on BTC is a cross-asset input — V2 residualization
  territory, locked under V1's single-symbol rule. Measuring long-bias wants
  the own-symbol underlying anyway.
- **Bucket quantile thresholds must be trailing / in-window** (PLAN 2.5
  conditional-return buckets). Full-sample quantiles are look-ahead — the
  exact leak caught and fixed in the SOL exploration.
- Directional-accuracy tests (row 8) run on daily-aggregated data, not bars
  (documented oversize under serial correlation).

### 3. Compute-first, role-assignment deferred

Every evaluation computes and reports the **entire** scorecard. ADR-0015's
role assignments (daily t as veto-only kill switch at |t|>3; stream Sharpe
ranks, never gates; sign consistency + incremental + deflated significance
as gate predicates; the rest diagnostics) remain the **working hypothesis**
for 1.5/2.2 wiring — they are *not* re-litigated here, but final gate
composition is confirmed only after scorecards have run on real data.
B/C/D-lineage rows must carry their provenance label in docs and reports;
nothing self-constructed may be presented as industry convention.

### 4. Recorded deliberate exclusions

- **Campbell-Thompson OOS R² / predictive-regression slope**: the legitimate
  *academic* single-asset convention; frozen with bar-level NW (ADR-0015) as
  the inference-tradition lineage unsuited to this regime. Recorded so
  "why no OOS R²?" has an answer on file.
- **Parameter/construction perturbation ("parameter plateau")**: real
  practitioner validation, but procedure-level (requires re-running mutated
  factor code), archived — revisit at RC report design.
- **Cost, capacity, implementation shortfall**: deployment layer (Trading
  Gate), unchanged.

## Consequences

- **PLAN 1.4 re-scopes into sub-tasks 1.4.0–1.4.10** (one per metric family,
  each with its own TDD cycle, known traps, and acceptance — see PLAN's
  dedicated section; the rows are *not* one afternoon's task). 1.4.0
  promotes the stream constructor out of `base_model.py` into
  `evaluation/metrics.py`; 1.4.1 is the daily-aggregation primitive
  absorbing the previously planned `_daily_block_tstat` batch and the
  `mining/loop.py` threshold/wording changes; DSR stays deferred to the
  Trial Registry; 1.4.9 is the decay profile; 1.4.10 is a real-data
  full-scorecard exit gate.
- **PLAN 1.5** emits the full scorecard per factor (not a handful of
  numbers); role wiring per ADR-0015 working hypothesis.
- **CONTEXT.md**: new controlled term Factor Scorecard; Decay Profile's
  diagnostic column renamed (no IC vocabulary); Factor Evaluation Report =
  scorecard + gate result.
- **Design doc §3.5** metric table replaced by the scorecard.
- `mining/loop.py` threshold/wording changes (ADR-0015 consequences) fold
  into sub-task 1.4.1.
