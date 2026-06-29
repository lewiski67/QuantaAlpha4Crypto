# Crypto Quant Factor Mining

This context defines the domain language for adapting QuantaAlpha into a crypto-native factor mining system.

## Language

**Effective Factor**:
A candidate signal that passes the Trading Gate: stable out-of-sample behavior under the allowed trading actions, supporting evidence such as stable Rank IC or IC, and positive performance after turnover, fees, slippage, and funding.
_Avoid_: Good factor, valid factor, alpha

**Crypto Data Universe**:
All crypto market, trade-derived, and external macro data available to the project for factor construction and validation.
_Avoid_: Dataset, raw files

**Forward Return**:
The future price return over a defined prediction horizon used as one evaluation target for a factor.
_Avoid_: Future profit, next return

**Tradable Signal**:
A factor-derived position signal that can survive realistic turnover and transaction cost assumptions in out-of-sample evaluation.
_Avoid_: Prediction, score

**Candidate Horizon**:
A time horizon considered during factor evaluation, including 1m, 15m, 30m, 1h, 4h, and 1d. A candidate horizon is not necessarily the frequency at which trades are placed.
_Avoid_: Trading frequency, rebalance interval

**Input Lookback Window**:
The maximum historical time span a factor is allowed to read when calculating one score at timestamp `t`. For example, a 4h input lookback window means the score at `t` may use data from `[t-4h, t]` but not future rows.
_Avoid_: Update frequency, holding horizon

**Update Frequency**:
How often a factor score is recalculated. This can be shorter or longer than the Input Lookback Window. For example, a factor may use a 4h lookback and update every 15m.
_Avoid_: Lookback, rebalance frequency

**Rebalance Frequency**:
How often the strategy is allowed to adjust positions from factor scores. This is separate from Update Frequency and separate from Holding Horizon.
_Avoid_: Holding horizon, candidate horizon

**Allowed Trading Action**:
An action the strategy is permitted to take: spot long, perpetual long, or perpetual short. Perpetual positions may use leverage, capped at 3x.
_Avoid_: Operation, trade type

**Binance Execution Venue**:
The only intended trading venue for first-stage strategy evaluation and deployment. Venue-specific fees, funding, symbol availability, and execution rules should be modeled from Binance rather than from exchange-agnostic assumptions.
_Avoid_: Exchange, broker

**Binance Crypto Trading System**:
The intended end-state of this project: a maintainable system for researching and eventually operating crypto strategies on Binance. The first-stage venue is Binance, but the tradable universe is not limited to Bitcoin.
_Avoid_: BTC-only system, exchange-agnostic crypto platform

**Progressive In-place Replacement**:
The migration strategy for QuantaAlpha: preserve the original architecture shape, entry points, and workflow concepts where practical, while gradually replacing or modifying their internals for the Binance Crypto Trading System.
_Avoid_: Permanent parallel rewrite, full greenfield rebuild

**Binance Trading Cost**:
The venue-specific cost paid by a strategy on Binance, including spot or perpetual maker/taker fees, perpetual funding payments when applicable, and execution slippage assumptions. The evaluator should prefer account-level or symbol-level Binance rates and fall back to conservative public defaults only when authenticated rates are unavailable.
_Avoid_: Generic fee, transaction cost

**Cost Source Fallback**:
The conservative cost assumptions used when Binance account-level fee or funding data is unavailable. Fallback costs should be treated as a limitation of the evaluation, not as the preferred cost source.
_Avoid_: Default fee, estimated fee

**Feature Data**:
Any historical data source that a factor is allowed to read when producing a directional score, including spot candles, trade-derived features, futures data, funding data, and external macro data.
_Avoid_: Input data, predictors

**PnL Data**:
The venue- and product-specific price and cost data used to calculate realized strategy returns. Spot actions must use Binance spot execution data, while perpetual long or short actions must use Binance USD-margined futures or mark price data plus funding.
_Avoid_: Backtest data, price data

**Crypto Panel**:
The canonical time-series table format for the refactored system, indexed by timestamp and symbol. It replaces Qlib daily stock data as the internal representation for crypto factor construction and evaluation.
_Avoid_: Qlib data, daily_pv, market dataframe

**Crypto-native Subsystem**:
The umbrella package under `quantaalpha/crypto/`. It contains two modules: `quantaalpha/crypto/evaluation/` for evaluating supplied Directional Factors, and `quantaalpha/crypto/mining/` for automating mining runs around that evaluator.
_Avoid_: Qlib compatibility layer, full rewrite

**Crypto Evaluation Core**:
The module under `quantaalpha/crypto/evaluation/` responsible for Crypto Panel construction, Factor Callable evaluation, fixed Evaluation Grid scoring, Walk-forward Validation, Research Gate and Trading Gate classification, Factor Evaluation Reports, and Candidate Factor Library persistence. It does not generate factors or call LLMs.
_Avoid_: Mining pipeline, automation loop, live strategy engine

**Crypto Mining Automation**:
The module under `quantaalpha/crypto/mining/` responsible for organizing mining runs around the Crypto Evaluation Core, including Crypto Factor Workspaces, batch evaluation, rejected diagnostics, LLM proposal providers, repair loops, and local run artifacts.
_Avoid_: Evaluation core, backtest engine, live execution system

