# Crypto Quant Factor Mining

This context defines the domain language for the crypto-native factor mining
system. The methodology was overhauled (time-series, pure-statistical
discovery); see `docs/design/factor-system-architecture.md` and the paradigm
ADR-0012. Terms below reflect the revised paradigm. Retired terms are kept and
marked so older code, reports, and ADRs remain readable.

## Paradigm (binding)

Factor discovery is **time-series, per-symbol** (not cross-sectional — the
tradable universe is 2–3 names, where cross-sectional Rank IC is degenerate).
The **factor layer carries zero free trading parameters**: thresholds, sizing,
holding-horizon *selection*, action choice, leverage, regime filters and risk
controls do not exist during discovery — they live only in the deployment
(portfolio / backtest / live) layer. Discovery produces statistical statements
about a signal, never a strategy.

## Language

**Effective Factor**:
A factor with demonstrated **incremental, market-neutral, statistically robust**
predictive power — i.e. one that passes the Research Gate. Tradability is a
portfolio property decided later at the Trading Gate, not a property of a single
factor. An Effective Factor is not by itself a tradable strategy.
_Avoid_: Good factor, valid factor, alpha, tradable factor

**Crypto Data Universe**:
All crypto market, trade-derived, and external macro data available to the project for factor construction and validation.
_Avoid_: Dataset, raw files

**Forward Return**:
The future price return over a defined prediction horizon used as a factor's
evaluation target. It is measured with **t+1 execution alignment** (a score from
the bar-`t` close is matched to a return that starts at the next executable
point), is **volatility-normalized**, and for alts is taken as the **market
residual** (see Market Neutralization).
_Avoid_: Future profit, next return

**Tradable Signal**:
A deployment-layer position signal produced by portfolio construction from one
or more Effective Factors. It is not a property of an individual factor.
_Avoid_: Prediction, score, factor

**Candidate Horizon** _(retired)_:
Formerly a fixed menu (1m/15m/30m/1h/4h/1d) the evaluator searched over. Retired:
horizon is now **read from the Decay Profile** (IC vs horizon), not selected from
a menu. Use Decay Profile / Holding Horizon instead.
_Avoid_: Trading frequency, rebalance interval

**Input Lookback Window**:
The maximum historical time span a factor is allowed to read when calculating one score at timestamp `t`. For example, a 4h input lookback window means the score at `t` may use data from `[t-4h, t]` but not future rows.
_Avoid_: Update frequency, holding horizon

**Update Frequency**:
How often a factor score is recalculated. This can be shorter or longer than the Input Lookback Window. For example, a factor may use a 4h lookback and update every 15m.
_Avoid_: Lookback, rebalance frequency

**Rebalance Frequency**:
How often the strategy is allowed to adjust positions from factor scores. This is
a **deployment-layer** parameter (portfolio construction), separate from Update
Frequency and Holding Horizon. It does not exist during discovery.
_Avoid_: Holding horizon, candidate horizon

**Allowed Trading Action**:
A deployment-layer choice of how a signal is traded: spot long, perpetual long,
or perpetual short. Leverage and its caps are risk-model parameters, also
deployment-layer — they are not part of factor-layer vocabulary.
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
The venue-specific cost paid by a strategy on Binance, including spot or perpetual maker/taker fees, perpetual funding payments when applicable, and execution slippage assumptions. A **deployment-layer** concern only; it does not enter factor discovery. The evaluator should prefer account-level or symbol-level Binance rates and fall back to conservative public defaults only when authenticated rates are unavailable.
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
The canonical time-series table format for the system, indexed by timestamp and symbol. It replaces Qlib daily stock data as the internal representation for crypto factor construction and evaluation.
_Avoid_: Qlib data, daily_pv, market dataframe

**Crypto-native Subsystem**:
The active package `quantaalpha_crypto/`. It contains `quantaalpha_crypto/evaluation/` for evaluating supplied Directional Factors and `quantaalpha_crypto/mining/` for automating mining runs around that evaluator.
_Avoid_: Qlib compatibility layer, full rewrite, `quantaalpha/crypto/`

**Crypto Evaluation Core**:
The module under `quantaalpha_crypto/evaluation/` responsible for Crypto Panel construction, Factor Callable evaluation, the Statistical Evaluation Engine (time-series IC/IR, Decay Profile, Incremental IC, Deflated Significance), Walk-forward Validation, Research Gate and Trading Gate classification, Factor Evaluation Reports, and Candidate Factor Library persistence. It does not generate factors or call LLMs.
_Avoid_: Mining pipeline, automation loop, live strategy engine

