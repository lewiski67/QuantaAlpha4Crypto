# Factor System Architecture (Revised)

Status: Design baseline for the next build phase
Date: 2026-06-29
Supersedes (methodology): the cross-sectional assumptions in
`docs/design/strategy_core_architecture_plan.md` (deleted 2026-07-02; recover
from git history if deployment-layer detail is ever needed) and the
Evaluation-Grid / single-factor-Sharpe assumptions in `docs/adr/0001` and
`docs/adr/0009`.
Requires follow-up: a paradigm ADR + a `CONTEXT.md` rewrite (see §6).

This document defines the target system structure and, for each component, its
**goal**, **design philosophy**, and **caveats**, so the system can be built
against it. It is the authoritative methodology reference until folded into ADRs
and `CONTEXT.md`.

---

## 0. Paradigm decision (read first)

The tradable universe is small (2–3 liquid Binance USD-M perps, e.g. BTCUSDT /
SOLUSDT) and the goal is short-horizon, small-capital intraday timing. That fact
forces one decision that overturns inherited assumptions:

**We do time-series (per-symbol) factor research, not cross-sectional.**

Reasons:

- Cross-sectional Rank IC / quintile long-short is statistically degenerate with
  2–3 symbols (rank correlation across N=2 is always ±1; quintiles of 3 names
  are undefined). The inherited A-share / CSI300 (≈300 names) methodology does
  not transfer.
- Our real question is per-symbol: *does this symbol's score predict its own
  future return over time?* That is a time-series prediction problem.

Switching to time-series is **not free** — it removes the automatic market
neutrality that long-short cross-sectional construction provided. The
methodology below adds back, explicitly, what cross-sectional gave for free:
market neutralization (§3.4), autocorrelation-corrected significance (§3.5), and
orthogonality (§3.7).

---

## 1. System overview

```
                         ┌──────────────────────────────────────────┐
   DISCOVERY (pure stats) │  no thresholds, no sizing, no strategy   │
                         └──────────────────────────────────────────┘
  Data Layer
   CryptoPanel
      │
      ▼
  Factor Generation ──────────────┐ (novelty-aware: knows the library)
   (LLM proposal/repair)          │
      │                           │ feedback: decay, orthogonality,
      ▼                           │           gross signal, NOT net P&L
  Factor Computation              │
   Factor Callable -> score        │  (score only; no-lookahead audit)
      │                           │
      ▼                           │
  Base Factor Model ──────────────┤  V1: trailing-return family, fixed
   (spanning benchmark; V2 adds   │  2min + 4h windows (ADR-0014, 1.3;
    market-proxy residualization) │  vol & funding benchmarks tested,
      │                           │  dropped); market proxy = V2 label
      ▼                           │
  Statistical Evaluation Engine   │  owns the forward-return target:
   - forward-return target         │    t+1 execution, vol-normalized
     (t+1, vol-norm; residual=V2)  │    (market-residual = V2, ADR-0014)
   - factor return stream Sharpe  │  ← core (ADR-0015)
   - sign consistency             │    (symbols × windows; validation
   - daily-block kill-switch t    │     universe may exceed trading set)
   - decay profile (stream Sharpe)│
   - orthogonality vs library     │
   - deflation (uses Trial Reg.)  │
   - walk-forward w/ purge+embargo│
   - full scorecard (ADR-0016)    │
      │                           │
      ▼                           │
  Research Gate (predicate)       │  pass/fail over the evidence above
      │ pass                      │
      ▼                           │
  Factor Library ─────────────────┘  orthogonality-enforced intake;
      │                              stores each factor's return stream
      │  (accumulate a decorrelated set)
      ▼
                         ┌──────────────────────────────────────────┐
   DEPLOYMENT            │  thresholds, sizing, risk live HERE       │
                         └──────────────────────────────────────────┘
  Portfolio Construction
   - factor combination
   - continuous weighting
   - state-adaptation via risk model (NOT a regime filter)
   - risk model (dynamic covariance / vol-target)
      │
      ▼
  Backtest Engine (single, high-fidelity)  ── NautilusTrader; same
      │  produces equity / cost / turnover / drawdown   engine runs live
      ▼
  Trading Gate (predicate)  ── net-after-cost pass/fail over those metrics
      │ pass
      ▼
  Live (same Strategy, same engine)
```

