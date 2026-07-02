# V1 evaluates directional (vol-normalized raw-return) prediction; market residualization deferred to V2

Date: 2026-07-02
Status: Accepted
Amends: ADR-0012 (defers its market-residual target clause to V2; all other
clauses of ADR-0012 — time-series per-symbol, zero free parameters, pure
statistical gate — remain in force for V1)
Reference: `docs/design/factor-system-architecture.md` §3.5–3.6

## Context

The product owner fixed the trading universe to a few large caps (BTC/ETH/SOL)
traded single-leg (long/short the coin itself, no hedge leg), event-driven (not
per-bar). Under this positioning the two return-prediction paths were examined:

1. **Directional**: predict the coin's raw forward return; trade single-leg.
   For BTC this is pure market timing (BTC ≈ the market, per ADR-0012 /
   design doc §3.5); for alts it is a bundled bet (~2/3 market co-movement +
   ~1/3 coin-specific, measured on real 2024–2026 daily data:
   corr(ETH,BTC)=0.82, variance explained 67%).
2. **Market-neutral**: predict the market residual; trade hedged
   (coin vs β·BTC). This is what ADR-0012 originally targeted.

Decision drivers for putting the directional form first:

- Single-leg is the intended first trading form; evaluation should measure what
  will be traded.
- The evaluation machinery (walk-forward + purge, mandatory causality audit,
  NW/ICIR, decay profile, trial registry) is label-agnostic; switching labels
  later costs one function swap.
- Per-trade fee arithmetic at equal horizon favors single-leg (one leg's fees,
  identical gross edge for the same underlying signal).

Known structural risks of raw-return labels, accepted with guardrails (below):
factor clones (market-direction variants dominating the library), pseudo
diversification across correlated coins, and trend-dominated pseudo
significance at long horizons.

## Decision

- **V1 label**: t+1-aligned, **volatility-normalized raw forward return**.
  No market residualization. Vol normalization is retained (it is unrelated to
  hedging; it keeps IC comparable across symbols/periods).
- **V1 signals are explicit directional bets.** The BTC clause of ADR-0012 /
  design doc §3.5 ("judged as an explicit directional market-timing bet")
  extends to all V1 symbols. Do not present V1 results as market-neutral.
- **Guardrails (mandatory in V1):**
  1. **Horizons confined to intraday scale (~15min–4h).** Raw-return labels at
     daily+ horizons are dominated by a single market trend path and are not
     statistically honest; long horizons reopen only with V2 residual labels.
  2. **TSMOM benchmark retained.** The Base Factor Model keeps the naked
     time-series-momentum benchmark; candidates must show incremental IC over
     it (clone killer). `residualize(...)` as a label transform is deferred.
  3. **Library correlation check retained** (factor return streams; reject
     high-correlation candidates) and the risk layer must treat the few coins
     as ~1 correlated bet, not N independent bets.
- **Event-driven form**: threshold/turnover choices stay out of the factor
  layer (zero free parameters). Evaluation verifies the *structure* via the
  conditional-return profile (bucket monotonicity + top-bucket significance,
  PLAN 2.5); the deployment layer picks thresholds against fee arithmetic.
- **V2**: reintroduce market residualization (`_market_residual`, per-window
  train-fit/test-apply β) as the label; machinery unchanged. Alts residualize
  against an external proxy; BTC stays directional (§3.5). V2 unlocks daily+
  horizons and hedged trading.

## Consequences

- PLAN 1.2 rescopes to `_vol_norm_returns` only; `_market_residual` moves to
  V2. PLAN 1.3 keeps the Base Factor Model as an incremental-IC benchmark but
  defers the residualization label transform.
- PLAN 2.5's conditional-return profile consumes vol-normalized raw returns in
  V1 (residual returns in V2) and becomes the central evidence for the
  event-driven trading form.
- Iteration 4's net-cost check must use event-driven turnover, not per-bar
  turnover; the fee wall at intraday horizons is the expected kill criterion
  for weak candidates.
- Old null results and library entries produced under raw labels remain valid
  as *directional* evidence only; they must be re-evaluated under V2 labels
  before any market-neutral claim.
