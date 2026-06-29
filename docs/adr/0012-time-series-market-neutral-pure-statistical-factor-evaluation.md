# Evaluate factors as time-series, market-neutral, pure-statistical signals

Date: 2026-06-29
Status: Accepted
Supersedes: ADR-0001 (fixed-grid evaluation); supersedes the single-factor-Sharpe
and "strong factor" parts of ADR-0009; retires the Break-even-Fee discovery
diagnostic introduced in ADR-0011.
Reference: `docs/design/factor-system-architecture.md`

## Context

The tradable universe is small (2–3 liquid Binance USD-M perps). The inherited
methodology — cross-sectional Rank IC, quintile long-short, a fixed Evaluation
Grid selected on the training set, and a single-factor strategy Sharpe gate — was
carried over from A-share / CSI300 (≈300 names) and from the crypto migration.

Three problems followed:

1. **Cross-sectional statistics are degenerate at N=2–3.** Rank correlation
   across two names is always ±1; quintiles of three names are undefined. The
   real question is time-series: does a symbol's score predict its own future
   return.
2. **Grid selection on the training set is parameter overfitting.** Selecting
   action / threshold / holding horizon / leverage per factor injects free
   parameters into discovery, the dominant overfitting risk on noisy
   short-horizon data.
3. **Single-factor strategy Sharpe conflates signal with construction.** Gating
   on the Sharpe of an arbitrarily-constructed single-factor strategy measures
   the construction as much as the factor.

## Decision

Factor discovery is **time-series, per-symbol, market-neutral, and purely
statistical**:

- **Time-series, per-symbol.** Evaluate whether each symbol's score predicts its
  own forward return. Cross-sectional Rank IC / quintile framing is retired.
- **Market-neutral target.** Measure IC against the **market residual**: for alts
  residualize against an external proxy (BTC or a broad index, not the
  within-universe equal weight, which degenerates to spread trading at small N);
  BTC itself is judged as an explicit directional market-timing bet. Targets are
  t+1-aligned and volatility-normalized.
- **Zero free trading parameters in the factor layer.** No grid, no threshold, no
  action/leverage choice, no sizing, no regime filter during discovery. Horizon
  is *read* from the Decay Profile, not searched. All trading parameters move to
  the deployment (portfolio / backtest / live) layer.
- **Pure-statistical gate.** The Research Gate is a predicate over: leakage-free
  evaluation, IC sign stability across walk-forward windows, IC information ratio
  with autocorrelation-corrected and **deflated** (multiple-testing) significance,
  and non-trivial **Incremental IC** over a Base Factor Model and the existing
  library. Single-factor Sharpe / net-return clauses are removed.

Tradability remains a **portfolio** property decided at the Trading Gate
(ADR-0011), never a single-factor property.

## Consequences

- `CONTEXT.md` is rewritten: Evaluation Grid, Candidate Horizon (menu), and
  Break-even Fee are retired; Effective Factor drops standalone net-P&L; new
  terms (Base Factor Model, Factor Return Stream, Market Neutralization,
  Incremental IC, Deflated Significance, Trial Registry, Decay Profile,
  Purge/Embargo) are added.
- `evaluation/grid.py` is demoted (no selection); `gates.py` becomes a pure
  statistical predicate; a Base Factor Model, Trial Registry, and orthogonality
  intake are added. See the design doc §4/§5 for sequencing.
- Old null results in `docs/research/` were produced under the superseded
  methodology and are not evidence of absent alpha.
- Leverage caps leave factor-layer vocabulary; they are deployment/risk
  parameters.