Two cross-cutting pieces of discovery infrastructure feed the engine: the
**Base Factor Model** (§3.4) and the **Trial Registry** (§3.5a).

---

## 2. The load-bearing invariant

There is exactly one rule that, if violated, collapses the whole design:

> **The factor layer carries zero free trading parameters.**
> Thresholds, holding-horizon selection, action choice, position sizing, regime
> filters, and risk controls do **not** exist during discovery. They live only
> in Portfolio Construction and below.

Everything the factor layer outputs is a **statistical statement about a
signal**, never a strategy. This is what keeps discovery honest and prevents the
backtest-overfitting that grid-on-train selection caused. Any diagnostic that
requires a turnover, threshold, or constructed trade to compute (e.g. a
break-even fee) is therefore a *deployment* concern, not a discovery one.

---

## 3. Components

### 3.1 Data Layer — `CryptoPanel` (`data.py`)

**Goal.** Provide a clean, timestamp-by-symbol panel of Binance spot / USD-M
futures / mark / funding data, with product-prefixed fields, as the single
canonical representation.

**Design philosophy.** Data has no opinion about factors or trades. It only
aligns indices, enforces the complete-history universe policy, and exposes
fields. Feature Data (what a factor may read) is kept distinct from PnL Data
(what realized returns are computed from). Keep this — it is correct and already
built.

**Caveats.**
- Funding is sparse (8h cadence on Binance perps). Do not let minute-level
  factors treat funding as a per-minute primary trigger; it is context.
- Survivorship: BTC/ETH/SOL are survivors. For a 2–3 name timing system that is
  acceptable (you trade exactly those names), but never market the results as a
  general crypto edge.

---

### 3.2 Factor Generation — `mining/` (LLM proposal/repair)

**Goal.** Produce candidate Factor Callables from a research direction, and
repair broken ones, without ever touching acceptance decisions.

**Design philosophy.** Generation is decoupled from judgement (the
`mining/ -> evaluation/` direction is the existing invariant — keep it). The LLM
proposes mechanisms; `evaluation/` judges them.

**Caveats.**
- **Novelty feedback is mandatory.** The proposal prompt must receive what is
  already in the Factor Library so it proposes *decorrelated* mechanisms.
  Without this, the LLM re-proposes variants of the same mechanism (already
  visible in the research log's repeated taker-flow exhaustion attempts) and
  burns budget against the orthogonality gate.
- **The library snapshot is filtered per label track (ADR-0014).** V1
  (directional, raw-return labels) and V2 (market-neutral, residual labels)
  proposal rounds each see only their own track's entries: the same mechanism
  under the two label regimes is two independent hypotheses, so "already
  tested" must be answered within one label regime. A mixed snapshot makes the
  LLM wrongly skip the untested other-track version.
- Feedback content is **gross signal, decay, and orthogonality** — never
  net-after-cost P&L. Cost belongs to the deployment side; feeding it back here
  re-introduces the discovery filter ADR-0011 removed.
- Keep secret redaction (`_redact_secrets`) on every feedback/artifact path.

---

### 3.3 Factor Computation — Factor Callable (`evaluation/factor.py`)

**Goal.** Run `factor(panel) -> score Series[(timestamp, symbol)]` under a
no-lookahead contract, and prove the factor reads no future data.

**Design philosophy.** One contract for hand-written and LLM factors. The score
is a continuous opinion, not a trade. This component owns *the score and its
input-side leakage audit only* — it does not define the forward-return target
(that belongs to the evaluation engine, §3.5). Keeping the boundary sharp avoids
smearing the return-target definition across components.

**Caveats.**
- Enforce the input-lookback audit (already present): scores recomputed on a
  truncated window must match, proving the factor reads no future rows.
- The score's own timestamp semantics must be unambiguous (score at `t` uses
  only `[t-lookback, t]`), so the engine can align a t+1 target to it.

