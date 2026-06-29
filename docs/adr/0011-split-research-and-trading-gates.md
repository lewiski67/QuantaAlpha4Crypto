# Split research and trading gates

Date: 2026-06-25
Status: Accepted. Amended by `docs/adr/0012-time-series-market-neutral-pure-statistical-factor-evaluation.md`: the gross/net split stands, but the Research Gate carries **no** threshold, turnover, cost, or break-even-fee diagnostics (those are deployment-layer). `break_even_fee` is retired — it requires a turnover/threshold construction the zero-parameter factor layer forbids. References to threshold/turnover/cost/break-even-fee in the Research Gate and Factor Evaluation Report below are superseded accordingly.

## Context

The first crypto evaluator used one acceptance gate for both research discovery and tradability. That gate required positive cost-adjusted trading performance, so short-horizon factors with real gross signal but excessive turnover were rejected before the mining loop could learn from them.

The original QuantaAlpha mining loop is different. Its iterative factor generation mainly feeds Rank IC and without-cost return evidence back to the model, while transaction costs are handled by later backtest and strategy evaluation surfaces. Crypto trading still needs Binance fees, slippage, funding, and turnover modeled explicitly, but those costs should not be the only first-stage discovery filter.

## Decision

The crypto evaluator will expose two gate decisions:

- **Research Gate**: discovery-stage gate used by the mining loop and Candidate Factor Library intake. It requires no leakage, sufficient coverage, stable directional or gross-return evidence, and reportable threshold, horizon, turnover, cost, and break-even-fee diagnostics. It does not require net profitability under the configured trading cost.
- **Trading Gate**: formal strategy-stage gate used by crypto backtest and portfolio selection. It requires cost-adjusted net profitability, acceptable turnover, drawdown, fee and slippage robustness, funding robustness where applicable, and portfolio/risk validation.

The mining loop will store factors that pass the Research Gate as research candidates. The formal backtest and portfolio layer will use the Trading Gate to decide whether any factor or factor combination is tradable.

Factor Evaluation Reports must expose `gross_return`, `net_return`, `turnover`, `trade_count`, and `break_even_fee` so the model and researcher can distinguish:

- no gross signal,
- gross signal crushed by cost,
- too much turnover,
- threshold or holding horizon likely too permissive,
- a genuinely tradable net edge.

## Consequences

- The main factor mining loop becomes closer to the original QuantaAlpha flow: discover possible signals first, then use stricter strategy evaluation later.
- Binance Trading Cost remains visible in reports and feedback, but net-after-cost profitability is no longer the only condition for research library intake.
- LLM feedback must explicitly describe whether the factor has gross signal, how much cost drag destroyed it, and whether the next proposal should reduce turnover, raise thresholds, change holding horizon, or abandon the mechanism.
- Candidate Factor Library entries remain research artifacts. A Research Gate pass is not permission to trade.
- Existing Candidate Factor Gate and Strong Factor Gate terminology is retained only for backward compatibility with older reports and tasks. New code and docs should prefer Research Gate and Trading Gate.
