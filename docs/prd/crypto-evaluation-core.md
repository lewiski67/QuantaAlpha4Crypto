# Crypto Evaluation Core PRD

Date: 2026-06-24
Status: Local PRD

## Problem Statement

QuantaAlpha currently needs a crypto-native Evaluation Core that can evaluate Directional Factors against the realities of Binance spot and USD-margined perpetual markets. The project should not force crypto market data into Qlib daily equity assumptions, and it should not treat a promising score series as an Effective Factor unless it survives realistic out-of-sample evaluation.

The user needs a research workflow that can take Feature Data from the Crypto Data Universe, convert it into a canonical Crypto Panel, evaluate Factor Callables across Candidate Horizons, model Binance Trading Cost with the right PnL Data, and produce auditable Factor Evaluation Reports. The workflow must separate research validation from live strategy deployment.

## Solution

Build the first-stage Crypto Evaluation Core under `quantaalpha/crypto/evaluation/`. It will load crypto Feature Data and PnL Data into a timestamp-by-symbol Crypto Panel, evaluate Directional Factors through a Python Factor Callable contract, select trading parameters only from a fixed Evaluation Grid on training windows, and judge Generalization Gate results with Walk-forward Validation.

The system will produce Factor Evaluation Reports and maintain a Candidate Factor Library for factors that pass the Research Gate. The Trading Gate is reserved for formal backtest and portfolio selection. A Research Gate pass does not produce an automatically deployable live trading strategy.

## User Stories

1. As a quant researcher, I want crypto market data represented as a Crypto Panel, so that minute bars, symbols, and products are evaluated without Qlib daily equity assumptions.
2. As a quant researcher, I want the Crypto Data Universe to distinguish Feature Data from PnL Data, so that factors can read broad historical data while realized returns use product-specific Binance execution data.
3. As a quant researcher, I want a Factor Callable interface, so that hand-written and LLM-generated Directional Factors can be evaluated through one contract.
4. As a quant researcher, I want Factor Callables to return a continuous score indexed by timestamp and symbol, so that trading-rule selection stays separate from factor construction.
5. As a quant researcher, I want Forward Return targets for configured Candidate Horizons, so that factor directionality can be compared across 1m, 15m, 30m, 1h, 4h, and 1d horizons.
6. As a quant researcher, I want fixed Evaluation Grid selection, so that action, threshold, holding horizon, and leverage choices are constrained before out-of-sample scoring.
7. As a quant researcher, I want Walk-forward Validation, so that Directional Factors are tested across multiple time-ordered market regimes.
8. As a quant researcher, I want the default 180d/30d/30d walk-forward window with a 30d step, so that parameter selection has enough history while validation remains out-of-sample.
9. As a quant researcher, I want Binance Trading Cost modeled explicitly, so that performance is not overstated by exchange-agnostic cost assumptions.
10. As a quant researcher, I want Cost Source Fallbacks recorded, so that reports expose when account-level or symbol-level Binance rates were unavailable.
11. As a quant researcher, I want spot, perpetual long, and perpetual short Allowed Trading Actions evaluated against the correct PnL Data, so that spot candles are not silently reused for perpetual PnL.
12. As a quant researcher, I want IC Stability included as supporting evidence, so that an Effective Factor is not judged only by one backtest metric.
13. As a quant researcher, I want monotonic grouped returns included where applicable, so that score ordering can be inspected beyond aggregate PnL.
14. As a quant researcher, I want Research Gate results, so that factors with stable gross signal can enter the Candidate Factor Library even if configured trading costs currently crush their net return.
15. As a quant researcher, I want Trading Gate results kept separate from Research Gate results, so that formal tradability is decided by portfolio/backtest validation rather than by first-pass mining intake.
16. As a quant researcher, I want every Factor Evaluation Report to include all Evaluation Grid trials, so that selected trading parameters are auditable.
17. As a quant researcher, I want gross return, net return, turnover, trade count, break-even fee, fees, funding, and drawdown in the report, so that gross signal, cost drag, and trading viability can be diagnosed separately.
18. As a quant researcher, I want Research Gate passes stored in a Candidate Factor Library with their evaluation metadata, so that later research can reproduce why a factor was retained.
19. As a quant researcher, I want rejected factors to have visible gate reasons, so that failed ideas can be audited without polluting the Candidate Factor Library.
20. As a maintainer, I want the Crypto Evaluation Core built beside existing Qlib modules, so that existing QuantaAlpha LLM and evolution concepts remain available without a fragile compatibility layer.