---

### 3.4 Base Factor Model — NEW (`evaluation/base_model.py`)

**Goal.** Provide the set of "already-known" return drivers that every new
factor must beat. It is the residualization target for both market
neutralization and orthogonality, and it defines how a factor becomes a
comparable **return stream**.

**Design philosophy.** A new factor is worth nothing for the information it
shares with known drivers; it is worth only its **residual** (incremental)
predictive power. You cannot define "incremental" without a base set. This is
the crypto, time-series analogue of a Barra model — small and self-built.

**Recommended v1 base set (original recommendation, superseded — see note):**

| Base factor | Definition | Why it must be controlled for |
| --- | --- | --- |
| Market proxy | **BTC return** (or a broad crypto index), *not* the within-universe equal weight | a factor that is secretly "long when crypto rises" must not pass |
| Time-series momentum | trailing return over a medium window (e.g. 24h–7d) | TSMOM is the default crypto edge; new factors must beat it |
| Volatility | trailing realized vol | prevents factors that are just vol-timing |
| Funding / carry | funding-rate level | perp-specific carry is a known driver |

> **As built (2026-07-02, iteration 1.3 + ADR-0014; evidence in HANDOFF).**
> Real BTC/ETH/SOL futures testing reshaped this table: the V1 base set is a
> single **trailing-return family at two fixed windows (2min, 4h)** — the
> momentum/reversal sign is symbol-dependent, so it is discovered by the
> spanning-regression coefficients, not pre-committed. **Volatility** was
> dropped (no directional definition at N=2–3; leverage-effect variant
> unverified on crypto; VRP needs options data the pipeline lacks) and the
> vol-norm label already removes vol-scale bets. **Funding** was dropped
> (level, sign, z-score, and extreme-quantile constructs all tested; best
> NW≈1.83, below bar; revival needs cross-sectional construction or richer
> positioning data). The **market proxy** is not a V1 spanning benchmark; it
> enters as V2's residualization target (ADR-0014 defers residualization).

**Market-neutralization at small N (critical).** With only 2–3 symbols, using
the within-universe equal-weight as "the market" is degenerate: regressing
SOL on `(BTC+SOL)/2` makes the residual ≈ `½(SOL − BTC)`, i.e. it silently turns
the test into **BTC–SOL spread trading**. To avoid that:
- **Alts (SOL/ETH):** residualize against an **external** market proxy (BTC or a
  broad index), producing genuine residual alpha rather than a within-set spread.
- **BTC itself:** there is no market to neutralize against (BTC ≈ the market), so
  a BTC signal is inherently a **directional market-timing bet** and must be
  judged as such — it is the hardest, lowest-Sharpe game; do not pretend it is
  market-neutral.

**Factor return stream (definition for orthogonality).** Orthogonality and
incremental significance are computed on factor *return streams*, not raw scores. Define a
parameter-free stream per symbol — `sign(score) × forward_return` (or
score-weighted `forward_return`) — and use it both for the incremental-
significance evidence and for the library correlation check (§3.7). This definition must be fixed and
versioned; it is the only "construction" allowed in discovery and it carries no
free parameters.

**Caveats.**
- The base set is itself a modelling choice; version it. Adding a base factor
  retroactively changes every historical orthogonality verdict.
- Keep it small. An over-rich base model absorbs real alpha into "known
  drivers" and rejects good factors.

---

### 3.5 Statistical Evaluation Engine — replaces `grid.py`'s role (`evaluation/`)

**Goal.** Build the forward-return target and turn a Factor Callable's scores
into a small set of **statistical statements**: does it predict, how strongly,
how stably, for how long, and incrementally over the library.

**Design philosophy.** Pure statistics. No grid search, no threshold, no
simulated strategy. This component **owns the forward-return target** end to
end — t+1 execution alignment, volatility-normalization, and
market-residualization (via §3.4) — so the target is defined in exactly one
place.

