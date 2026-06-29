# Use two-layer factor acceptance gates

Status: Superseded for new mining intake by `docs/adr/0011-split-research-and-trading-gates.md`; the single-factor test-Sharpe (>0.8 / >1.2) and "strong factor" criteria below are further superseded by `docs/adr/0012-time-series-market-neutral-pure-statistical-factor-evaluation.md` (the Research Gate is a pure statistical predicate; tradability Sharpe is a portfolio-level Trading Gate concern).

The first-stage evaluator will use a two-layer gate: candidate factors require stable out-of-sample directionality, positive cost-adjusted trading performance, and test Sharpe above 0.8, while strong factors require test Sharpe above 1.2 and no obvious train-to-test collapse. Rank IC is treated as supporting evidence through sign stability and a low minimum absolute mean threshold, because realistic financial IC is often small and high fixed IC cutoffs can reward overfitting.