## Implementation Decisions

- The first-stage system will use a Crypto Evaluation Core under `quantaalpha/crypto/evaluation/` beside the existing Qlib-oriented modules.
- The canonical internal representation will be a Crypto Panel indexed by timestamp and symbol.
- Feature Data and PnL Data will be modeled separately. Feature Data may include broad historical data; PnL Data must match the selected Binance product and Allowed Trading Action.
- Directional Factors will use the first-stage Factor Callable contract: a callable reads a Crypto Panel and returns a continuous score series indexed by timestamp and symbol.
- The evaluator will keep factor generation separate from trading-rule selection. A Directional Factor will not directly choose action, threshold, holding horizon, or leverage.
- Trading parameter selection will use a small fixed Evaluation Grid selected on the training set.
- Walk-forward Validation will be the generalization method. The default window will be 180 days train, 30 days validation, 30 days test, and a 30 day step.
- Binance Trading Cost will prefer account-level or symbol-level fees and historical funding where available.
- Cost Source Fallbacks will use conservative public defaults and must be recorded as report limitations.
- Spot actions will use Binance spot execution data. Perpetual long and perpetual short actions will use Binance USD-margined futures or mark price data plus funding.
- Research Gate acceptance requires no leakage, sufficient coverage, stable out-of-sample directionality or gross-return evidence, and auditable threshold, horizon, turnover, cost, and break-even-fee diagnostics. It does not require positive net return after the configured Binance Trading Cost.
- Trading Gate acceptance requires positive cost-adjusted net performance, acceptable turnover, drawdown, fee and slippage robustness, funding robustness where applicable, and portfolio/risk validation. It is the formal tradability gate, not the first-stage mining intake gate.
- Candidate Factor Gate and Strong Factor Gate are legacy names from the initial evaluator. New code and docs should prefer Research Gate and Trading Gate.
- IC Stability is supporting evidence and should use same-sign rate and low minimum absolute mean Rank IC rather than unrealistic high fixed IC cutoffs.
- The system will output auditable Factor Evaluation Reports and a Candidate Factor Library, not live trading strategies.

## Testing Decisions

- Tests should assert external behavior: panel shape and indexing, no-lookahead alignment, product-specific PnL selection, fixed-grid selection boundaries, walk-forward window construction, gross and net metrics, gate outcomes, and report contents.
- Tests should avoid asserting private implementation details of loaders, evaluators, or report writers when behavior can be checked through public module seams.
- Crypto Panel tests should use small deterministic timestamp-by-symbol fixtures.
- Factor Callable tests should include at least one deterministic baseline Directional Factor with known score alignment.
- Evaluation Grid tests should verify that selected parameters come only from the configured fixed grid and are selected on training data before validation and test scoring.
- Walk-forward Validation tests should verify 180d/30d/30d default window generation and 30d rolling steps.
- Binance Trading Cost tests should cover account-level or symbol-level rates, historical funding where available, and Cost Source Fallback reporting.
- PnL Data tests should prove that spot and perpetual actions use distinct product-specific data.
- Gate tests should cover Research Gate pass/fail, Trading Gate pass/fail, IC Stability support, and train-to-test collapse rejection.
- Factor Evaluation Report tests should verify that all Evaluation Grid trials, selected parameters, gross return, net return, costs, funding, turnover, trade count, break-even fee, drawdown, IC Stability, grouped returns, and gate results are present.

## Out of Scope

- Live Binance order execution.
- Automatically deployable live trading strategies.
- Paper trading or live shadow checks.
- A full rewrite of existing Qlib-oriented modules.
- A broad unconstrained hyperparameter search.
- Exchange-agnostic cost assumptions as the preferred evaluation path.
- Replacing the Factor Callable interface with a strategy DSL.
- Guaranteeing that Candidate Factor Library entries are production-ready.

## Further Notes

This PRD is synthesized from the repository's single-context domain glossary and ADR-0001 through ADR-0011. It intentionally follows the existing decision record: fixed-grid out-of-sample evaluation, Walk-forward Validation, Binance-specific cost modeling, Feature Data and PnL Data separation, Crypto Panel representation, a Crypto Evaluation Core beside Qlib modules, Python Factor Callables, split Research Gate and Trading Gate semantics, and auditable reports instead of live strategies.