> **Amended 2026-07-03 (ADR-0015).** The metric set re-centers on the
> **Factor Return Stream** (the trading-evaluation tradition: STW 1999,
> Lempérière et al. 2014, MOP 2012, practitioner PSR/DSR). The gross stream
> Sharpe here is *not* the retired "Sharpe-of-a-constructed-strategy": the
> sign(score) stream carries zero free parameters (§3.7) — no threshold,
> sizing, or costs — so it remains a pure statistic. The previous IC-centric
> table treated bar-level NW significance as the headline; at minute-bar
> sample sizes that test's power saturates and it retains only kill-switch
> value.
>
> **Amended again 2026-07-03 (ADR-0016).** The table below is the full
> **Factor Scorecard** — every evaluation computes all rows; programmatic
> roles (veto / rank / diagnostic) stay per ADR-0015's working hypothesis
> and are finalized only after real-data scorecards (1.5+). Lineage labels:
> **A** multi-lineage industry standard · **B** citable single lineage
> (AFML) · **C** academic practice · **D** self-constructed (must not be
> presented as industry). "IC / Rank IC" vocabulary is removed: the rank
> form has no single-asset time-series pedigree (cross-sectional lineage);
> the surviving magnitude diagnostic is the **time-series predictive
> correlation** [D] plus bucket monotonicity (PLAN 2.5) [C].

| # | Scorecard row (all on the Factor Return Stream, per symbol × horizon, OOS once 1.5 wires walk-forward) | Lineage |
| --- | --- | --- |
| 1 | Gross stream Sharpe (annualized) — strength/ranking number, pre-cost | A |
| 2 | Stream-mean t on the UTC-daily aggregated stream (= daily Sharpe significance; kill switch \|t\|>3 per ADR-0015; NW on X_d only if its ACF demands it) | form A, daily calibration D |
| 3 | PSR; DSR once the Trial Registry (§3.5a) exists | B |
| 4 | Bet count (flips/flattenings; event triggers) | A |
| 5 | Gross edge per bet (bp) = gross PnL / bet count — breakeven-cost numerator, pre-cost | A |
| 6 | Sub-period Sharpe table + sign counts across symbols × windows (replication, not cross-sectional; co-moving symbols ≈ 1 bet) | A |
| 7 | Correlation to baseline streams + incremental alpha t (FWL intercept vs base model + library, §3.4) | A |
| 8 | Conditional directional accuracy (hit rate conditioned on up/down + payoff ratio; HM/PT form, daily-blocked) | A |
| 9 | Max drawdown, Calmar, time under water | A |
| 10 | Skewness, kurtosis of the stream (PSR inputs) | A |
| 11 | Return concentration, HHI form, positive/negative streams separately | concept A, HHI B |
| 12 | Turnover / average holding period / signal half-life; lag sensitivity (entry +1/+2/+3 bars) | A / A− |
| 13 | Market-exposure trio: corr to **own-symbol** buy-and-hold, alpha t after market control, ratio of longs (own-symbol only — BTC-as-index is a cross-asset input, V2 territory) | A |
| + | Decay profile: row 1 swept over `V1_HORIZON_GRID` — read the natural horizon, don't optimize it | A |
| opt | Time-series predictive correlation (Pearson/Spearman), score vs label — never named IC/Rank IC | D |

Deliberate exclusions (recorded in ADR-0016): Campbell-Thompson OOS R²
(frozen academic lineage, with bar-level NW); parameter-perturbation
plateau checks (procedure-level, revisit at RC report design); cost /
capacity / implementation shortfall (deployment layer).

**Caveats.**
- **t+1 execution.** A score from the bar-`t` close cannot be traded at the
  bar-`t` close; the forward return must start at the next executable point (t+1
  open / t+1 bar). This is part of the look-ahead surface, alongside the old
  threshold issue.
- **Overlapping returns inflate significance.** With holding horizon `h`,
  adjacent forward returns share their window and are autocorrelated by
  construction. Effective independent sample ≈ span / h × n_symbols, far smaller
  than row count. Handled by daily-block aggregation of the stream (ADR-0015);
  bar-level Newey-West is frozen — even after NW correction the effective
  sample at minute frequency stays large enough that "significant" is nearly
  information-free, and NW's truncated kernel understates long-run variance
  under long overlap (Hodrick-1992 critique).