**Crypto Mining Automation**:
The module under `quantaalpha_crypto/mining/` responsible for organizing mining runs around the Crypto Evaluation Core, including Crypto Factor Workspaces, batch evaluation, rejected diagnostics, LLM proposal providers, repair loops, and local run artifacts.
_Avoid_: Evaluation core, backtest engine, live execution system

**Original-flow Crypto Mining**:
The next migration stage in which crypto-correct data, factor artifacts, execution, feedback, evaluation, and reporting are folded back into the original QuantaAlpha workflow shape. It preserves the original propose -> code/artifact -> execute -> feedback/repair -> evaluate -> library/report -> next round flow while replacing Qlib/A-share/daily-frequency internals.
_Avoid_: Separate crypto-only workflow, Qlib-compatible crypto mode

**Cost-aware Mining Feedback** _(renamed: Mining Feedback)_:
The loop feedback passed from evaluation results into the next factor proposal or
repair round. It carries **gross signal, Decay Profile, and orthogonality /
Incremental IC** — it distinguishes (a) no gross signal, (b) gross signal but
collinear with the library, (c) gross signal that is incremental. It does **not**
carry net return, cost drag, turnover, or break-even fee; cost is a deployment
concern and must not re-enter the discovery loop.
_Avoid_: Post-hoc cost review, final-only backtest, net-cost feedback

**Trade Trigger**:
A deployment-layer condition under which a portfolio signal places or adjusts a position. It does not exist during discovery.
_Avoid_: Prediction threshold, timing rule

**Directional Factor**:
A factor whose output is a continuous score representing market direction or strength, evaluated **per symbol as a time series**. The factor does not choose the trading action, threshold, holding horizon, sizing, or leverage.
_Avoid_: Strategy factor, complete trading rule

**Factor Callable**:
The formal interface for a directional factor: a Python callable that reads feature data from a crypto panel and returns a continuous score series indexed by timestamp and symbol.
_Avoid_: Factor script, trading strategy

**Evaluation Grid** _(retired)_:
Formerly a fixed set of action/threshold/holding-horizon/leverage choices the
evaluator searched on the training set. Retired: parameter selection at the
factor layer is overfitting. Horizon is read from the Decay Profile; all other
trading parameters move to the deployment layer.
_Avoid_: Hyperparameter search, strategy optimization

**Base Factor Model**:
The small, versioned set of already-known return drivers every new factor must
beat — v1: a market proxy (BTC or a broad index, **not** within-universe equal
weight), time-series momentum, volatility, funding/carry. It is the
residualization target for Market Neutralization and Incremental IC.
_Avoid_: Risk model, Barra, factor zoo

**Factor Return Stream**:
The parameter-free per-symbol return series derived from a factor's scores —
`sign(score) × forward_return` (or score-weighted forward return) — used to
compute residual IC and to check orthogonality against the library. The only
"construction" permitted in discovery; carries no free parameters.
_Avoid_: Strategy return, backtest PnL

**Market Neutralization**:
Removing the common crypto market factor from a target before measuring IC, so a
factor is not rewarded for being secretly long market beta. For alts, residualize
against an external proxy (BTC/index); for BTC itself there is no market to
neutralize against, so a BTC signal is inherently a directional market-timing bet
and judged as such. With only 2–3 symbols, never neutralize against the
within-universe equal weight (it degenerates to spread trading).
_Avoid_: Demeaning, beta hedge

**Incremental IC**:
A factor's predictive power **after** residualizing its Factor Return Stream
against the Base Factor Model and the existing library. A factor's value is its
incremental contribution, not its standalone IC.
_Avoid_: Raw IC, standalone IC

**Deflated Significance**:
Statistical significance discounted by the number of candidates evaluated
(multiple-testing correction; deflated Sharpe / t-stat). The denominator comes
from the Trial Registry.
_Avoid_: Raw t-stat, nominal p-value

**Trial Registry**:
The machine-readable count of all factor candidates/configurations evaluated
(including repaired and rejected), used as the denominator for Deflated
Significance. The human-readable research log does not serve this purpose.
_Avoid_: Research log, leaderboard

