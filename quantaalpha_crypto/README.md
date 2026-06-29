# Crypto-native Modules

`quantaalpha_crypto/` is the standalone crypto strategy research package. It is separated from the original `quantaalpha/` package; the original project should be treated as reference code only once moved under `old/`.

> **Methodology in transition — this README describes the *current* code.** The
> factor-discovery methodology is being overhauled (see
> `docs/design/factor-system-architecture.md`, ADR-0012/0013, `CONTEXT.md`):
> time-series, market-neutral, **pure-statistical** discovery with **zero free
> trading parameters** in the factor layer. The "fixed Evaluation Grid",
> "Candidate/Strong Factor Gate", the "candidate timing grid", and the
> "evaluator handles thresholds / action / holding horizon / leverage" language
> below all reflect the implementation being replaced. The Research Direction
> Template in particular (it shapes LLM proposals) will be rewritten when the
> evaluator is migrated — do not treat its grid/threshold framing as the target.

## Binance Data Adapter

Path: `quantaalpha_crypto/data.py`

Purpose: load local Binance historical data into Crypto Panels.

It owns:

- local CSV OHLCV loading
- Binance spot candle JSONL loading from `candles/<SYMBOL>/<frequency>.jsonl`
- Binance USD-M futures JSONL loading from `external/binance/futures/<SYMBOL>/`
- mark price, premium index, and funding-rate columns for futures research panels
- symbol and time-range filtering
- one-file or multi-file data references
- Feature Data and PnL Data `CryptoPanel` construction
- data dependency metadata for manifests and reports

It does not download live Binance data, place orders, or use Qlib.

## Crypto Evaluation Core

Path: `quantaalpha_crypto/evaluation/`

Purpose: evaluate supplied Directional Factors.

It owns:

- Crypto Panel construction and validation
- Factor Callable evaluation
- fixed Evaluation Grid scoring
- Binance cost and funding accounting
- portfolio-level backtesting for selected factor scores
- Walk-forward Validation
- Candidate Factor Gate and Strong Factor Gate
- Factor Evaluation Reports
- Candidate Factor Library persistence

It does not generate factors, call LLMs, repair code, or orchestrate mining rounds.

## Crypto Mining Automation

Path: `quantaalpha_crypto/mining/`

Purpose: organize mining runs around the Crypto Evaluation Core.

It owns:

- Crypto Factor Workspace creation
- run manifests and artifact paths
- auditable factor artifacts
- crypto source runner for `factor(data)` execution
- batch evaluation of supplied Factor Callables
- rejected diagnostics
- portfolio backtest artifact persistence
- LLM proposal interfaces
- bounded repair loops
- Anthropic Claude proposal and repair providers
- CLI and future pipeline integration

It delegates factor acceptance to the Crypto Evaluation Core.

## Command Paths

Deterministic proving command:

```bash
python -m quantaalpha_crypto.mining.cli --config crypto_round.json --output-dir artifacts/
```

Installed console command:

```bash
quantaalpha-crypto --config crypto_round.json --output-dir artifacts/
```

Original-flow crypto mining command:

```bash
quantaalpha crypto_mine_original --config original_flow_crypto.json
```

`quantaalpha crypto_mine_original` is a compatibility command that forwards to `quantaalpha_crypto`. New code should import and execute `quantaalpha_crypto` directly.

Original-flow configs may include an optional `research_direction`. When present, proposal and repair prompts must stay aligned to that direction, and the direction is recorded in manifests and factor artifacts for provenance.

## Research Direction Template

Use `research_direction` to describe one testable market mechanism, not a generic request to find profitable factors.

Before choosing a new direction, check `docs/research/crypto-research-directions.md` for directions that have already been tested or queued.

The run config is authoritative for data paths, symbols, timing, and evaluation settings. The direction text should mirror those settings so the LLM proposes factors inside the same research boundary.

Use this brief format for new directions:

```text
Research mechanism:
[One falsifiable market mechanism and the expected continuation/reversal direction.]

Venue/product:
[Binance spot or Binance USD-M futures.]

Tradable/evaluated universe:
[Symbols that may be scored for PnL and reports.]

Feature universe:
[Symbols/data sources the factor may read. State "same as tradable universe" unless the config explicitly separates feature_universe from tradable_universe.]

Available fields:
[Exact Crypto Panel columns the factor may read.]

Candidate timing grid:
input_lookback_window candidates: [...]
update_frequency candidates: [...]
rebalance_frequency candidates: [...]
holding_horizon / candidate_horizon candidates: [...]

Timing rationale:
[Why these windows and horizons match this mechanism.]

Preferred factor construction:
[Normalization, interaction terms, conditioning/regime filters, and cost/funding-aware constraints.]

Avoid:
[Unavailable fields, generic templates, future-looking operations, repeated mechanisms, or invalid execution assumptions.]

Evaluation boundary:
[Directional factor only. The evaluator handles action selection, thresholds, holding horizon, leverage, Binance fees, slippage, funding, walk-forward gates, and report/library persistence.]
```

Required elements:

- Research mechanism: one falsifiable behavioral, microstructure, basis/funding, liquidity, or regime hypothesis.
- Venue, product, and universe: Binance spot or USD-M futures, with explicit tradable symbols.
- Feature universe versus tradable universe: say whether they are the same. Until the config supports a separate `feature_universe` and `tradable_universe`, do not ask the model to use extra symbols as context while evaluating only BTCUSDT/SOLUSDT.
- Signal source: exact fields the factor may read from the current Crypto Panel.
- Forecast target: continuation or reversal, with candidate or holding horizon.
- Candidate timing grid: input lookback window, update frequency, rebalance frequency, and holding/candidate horizon candidates.
- Timing rationale: why those windows match the mechanism rather than being copied from a prior example.
- Evaluation boundary: allowed trading actions, cost/funding awareness, and target product for PnL.
- Constraints: unavailable fields, generic templates, repeated directions, and future-looking inputs.

Project-specific guardrails:

- A direction should be falsifiable. It should be possible for a completed walk-forward run to say the mechanism was supported, rejected, or needs a narrower mutation.
- Do not include fields that are not currently loaded into the Crypto Panel. For example, open interest and long-short-ratio endpoints exist on Binance, but they are unavailable to this project until the adapter ingests them.
- Do not mix spot and perpetual PnL assumptions. Spot directions should use spot PnL. USD-M futures directions should include mark/last price, premium, funding, fees, slippage, and allowed perp long/short actions.
- For the current temporary trading scope, tradable/evaluated outputs should remain BTCUSDT and SOLUSDT unless a config explicitly separates feature context from tradable output.
- Avoid broad repeats. If a prior direction was rejected, the next direction should narrow the mechanism, change timing deliberately, add a newly available data source, or define a different regime condition.
- Do not reuse example timing blindly. Choose input lookback, update frequency, rebalance frequency, and holding horizon from the mechanism being tested.

Timing guidance:

| Mechanism family | Typical input lookback | Typical candidate/holding horizon | Notes |
| --- | --- | --- | --- |
| Taker-flow or short liquidity shock | 30min to 24h | 5min to 30min | Short windows keep the signal close to the microstructure event and reduce stale flow effects. |
| Premium or mark-vs-last divergence | 4h to 7d | 15min to 4h | Longer normalization helps identify abnormal basis/premium states, but evaluation cost grows quickly on 1m data. |
| Funding pressure | 3d to 30d or last 3 to 21 funding events | 1h to 24h | Funding is sparse relative to 1m bars, so factors should avoid treating every zero-filled minute as a new funding observation. |
| Volatility or liquidity regime filter | 1d to 14d | Match the underlying mechanism | Regime filters should condition another mechanism, not become a vague standalone direction. |
| Cross-asset context | Depends on added data | Depends on target mechanism | Use only after the config separates `feature_universe` from `tradable_universe`. |

Weak direction:

```text
Find profitable crypto factors.
```

Spot direction example:

```text
Research mechanism:
Test whether abnormal taker-flow and liquidity shocks predict short-horizon continuation or reversal in Binance spot markets.

Venue/product:
Binance spot.

Tradable/evaluated universe:
BTCUSDT, ETHUSDT, and SOLUSDT.

Feature universe:
Same as tradable universe.

Available fields:
open, high, low, close, volume, quote_volume, trade_count, taker_buy_base_volume, taker_buy_quote_volume.

Candidate timing grid:
input_lookback_window candidates: 30min, 2h, 6h, 24h.
update_frequency candidates: 5min, 15min.
rebalance_frequency candidates: 15min, 30min.
holding_horizon / candidate_horizon candidates: 5min, 15min, 30min.

Timing rationale:
Taker-flow and liquidity shocks are expected to decay quickly, so the grid keeps lookbacks and horizons shorter than funding or basis directions.

Preferred factor construction:
Normalize taker imbalance, quote volume, trade-count acceleration, and intrabar range expansion by symbol-specific rolling distributions. Prefer interaction factors that condition price movement on abnormal liquidity/trade-flow states.

Avoid:
Generic close-to-close momentum unless explicitly normalized by volume, trade count, or intrabar range; centered rolling windows; negative shifts; target/forward-return columns; unavailable futures-only fields.

Evaluation boundary:
Generate directional factor candidates only. The evaluator handles spot-long action selection, thresholds, holding horizons, Binance fees, slippage, walk-forward gates, reports, and library persistence.
```

Futures direction example:

```text
Research mechanism:
Test whether one specific crowding mechanism, such as abnormal premium expansion after aggressive taker-buy imbalance, predicts 15-minute to 1-hour mean reversion on Binance USD-M futures.

Venue/product:
Binance USD-M futures.

Tradable/evaluated universe:
BTCUSDT and SOLUSDT.

Feature universe:
Same as tradable universe until explicit feature_universe/tradable_universe split is implemented.

Available fields:
open, high, low, close, volume, quote_volume, trade_count, taker_buy_base_volume, taker_buy_quote_volume, funding_rate, mark_close, premium_close.

Candidate timing grid:
input_lookback_window candidates: 4h, 24h, 3d, 7d.
update_frequency candidates: 5min, 15min.
rebalance_frequency candidates: 15min, 30min.
holding_horizon / candidate_horizon candidates: 15min, 30min, 1h.

Timing rationale:
Premium and mark-vs-last divergence need enough history to define abnormal basis states, while taker-flow pressure is expected to decay faster; this grid tests both without defaulting to pure 7d/15min timing.

Preferred factor construction:
Normalize premium, mark-last divergence, funding pressure, and taker imbalance by symbol-specific rolling distributions. Prefer interaction factors and liquidity/volatility regime conditioning over single-field thresholds.

Avoid:
Open interest, long-short ratio, raw price-only momentum, centered rolling windows, negative shifts, target/forward-return columns, and broad repeats of previously rejected funding/premium templates.

Evaluation boundary:
Generate directional factor candidates only. The evaluator handles perp long/short action selection, thresholds, holding horizons, leverage, Binance fees, slippage, funding, walk-forward gates, reports, and library persistence.
```

The futures example above is a mechanism-specific example, not a default. For pure funding pressure, use an event-aware funding lookback and longer horizons. For pure taker-flow imbalance, start with shorter lookbacks and horizons before spending full walk-forward budget.

Manual real smoke command:

```bash
quantaalpha crypto_mine_real_smoke --config configs/crypto_original_flow_smoke.example.json --allow-live-llm
```

This path is intentionally opt-in and is not required for CI. It requires local Binance data and `ANTHROPIC_API_KEY` in the environment. The config must use `provider="anthropic"` and `repair_provider="anthropic"`.

## Public Interface

The top-level `quantaalpha_crypto` package re-exports the stable public interface for convenience. New code should prefer importing from the explicit module when the module role matters:

```python
from quantaalpha_crypto.evaluation import evaluate_directional_factor
from quantaalpha_crypto.mining import create_crypto_factor_workspace
```