- **Walk-forward must purge + embargo.** Because labels span `h`, training
  samples whose label window overlaps the test period leak future information.
  Purge those samples and embargo a buffer around the train/test boundary
  (López de Prado). The current rolling split (ADR-0002/0003) does not do this
  and leaks at boundaries.
- **Label is volatility-normalized.** Raw returns are heteroscedastic; any
  statistic on raw returns is dominated by high-vol periods. All scorecard
  rows run against vol-normalized forward returns.
- This engine produces evidence, not a decision. The decision is the Research
  Gate (§3.6).

---

### 3.5a Trial Registry — NEW (`evaluation/trial_registry.py`)

**Goal.** Keep a machine-readable count of how many factor candidates /
configurations have been evaluated, so multiple-testing deflation is honest.

**Design philosophy.** Deflation is meaningless without a true denominator. The
human-readable research log (`docs/research/`) is for narrative; it cannot drive
deflation. Every evaluation increments the registry; the Research Gate reads the
count to deflate significance.

**Caveats.**
- Count *all* attempts, including repaired and rejected ones — they are part of
  the search and inflate the multiple-testing burden.
- Scope the denominator sensibly (per research direction vs global); document the
  choice, because it changes the deflation strength.

---

### 3.6 Research Gate — `evaluation/gates.py` (rewritten)

**Goal.** A pure pass/fail predicate over the evaluation evidence, for library
intake and mining feedback. It runs no simulation; it only reads §3.5 output.

