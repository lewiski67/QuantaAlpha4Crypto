# Strategy Core Architecture Plan

> **Superseded (methodology) by `docs/design/factor-system-architecture.md`.**
> This earlier plan assumes cross-sectional evaluation, threshold/grid search in
> the evaluator, and an explicit regime filter — all overturned by the
> time-series, zero-free-parameter paradigm (ADR-0012). Retained for the layer
> split (data / factor / strategy core / runner adapters), the strategy-candidate
> schema, and the Coinbase venue-migration note, which remain useful. Where this
> file conflicts with `factor-system-architecture.md`, the latter wins.

## Goal

Build the crypto mining/evaluation stack around a reusable strategy core.

The evaluator, future full backtester, and future live trading runner should reuse the same decision logic instead of reimplementing signal, regime, sizing, and risk behavior separately.

## Target Pipeline

```text
Data
  -> Factor Generator / Factor Calculator
  -> Strategy Core
     - Signal Rule
     - Regime Filter
     - Position Sizing
     - Risk Manager
     - Target Position / Order Intent
  -> Runner Adapter
     - Evaluator Runner
     - Backtest Runner
     - Live Trading Runner
```

## Recommended Project Structure

```text
repo_root/
  pyproject.toml
  README.md
  AGENTS.md

  configs/
  docs/
  scripts/
  tests/
  artifacts/

  quantaalpha_crypto/
    __init__.py
    cli.py

    data/
      adapters.py
      panel.py
      universe.py

    factors/
      generator.py
      calculator.py
      validation.py

    strategy/
      candidate.py
      decision.py
      signal.py
      regime.py
      sizing.py
      risk.py

    evaluation/
      runner.py
      grid.py
      report.py
      library.py

    backtest/
      runner.py
      accounting.py
      execution.py

    live/
      runner.py
      exchange.py
      reconciliation.py

    mining/
      proposal.py
      repair.py
      round.py
      workspace.py

  old/
    quantaalpha_original/
```

`data/` owns clean, aligned, product-prefixed crypto market data and the complete-history universe policy.

`factors/` owns factor generation, factor calculation, and future-dependency validation. It outputs factor scores, not trades.

`strategy/` is the reusable strategy core. It turns factor scores into decisions through signal rules, regime filters, sizing, risk checks, and target position/order intent. This is the shared module used by evaluator, backtest, and live runners.

`evaluation/` is the fast research evaluator. It runs walk-forward/grid screening, computes lightweight event-level PnL, writes reports, and stores strategy candidates.

`backtest/` is the future full portfolio simulator. It should handle capital, positions, overlapping trades, equity curves, margin, liquidation, and realistic execution assumptions.

`live/` is the future real trading adapter. It should read live market/account state, call `strategy/`, submit/cancel orders, and reconcile fills.

`mining/` owns the LLM/research loop: proposal, repair, round orchestration, workspace artifacts, and feedback into the next candidate generation round.

This mirrors the original project's domain split (`factors/`, `backtest/`, `pipeline/`) while separating the crypto system into its own `quantaalpha_crypto` package. `old/` is reference-only: it should not be imported, packaged, or tested. The important design decision is that `strategy/` is the shared decision module, while `evaluation/`, `backtest/`, and `live/` are adapters around it.

## Layer Responsibilities

### 1. Data

Provides clean, aligned, product-prefixed market data.

Responsibilities:

- enforce the complete-history data universe policy
- align timestamp and symbol indexes
- expose product-prefixed fields such as `spot_close` and `futures_close`
- keep incomplete datasets outside the default evaluation universe

Non-responsibilities:

- factor logic
- trading decisions
- risk decisions

### 2. Factor Generator / Factor Calculator

Generates and computes factor scores.

Responsibilities:

- generate candidate factor formulas or Python callables
- compute `score_t = f(data_before_t)`
- enforce input lookback rules
- reject future-dependent factors

Non-responsibilities:

- deciding whether to trade
- deciding position size
- applying portfolio risk constraints

### 3. Strategy Core

Turns factor scores and current state into target trading intent.

The strategy core should not know whether it is running inside evaluator, full backtest, or live trading.

Input:

```text
timestamp
symbol
factor_score
market_state
account_state
strategy_config
```

Output:

```text
target position or order intent
signal metadata
regime metadata
risk metadata
decision reasons
```

Submodules:

```text
Signal Rule
Regime Filter
Position Sizing
Risk Manager
Target Position / Order Intent
```

### 3.1 Signal Rule

Converts factor score into trade intent.

Examples:

```text
score > rolling_quantile(score_history, 0.8) -> long
score < rolling_quantile(score_history, 0.2) -> short
otherwise -> flat
```

Initial implementation:

```text
rolling_quantile threshold
per-symbol history
strict past-only threshold calculation
```

### 3.2 Regime Filter

Controls whether the strategy is allowed under the current market regime.

Initial implementation:

```text
diagnostics only
```

Later implementation:

```text
allow_regime / disable_regime templates
```

Examples:

```text
allow low_vol only
disable high_funding
disable high_vol
allow trend regime only
```

### 3.3 Position Sizing

Converts trade intent into target exposure.

Initial implementation:

```text
fixed_fraction
```

Later implementations:

```text
vol_target_sizing
signal_strength_sizing
fractional_kelly, only if diagnostics justify it
```

### 3.4 Risk Manager

Approves, reduces, or blocks target exposure.