**Decay Profile**:
IC measured as a function of horizon. It replaces searching a horizon menu: the
natural Holding Horizon is read from where IC peaks/persists, and regime
sensitivity is read from per-window IC dispersion (a diagnostic, not a filter).
_Avoid_: Horizon grid, candidate horizon

**Holding Horizon**:
The future return horizon over which a score is judged. Read from the Decay
Profile, not selected from a grid. It does not define update or rebalance cadence.
_Avoid_: Rebalance frequency, update frequency, input lookback window

**Generalization Gate**:
The out-of-sample requirement that a factor's signal survives Walk-forward
Validation (with Purge/Embargo) and Deflated Significance before being considered
effective. It rejects factors that look good only by in-sample chance or
multiple-testing luck.
_Avoid_: Final score, backtest result

**Research Gate**:
The discovery-stage gate (a pure predicate over statistical evidence) for mining
feedback and Candidate Factor Library intake. It requires: no leakage (input
audit + t+1 + purged/embargoed walk-forward), sufficient coverage, IC sign
stability, IC IR and **deflated** significance, and non-trivial **Incremental
IC**. It uses **no** thresholds, turnover, cost, or break-even diagnostics — those
are deployment-layer.
_Avoid_: Production gate, tradability approval

**Trading Gate**:
The deployment-stage gate: a predicate over a single backtest engine's output for
a **constructed portfolio**. It requires positive cost-adjusted net performance,
acceptable turnover, drawdown, fee/slippage and funding robustness, and risk
validation. Tradability is judged here, on the portfolio — never on a single
factor.
_Avoid_: Research gate, first-pass factor screen, single-factor tradability

**Research Candidate**:
A factor that passes the Research Gate and is retained for further iteration or
eventual portfolio use. It has incremental gross signal but is not, by itself,
tradable or production-ready.
_Avoid_: Production-ready factor, live strategy

**Break-even Fee** _(retired)_:
Formerly the fee level that would consume a factor's gross edge. Retired from
discovery: it requires a turnover/threshold construction to compute, which the
zero-parameter factor layer forbids. Any cost-sensitivity view belongs to the
deployment layer.
_Avoid_: Binance fee, fixed cost assumption

**Candidate Factor Gate** _(legacy)_:
Legacy term for the earlier single first-stage acceptance gate. Use Research Gate (intake) and Trading Gate (tradability).
_Avoid_: Research Gate, Trading Gate

**Strong Factor Gate** _(legacy)_:
Legacy term for the earlier stricter first-stage label. Express strength through Research Gate diagnostics (IC IR, deflated significance, incremental IC) instead.
_Avoid_: Production-ready factor, guaranteed alpha

**Factor Evaluation Report**:
An auditable report for a directional factor: data dependencies, time-series
IC / IC IR per symbol (on market-residual, vol-normalized returns), Decay
Profile, Incremental IC vs base model + library, per-window IC dispersion,
autocorrelation-corrected and **deflated** significance, walk-forward (purged/
embargoed) window metrics, and the Research Gate result. Cost/turnover/net-return
fields belong only to the deployment-side Trading Gate report.
_Avoid_: Backtest summary, leaderboard row

**Candidate Factor Library**:
The first-stage storage for factors that pass the Research Gate. It stores
**signals** (not strategies), including each factor's **Factor Return Stream**,
so intake can enforce orthogonality. Inclusion means the factor is a research
candidate and does not imply Trading Gate approval or permission to trade.
_Avoid_: Production strategy library, alpha book

**IC Stability**:
The requirement that time-series IC (on market-residual, vol-normalized returns)
is consistently signed across **purged/embargoed** walk-forward test windows,
with **autocorrelation-corrected** significance. Stability + Incremental IC +
Deflated Significance matter more than raw IC magnitude.
_Avoid_: High IC, significant IC

**Walk-forward Validation**:
An out-of-sample method that repeatedly trains/validates/tests on time-ordered
rolling windows, with **Purge/Embargo** around each train/test boundary to stop
overlapping-label leakage. First-stage default: 180d train, 30d validation, 30d
test, 30d step — noting that, with co-moving symbols, windows are not independent
and "survived N windows" is weaker evidence than in a broad cross-section.
_Avoid_: Single train/valid/test split, random split

**Purge/Embargo**:
Dropping training samples whose label window overlaps the test period (purge) and
holding out a buffer around the boundary (embargo), required because forward
returns span a horizon and would otherwise leak future information at window
edges.
_Avoid_: Plain rolling split
