# Evaluation re-centered on the Factor Return Stream (trading-evaluation tradition); IC demoted to diagnostic; bar-level NW frozen

Date: 2026-07-03
Status: Accepted
Amended-by: ADR-0016 (metric set expanded into the lineage-labeled Factor
Scorecard; "IC / Rank IC as diagnostics" corrected — the rank form has no
single-asset time-series pedigree, the surviving diagnostic is named
time-series predictive correlation; role assignments here remain the
working hypothesis pending real-data scorecards)
Amends: ADR-0012 (its statistical-engine metric set), ADR-0014 (evaluation
metric references; the V1 label, guardrails, and event-driven form are
unchanged). Design doc §3.5 metric table amended accordingly.
Supersedes in part: the "全样本 IC + NW = 评估原语" rationale recorded in PLAN
iteration 0.3 (the formula stands; its interpretive conventions do not
transfer to minute-bar sample sizes).

## Context

A day-long methodology review (2026-07-03, driven by the product owner
questioning why NW t-stats grow mechanically with sample size) established,
with web-verified evidence at each step:

1. **Two legitimate traditions exist for single-asset time-series factor
   evaluation.** (a) The *academic inference tradition*: predictive regression
   slope with HAC (Newey-West / Hansen-Hodrick / Hodrick 1992) standard
   errors, full sample. Our bar-level `_nw_ic_tstat` is mathematically this.
   (b) The *trading-evaluation tradition*: turn the signal into a
   parameter-free position stream, evaluate the resulting P&L series —
   Sharpe/mean significance, cross-instrument × cross-period consistency,
   multiple-testing correction (Sullivan-Timmermann-White 1999 Reality Check;
   Lempérière et al. 2014 "Two Centuries of Trend Following" sign-strategy
   t-stats with cross-asset/cross-century stability as the headline evidence;
   Moskowitz-Ooi-Pedersen 2012 per-instrument sign strategies, 58/58 positive;
   practitioner PSR/DSR; institutional "OOS t≥2, ≥30 trades, net-positive"
   checklists).

2. **Tradition (a) does not transfer to our sample-size regime.** Its
   interpretive conventions (|t|>2 meaningful) were calibrated at monthly/
   daily frequency, T ≈ hundreds. At n ≈ 1.3M minute bars, after NW
   correction the effective sample is still 10⁴–10⁵; any structural non-zero
   correlation — including economically worthless microstructure artifacts —
   tests significant. A significance test's power saturates: "significant"
   carries almost no information, only "not significant" (a reliable kill)
   does. Verified corroboration: even academic intraday studies with HF data
   (Gao-Han-Li-Zhou 2018) structure their tests as **one observation per
   day**, not per bar; the NW literature itself documents that NW understates
   long-run variance under long overlapping horizons (Hodrick 1992 line).

3. **Industry ICIR is a cross-sectional construct** (mean/std of per-period
   *cross-sectional* IC). Our per-window *time-series* IC aggregation is a
   self-constructed first-principles analog, defensible but not a citable
   convention. It must not be presented as "what industry does".

4. **Practitioner scorecards (WorldQuant fitness, CTA metrics) contain no
   t-stat and no IC as headline items.** They score after-cost Sharpe
   (turnover-penalized) and de-correlation against the existing pool;
   significance appears only as an OOS-only checklist item (PSR/DSR form).

## Decision

1. **Core evaluation object: the Factor Return Stream** (`sign(score) ×
   vol-norm label`, design doc §3.7 — already the only permitted
   parameter-free construction). The headline metrics are:
   - **Gross stream Sharpe** (per symbol, per horizon) — the strength/ranking
     number.
   - **Cross-symbol × cross-window sign consistency** — the truth/robustness
     evidence (replication logic, not a cross-sectional construct: each
     symbol/window is an independent run of the same single-asset evaluation;
     a binomial view over runs is the natural pure statistic). Correlation
     discount applies: co-moving symbols count as ~1 bet (ADR-0014 guardrail
     3), so N symbols ≠ N independent confirmations.
   - **Incremental significance vs the Base Factor Model** (ADR-0014,
     unchanged in construction).