Initial implementation should be conservative and template-based.

Examples:

```text
max_leverage
max_position_fraction
max_daily_loss
max_drawdown_stop
funding_cost_cap
volatility_cap
liquidity_cap
```

Risk manager should not be a free-form LLM-generated module.

### 3.5 Target Position / Order Intent

The strategy core should output target intent, not directly execute trades.

Example output:

```json
{
  "timestamp": "2026-01-01T00:00:00Z",
  "symbol": "BTCUSDT",
  "product": "spot",
  "action": "spot_long",
  "target_position_fraction": 0.1,
  "allowed": true,
  "signal_metadata": {
    "score": 0.91,
    "threshold": 0.83,
    "threshold_method": "rolling_quantile"
  },
  "risk_metadata": {
    "risk_profile": "conservative",
    "blocked_reasons": []
  }
}
```

## Runner Adapters

Runner adapters consume the strategy core output in different execution environments.

### Evaluator Runner

Purpose:

```text
fast factor and strategy-candidate screening
```

Responsibilities:

- run walk-forward evaluation
- compute fast event-level PnL
- apply cost/funding assumptions
- write reports and candidate library entries

Non-responsibilities:

- full account ledger
- exact execution simulation
- exchange API calls

### Backtest Runner

Purpose:

```text
full portfolio/accounting simulation
```

Responsibilities:

- initial capital
- cash and position ledger
- overlapping positions
- equity curve
- drawdown
- margin
- liquidation risk
- realistic execution/slippage assumptions

### Live Trading Runner

Purpose:

```text
real execution
```

Responsibilities:

- read live market/account state
- call strategy core
- generate orders
- submit/cancel/monitor exchange orders
- handle fills, failures, and reconciliation

## Strategy Candidate Schema

The final accepted artifact should be treated as a strategy candidate, not a pure factor.

Recommended structure:

```json
{
  "factor": {
    "name": "momentum_reversion",
    "callable_reference": "...",
    "input_columns": ["spot_close", "spot_volume"],
    "input_lookback_window": "24h"
  },
  "symbol": "BTCUSDT",
  "signal_rule": {
    "method": "rolling_quantile",
    "threshold_quantile": 0.8,
    "threshold_lookback_window": "90d",
    "action": "spot_long",
    "holding_horizon": "4h"
  },
  "position_sizing": {
    "method": "fixed_fraction",
    "fraction": 0.1
  },
  "risk": {
    "profile": "conservative",
    "max_leverage": 1.0,
    "max_position_fraction": 0.1
  },
  "evaluation": {
    "gate_status": "strong",
    "walk_forward_settings": {},
    "cost_model": {},
    "report_reference": "reports/momentum_reversion__BTCUSDT.json"
  }
}
```

## Design Rules

- LLM may generate factor logic.
- LLM should not freely generate signal, regime, sizing, or risk logic in the early system.
- Signal, regime, sizing, and risk should be fixed templates or controlled search spaces.
- The same strategy core should be used by evaluator, full backtester, and live runner.
- Evaluator should not become the permanent home for all trading logic.
- Strategy core should return decisions; runners decide how to simulate or execute those decisions.

## Recommended Implementation Order

### Step 1: Strategy Candidate Schema

Define a structured strategy-candidate artifact that separates:

```text
factor
signal_rule
position_sizing
risk
evaluation
```

### Step 2: Shared Signal Rule

Move threshold logic into a reusable signal module.

Initial method:

```text
per-symbol rolling quantile threshold
```

This also fixes the current whole-window threshold look-ahead issue.

### Step 3: Evaluator Integration

Make the evaluator runner call the shared signal rule instead of computing trade masks directly inside grid evaluation.

### Step 4: Candidate Library Rename / Reshape

Rename or reshape the current candidate factor library into a strategy candidate library.

### Step 5: Minimal Position Sizing

Add fixed-fraction sizing.

Do not add complex sizing before the accounting model exists.

### Step 6: Minimal Risk Manager

Add conservative template-based risk checks:

```text
max_leverage
max_position_fraction
funding cap
volatility cap
```

### Step 7: Regime Diagnostics

Add regime diagnostics before enforcing regime filters.

### Step 8: Full Backtest Runner

Only after the shared strategy core is stable, add full account/equity simulation.

### Step 9: Live Trading Runner

Only after full backtest behavior is consistent with evaluator behavior, add live execution.

## Current Project Implication

The current crypto evaluator already behaves like a lightweight strategy-candidate evaluator.

The next architectural correction is to stop treating the accepted artifact as a pure factor and start representing it as:

```text
factor + signal rule + symbol + sizing/risk templates + evaluation evidence
```

## Pending Venue Migration Note

Future trading may need to move from Binance to Coinbase because of Europe compliance concerns.

Do not hard-code Binance assumptions into the strategy core. Binance-specific behavior should stay in data, cost, execution, and venue adapters.

Potential future target universe:

```text
ETH
SOL
SHIB
```

Coinbase spot fees are likely too high for the intended strategy style, so the default future trading direction should be contracts/derivatives rather than spot. Keep this restriction until the user explicitly says Binance compliance concerns are resolved.

Before implementation, re-audit:

- complete 2024-2026 Coinbase data availability
- Coinbase symbol naming
- spot/perp/futures product availability
- field semantics versus current `spot_*` and `futures_*` columns
- Coinbase fees, slippage, funding/perp assumptions, and execution constraints