**Original-flow Crypto Mining**:
The next migration stage in which crypto-correct data, factor artifacts, execution, feedback, evaluation, and reporting are folded back into the original QuantaAlpha workflow shape. It preserves the original propose -> code/artifact -> execute -> feedback/repair -> evaluate/backtest -> library/report -> next round flow while replacing Qlib/A-share/daily-frequency internals.
_Avoid_: Separate crypto-only workflow, Qlib-compatible crypto mode

**Cost-aware Mining Feedback**:
The loop feedback passed from evaluation/backtest results into the next factor proposal or repair round. It should include gross return, net return, cost drag, turnover, trade count, break-even fee, fees, slippage, funding where applicable, drawdown, and threshold/horizon diagnostics, so factor mining can tell no-signal factors apart from gross signals that are crushed by costs.
_Avoid_: Post-hoc cost review, final-only backtest

**Trade Trigger**:
The condition under which a tradable signal becomes strong enough to place or adjust a position. Trade triggers separate signal evaluation from forced periodic trading.
_Avoid_: Prediction threshold, timing rule

**Directional Factor**:
A factor whose output is a continuous score representing market direction or strength. In the first stage, the factor does not directly choose the trading action, threshold, holding horizon, or leverage.
_Avoid_: Strategy factor, complete trading rule

**Factor Callable**:
The first-stage formal interface for a directional factor: a Python callable that reads feature data from a crypto panel and returns a continuous score series indexed by timestamp and symbol.
_Avoid_: Factor script, trading strategy

**Evaluation Grid**:
A small fixed set of action, threshold, holding horizon, and leverage choices that the evaluator may search on the training set for each directional factor.
_Avoid_: Hyperparameter search, strategy optimization

**Holding Horizon**:
The future return horizon used to evaluate a score or simulated trade outcome. It answers "over what future period is this signal judged?" and does not define how often the factor updates or how often the strategy rebalances.
_Avoid_: Rebalance frequency, update frequency, input lookback window

**Generalization Gate**:
The out-of-sample requirement that a factor-selected strategy must pass on validation and test periods before being considered effective. This gate exists to reject factors that only work because the evaluation grid overfit the training set.
_Avoid_: Final score, backtest result

**Research Gate**:
The discovery-stage gate used by the mining loop and Candidate Factor Library intake. It requires no leakage, sufficient coverage, stable directional or gross-return evidence, and auditable threshold, horizon, turnover, cost, and break-even-fee diagnostics. It does not require the configured Binance Trading Cost to leave positive net return.
_Avoid_: Production gate, tradability approval

**Trading Gate**:
The formal strategy-stage gate used by crypto backtest and portfolio selection. It requires positive cost-adjusted net performance, acceptable turnover, drawdown, fee and slippage robustness, funding robustness where applicable, and portfolio/risk validation.
_Avoid_: Research gate, first-pass factor screen

**Research Candidate**:
A factor that passes the Research Gate and is worth retaining for further iteration, threshold tuning, or portfolio backtest. A Research Candidate may have positive gross signal while still failing the Trading Gate because costs, turnover, drawdown, or portfolio context are unacceptable.
_Avoid_: Production-ready factor, live strategy

**Break-even Fee**:
The per-trade fee level at which a factor's gross edge would be fully consumed by trading cost under a specific action, threshold, holding horizon, and rebalance setup. It is a diagnostic for fee sensitivity, not an exchange fee quote.
_Avoid_: Binance fee, fixed cost assumption

**Candidate Factor Gate**:
Legacy term for the earlier single first-stage acceptance gate. New code and docs should prefer Research Gate for mining intake and Trading Gate for formal tradability decisions.
_Avoid_: Research Gate, Trading Gate

**Strong Factor Gate**:
Legacy term for the earlier stricter first-stage label. New code and docs should express strength through Research Gate diagnostics and Trading Gate results instead of treating "strong" as production readiness.
_Avoid_: Production-ready factor, guaranteed alpha

**Factor Evaluation Report**:
An auditable report for a directional factor that includes data dependencies, all evaluation grid trials, selected trading parameters, walk-forward window metrics, IC stability, quantile behavior, costs, funding, drawdown, turnover, trade count, gross return, net return, break-even fee, and Research Gate or Trading Gate results.
_Avoid_: Backtest summary, leaderboard row

**Candidate Factor Library**:
The first-stage storage location for evaluated factors that pass the Research Gate. Inclusion in this library means the factor is a research candidate and does not imply Trading Gate approval, production readiness, or permission to trade live.
_Avoid_: Production strategy library, alpha book

**IC Stability**:
The requirement that Rank IC or IC is consistently signed across walk-forward test windows. The first-stage minimum uses same-sign rate of at least 60% and absolute mean Rank IC of at least 0.01.
_Avoid_: High IC, significant IC

**Walk-forward Validation**:
An out-of-sample validation method that repeatedly trains, validates, and tests on time-ordered rolling windows. The first-stage default uses 180d train, 30d validation, 30d test, and a 30d step.
_Avoid_: Single train/valid/test split, random split