**Design philosophy.** Gate on scorecard evidence, not on a constructed strategy. The
current `test_sharpe > 0.8` / `non_positive_oos_return` clauses are
single-factor-strategy artifacts and must be removed — they conflate signal with
an arbitrary trading construction. (Symmetry: the Trading Gate, §3.10, is the
same shape — a predicate over a single engine's output.)

**Pass conditions (target shape, re-expressed per ADR-0015):**
- No leakage (input-lookback audit passes, t+1 respected, walk-forward
  purged/embargoed).
- Sufficient coverage.
- Daily-block kill-switch t on the OOS factor return stream clears |t|>3
  (veto-only: passing is an entry ticket, never an endorsement or ranking).
- Sign consistency of the stream mean across walk-forward test windows and
  across symbols (validation universe may exceed the trading set).
- **Deflated** significance clears a bar set with multiple-testing in mind
  (DSR form once the Trial Registry exists).
- **Incremental significance** over the base model + existing library is
  non-trivial.

**Caveats.**
- Keep the financial-edge humility from ADR-0009: real single-signal edges are
  small; do not set a high absolute stream-Sharpe cutoff that rewards
  overfitting. Consistency + incrementality + deflated significance matter
  more than raw magnitude.
- The gate reads the Trial Registry count so deflation is honest.

---

### 3.7 Factor Library — `evaluation/library.py` (intake hardened)

**Goal.** Store research candidates as **signals** (not strategies), with the
evidence, return stream, and data dependencies needed both to enforce
orthogonality and to reuse them in portfolio construction.

**Design philosophy.** The library is a set of **decorrelated signals**, not a
pile of whatever passed. Intake enforces orthogonality: a new factor whose
return stream is ~collinear with an existing entry adds nothing and is rejected
(or replaces the weaker twin).

**Caveats.**
- **Persist each factor's return stream** (§3.4 definition), not just metadata.
  Without the stored stream you cannot correlate a new candidate against the
  library, so the orthogonality gate cannot run.
- Store signals, not bound trading parameters. The same factor will be used by
  the portfolio layer with different horizons / weights; do not freeze a
  threshold or action into the library entry.
- Orthogonality is enforced **at intake**, which is *earlier* than where the
  deployment layer's diversification sits. Diversification later only works if
  the library was kept diverse here.
- Entries must carry: the full scorecard (incl. incremental-significance
  evidence and decay profile), return stream, base-model version, data
  dependencies, and the candidate-count context for deflation.

---

### 3.8 Mining Feedback Loop — `mining/round.py` + proposal

**Goal.** Close the loop: turn evaluation evidence into the next proposal/repair.

**Design philosophy.** Feedback distinguishes the only states that matter for
*generation*: (a) no gross signal → abandon mechanism; (b) gross signal but
collinear with library → propose something decorrelated; (c) gross signal,
incremental, decaying at horizon X → exploit/refine. Cost/turnover are NOT in
this loop.

**Caveats.**
- This is where novelty (§3.2) and orthogonality (§3.7) results are routed back.
  The loop is incomplete without it.
- Do not let Trading-Gate / net-P&L results leak into proposal feedback.

---

### 3.9 Portfolio Construction — NEW (`portfolio/` or `strategy/`)

**Goal.** Combine library signals into target positions. **This is the first
place trading parameters legally exist.**

**Design philosophy.** Continuous weighting, not thresholds. Map combined signal
strength to exposure; let a cost-aware optimizer produce an *implicit* threshold
(weak signal → expected edge < cost → optimizer holds zero) rather than a
hand-set quantile. Market-state adaptation is handled by the **risk model**
(dynamic covariance / vol-target), which de-risks automatically in turbulent
conditions — this is *not* a regime filter and must not be confused with one.

**Caveats.**
- With only 2–3 symbols, "portfolio" is thin; continuous per-symbol sizing from
  combined signal + a vol-target is the realistic v1, not a 300-name optimizer.
- Threshold optimization is forbidden even here — prefer fixed conventions or
  the optimizer's implicit cutoff; searching a quantile re-introduces
  overfitting.
- **No explicit regime filter.** Regime-dependence is surfaced upstream as a
  discovery diagnostic (per-window stream-Sharpe dispersion, §3.5); here it dissolves into
  risk sizing. An on/off regime switch is avoided because it shrinks the test
  window and needs a hard-to-define, leak-prone regime label.

---

### 3.10 Trading Gate — predicate over the backtest engine (`evaluation/portfolio.py` re-scoped)

**Goal.** Decide whether a **constructed portfolio** is net-positive after real
Binance cost, with acceptable turnover / drawdown / funding robustness.

**Design philosophy.** Tradability is a property of the **portfolio**, not of an
individual factor. The Trading Gate is a **predicate** — it consumes the metrics
produced by the single backtest engine (§3.11) and returns pass/fail. It is not a
second simulator. (Same evidence-vs-decision split as Statistical Engine vs
Research Gate.)

**Caveats.**
- Until a portfolio layer exists, a single-factor minimal construction is a
  *temporary* stand-in for the input. Be explicit that it is a proxy.
- Keep the criterion decoupled from the engine: the same gate predicate should
  apply whether metrics come from the current lightweight engine or NautilusTrader.

---

### 3.11 Backtest Engine + Live Runner — NEW, single engine (NautilusTrader — committed)

**Goal.** One event-driven engine that produces high-fidelity backtest metrics
(account / equity / margin / funding) and runs live execution against Binance —
the same Strategy object in both.

**Design philosophy.** One engine, two modes. Do not build a separate "fast" and
"high-fidelity" simulator: at 2–3 symbols and a handful of portfolio
constructions there are too few candidates to justify a screening tier. The
Trading Gate is just a predicate over this engine's output. **The backtest/live
engine will be built on NautilusTrader (decided 2026-06-29).** Its Binance and
Coinbase venue adapters also de-risk the possible Binance→Coinbase (EU-compliance)
migration. The engine touches deployment only; it does **not** enter discovery
(too slow and concept-mismatched for batch statistical screening). Promote this
to an ADR when the deployment layer is actually built.

**Caveats.**
- Do not adopt NT before the discovery layer's conclusions are trustworthy
  (look-ahead, purge/embargo, market neutralization fixed). High-fidelity
  backtest of an untrustworthy signal is wasted fidelity.
- Adapter needed: library signals (batch series) → NT event-driven `on_bar`.
  Keep venue specifics (fees, funding, symbols) in adapters, never in the
  strategy core, to preserve the venue-migration option.
- Add a fast screening tier *only if* the number of portfolio candidates grows
  enough to need one — not before.

---

### 3.12 Evolutionary Search — DEFERRED (`mining/evolution/`)

**Status: do not build yet.** This is the correct home for the old QuantaAlpha
mutation/crossover/trajectory idea, redesigned. It is a search-efficiency layer
*on top of* a correct discovery process; building it before discovery is correct
just optimizes toward noise faster, and it fights the deflation in §3.5/§3.6.

**Goal.** Direct the LLM proposal budget toward decorrelated, genuinely additive
mechanisms instead of round-by-round blind proposal.

**Design philosophy (how it differs from old QuantaAlpha evolution):**

| Old evolution flaw | Redesign |
| --- | --- |
| Fitness = backtest P&L vs SOTA (conflated, overfit-prone) | Fitness = **deflated incremental IR** — marginal IC/IR after residualizing against base model + current library, penalized by the Trial Registry count |
| Population can collapse onto one mechanism | **Quality-diversity / niching**: an archive binned by mechanism signature (decay-horizon profile, fields used, sign pattern) keeps the search spread |
| Mutation/crossover operate on expression ASTs | **LLM is the variation operator**; the genome is the natural-language mechanism + the Callable. Crossover = "combine A's trigger with B's normalization"; mutation = vary lookback / conditioning event |
| Blindly multiplies candidates, multiple-testing-unaware | **Explicit evaluation budget**; deflation denominator = total evaluated, so selection must yield survivors that still clear the bar at the final denominator |
| (old had none) GA overfits the windows it selects on | **Reserved holdout**: GA runs on train+validation walk-forward only; the final test window is touched once per survivor before intake |

**Caveats.**
- Evolution and honest deflation are in tension: more candidates raise the bar
  for all of them. The budget + reserved-holdout discipline is what keeps the GA
  from making acceptance *harder*. Do not run it open-ended.
- Only worth building once discovery is correct *and* a search bottleneck is
  demonstrated (you are finding some factors and want more/better) — not to
  rescue a pipeline that finds nothing.
- **The fitness formula above is written in V2 (market-neutral) language.** If
  this layer is ever built during V1 (ADR-0014: directional raw-return labels),
  adapt it: incremental IR over the TSMOM/base-model benchmark, not over a
  residualized target. Do not copy the residualization clause verbatim into a
  V1 run.

---

## 4. Mapping to current code (what changes)

| Current | Action |
| --- | --- |
| `evaluation/grid.py` (grid search, selects best trial on train) | **Demote.** Strip parameter selection. Horizon becomes a decay profile, not a search; threshold/action removed. |
| `evaluation/gates.py` (Sharpe>0.8 etc.) | **Rewrite** as a pure predicate (ADR-0015 shape): daily-block OOS kill-switch t + sign consistency + incremental + deflated; drop old strategy-Sharpe/return clauses. |
| `evaluation/factor.py` | **Narrow** to score + input-lookback audit only; the forward-return target moves out to the engine. |
| `evaluation/metrics.py` | **Add** daily-block stream t (ADR-0015; bar-level NW retained as frozen primitive), stream-Sharpe decay, factor-return-stream helpers; market-residualization deferred to V2 (ADR-0014). |
| `evaluation/base_model.py` | **New.** §3.4 (incl. small-N market proxy + return-stream definition). |
| `evaluation/walk_forward.py` | **Fix** to purge + embargo around train/test boundaries. |
| `evaluation/trial_registry.py` | **New.** §3.5a. |
| `evaluation/library.py` | **Harden intake** with orthogonality; persist each factor's return stream. |
| `evaluation/portfolio.py` | **Re-scope** as the portfolio-level Trading Gate predicate (single engine, not a second simulator). |
| `portfolio/` or `strategy/` | **New** construction layer. §3.9. |
| `backtest/` + `live/` | **New**, single NautilusTrader-based engine, two modes. §3.11. |
| `mining/` proposal feedback | **Add** novelty + orthogonality routing. §3.2/3.8. |
| `mining/evolution/` | **Deferred.** §3.12. Redesigned GA over decorrelated incremental factors; do not build before discovery is correct. |

---

## 5. Build sequence (dependency order)

1. **Fix discovery correctness first** (blocks everything downstream):
   t+1 execution + vol-normalized label (market neutralization deferred to V2,
   ADR-0014), the Base Factor Model spanning benchmark, honest significance
   (daily-block stream t per ADR-0015; bar-level autocorr-corrected t-stats
   frozen), and walk-forward purge+embargo.
2. **Define + store the factor return stream** (Base Factor Model) — prerequisite
   for both orthogonality and incremental significance.
3. **Rewrite Research Gate** as a pure predicate; add the Trial Registry and
   multiple-testing deflation.
4. **Harden library intake** with orthogonality on stored return streams.
5. **Close the mining loop** with novelty + orthogonality feedback.
6. **Only then** build Portfolio Construction + the Trading-Gate predicate.
7. **Last**, stand up the single NautilusTrader engine for backtest/live.

Optional, only after step 5 and only if a search bottleneck is demonstrated:
Evolutionary Search (§3.12). It is a search-efficiency layer, not a correctness
step; never build it before discovery is trustworthy.

**On the mining loop (decided).** The propose → evaluate → feedback → next loop
skeleton may be scaffolded early (it is the chosen entry point), but its
**evaluate ring must be wired to the new statistical evaluation (steps 1–3), not
to the existing `grid.py`/`gates.py`.** Wiring the loop to the old grid/gates
first would make its accept/feedback signals old-paradigm and untrustworthy, and
the feedback would teach the LLM the wrong lessons. Build the skeleton and the
new evaluate ring together; do not "get the loop green on old eval, then swap."

Do not reorder. Each step's evidence is meaningless until the prior step's
correctness holds.

---

## 6. Impact on CONTEXT.md and ADRs (follow-up task)

> **Status 2026-07-03: this pass has landed** (ADR-0012/0013 + CONTEXT.md
> rewrite; further amended by ADR-0015/0016). Kept for the record; note the
> vocabulary below has since evolved further — "time-series residual IC"
> wording was itself retired by ADR-0016 (no IC vocabulary for single-asset
> time-series evaluation; see the §3.5 scorecard).

This design overturns controlled vocabulary and decisions and needs a separate
documentation pass:

- **New ADR** (paradigm): "Evaluate factors as time-series, per-symbol,
  market-neutralized signals" — supersedes the cross-sectional framing. It must
  note the small-N market-neutralization degeneracy (§3.4) and mandate an
  external market proxy.
- **New ADR / amendment** (validation): walk-forward must purge + embargo
  overlapping labels; amends ADR-0002 / ADR-0003.
- **`CONTEXT.md` rewrite:**
  - `Effective Factor` — drop standalone net-P&L from the definition; tradability
    is a portfolio property.
  - `Evaluation Grid` — retire, or redefine as decay profiling.
  - `Candidate Horizon` — retire the fixed `{1m,15m,30m,1h,4h,1d}` menu; reframe
    as the decay profile (IC vs horizon), which is read, not searched.
  - `Directional Factor` / `Rank IC` — reframe as time-series residual IC.
  - `IC Stability` — add autocorrelation-correction + deflation.
  - `Allowed Trading Action` — remove the baked-in 3x leverage cap; leverage is a
    deployment/risk-model parameter, not factor-layer vocabulary.
  - `Break-even Fee` — retire. It requires a turnover/construction to compute and
    is a deployment diagnostic at most; it was a relic of the old entangled gate.
    (This also closes the long-standing "break_even_fee never implemented" gap by
    removing the expectation rather than building it.)
  - Add: `Base Factor Model`, `Factor Return Stream`, `Incremental Significance`
    (renamed from `Incremental IC`, ADR-0015), `Market Neutralization`,
    `Deflated Significance`, `Trial Registry`, `Purge/Embargo`.
- **ADR-0001 / ADR-0009**: mark superseded by the new paradigm ADR.

That pass has landed; this file and the ADRs (0012–0016) are jointly
authoritative, with `CONTEXT.md` carrying the controlled vocabulary.