2. **Significance is computed on the daily-aggregated stream and acts only as
   a kill switch.** Sum the per-bar stream into UTC-daily buckets `X_d`
   (~900 obs; point estimate exactly preserved; intraday autocorrelation
   absorbed into block variance). Test `mean(X_d)` with a plain t — which *is*
   the daily Sharpe significance test — at threshold **|t| > 3**
   (Harvey-Liu-Zhu-style mining-era hurdle). Passing grants entry only; t
   magnitude never ranks factors and is never positive evidence. Ultimately
   this t must be computed on the **walk-forward pooled OOS stream**
   ("in-sample t is not evidence" — verified institutional practice); until
   1.5 wiring, the full-sample daily t is a coarse pre-filter only.
   Upgrade path: plain t → PSR (fat-tail/skew correction) → DSR (trial-count
   correction, iteration 2's Trial Registry).

3. **IC / Rank IC are demoted to diagnostics.** Not deleted: they answer the
   magnitude-ordering question ("are more extreme scores more predictive?")
   that the sign-stream is blind to and that V1's event-driven thesis depends
   on (PLAN 2.5 bucket monotonicity). They no longer gate, rank, or headline
   anything.

4. **Bar-level NW machinery is FROZEN, not deleted.** `_nw_ic_tstat`
   (factor.py) and the bar-level lag convention embody the academic
   predictive-regression tradition; they stay in the tree, unwired from
   verdicts. `_nw_tstat` (metrics.py) itself is retained as a pure primitive
   — the daily series may still need it (see 5).

5. **If NW is needed again, this is the recorded migration spec:**
   - Apply it to the *daily* series `X_d`, never to bar-level streams.
   - `lag_days` default 1 (V1 horizons ≤ 4h spill at most one UTC boundary),
     but validate empirically first: plot the ACF of `X_d` — crypto trades
     24/7, the "day" boundary has no closing-auction independence argument,
     and vol clustering may extend dependence across days. If the ACF is flat,
     lag 0 (plain t) suffices and NW exits entirely.
   - Multi-symbol pooling: sum *all* symbols' contributions into the same
     `X_d` per day (never treat symbol-days as independent blocks —
     corr(ETH,BTC)=0.82 would overstate n ~3×).
   - `incremental_significance`'s residual-stream NW has the same disease and
     takes the same medicine when 1.5 wires it (daily-block the residual
     stream; lag per the same ACF check).

6. **Validation universe ≠ trading universe.** Sign-consistency replication
   may use all ~35 local USD-M futures symbols (grouped by liquidity tier;
   thin-book symbols' candle-structure artifacts noted; shorter listings and
   survivorship acknowledged). Trading universe stays BTC/ETH/SOL
   (ADR-0014). This operationalizes the existing "information universe ≠
   tradable universe" principle for validation.

7. **Verdict wording discipline.** Passing the kill switch is labeled
   "passes-noise-screen" (or equivalent), never "signal": a pass is an entry
   ticket, not an endorsement. This matters downstream — mining feedback that
   labels a mere pass as "signal" would teach the LLM to breed variants of
   noise-adjacent candidates.

## Consequences

- `evaluation/factor.py`'s bar-level `_nw_ic_tstat` verdict path and
  `mining/loop.py`'s `|NW t| ≥ 2 → "signal"` single-metric verdict are the
  as-is embodiment of what this ADR retires. Code changes (stream-Sharpe
  evaluation output, daily-block kill switch, threshold 3.0, verdict rename)
  follow as a separate implementation batch; this ADR is the specification.
- PLAN 1.4 re-scopes: the Decay Profile's y-axis becomes per-horizon **stream
  Sharpe** (IC retained as a diagnostic column); the horizon-reading role is
  unchanged.
- PLAN 1.5's pooled-OOS wiring now pools the *stream*, not IC contributions;
  the "pooled OOS NW + ICIR two-line" design is re-expressed as
  "pooled OOS daily-block t (kill switch) + per-window stream-Sharpe/sign
  consistency (stability)".
- PLAN 2.2's Research Gate predicate set becomes: daily-block OOS t > 3
  (kill), cross-symbol × cross-window sign consistency, incremental
  significance vs base model + library, deflated significance (DSR-form),
  bucket monotonicity (2.5) — IC-based predicates removed.
- CONTEXT.md language updated: Factor Return Stream is the core evaluation
  object; "IC Stability" re-expressed as stream sign consistency; Decay
  Profile re-defined on stream Sharpe.
- The 2026-07-03 CLV exploration's bar-level t-stats (|t| up to 6.5) are
  re-labeled: sign direction and 4h-kill conclusions stand; all "significant"
  claims await re-verification under the daily-block OOS standard.
