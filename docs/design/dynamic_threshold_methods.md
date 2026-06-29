# Dynamic Threshold Methods for Factor Evaluation

## Context

Current factor evaluation should not compute thresholds from the full validation or test window, because that uses future score distribution information that would not be available in live trading.

For any decision timestamp `t`, threshold calculation must only use data available strictly before `t`.

```text
valid:   threshold_t = f(score history before t)
invalid: threshold_t = quantile(all scores inside validation/test window)
```

## 1. Rolling Or Expanding Quantile Threshold

Use a rolling or expanding historical score distribution to compute the threshold.

```text
threshold_t = quantile(score[t - lookback_window : t), q)
trade_t = score_t > threshold_t
```

Important rules:

- Use only past scores.
- Apply `shift(1)` or equivalent logic so `score_t` is not included in its own threshold.
- Compute independently per symbol.

Example:

```text
BTCUSDT threshold history != SOLUSDT threshold history
```

This is the closest replacement for the current whole-window quantile logic.

## 2. Rolling Z-Score Threshold

Normalize the score by its recent mean and volatility.

```text
z_t = (score_t - rolling_mean_{t-1}) / rolling_std_{t-1}
trade_t = z_t > k
```

This is similar in spirit to Bollinger Bands and other rolling volatility bands.

Pros:

- Handles changing score scale.
- Easier to compare across regimes if score distribution is roughly stable after normalization.

Cons:

- Sensitive to outliers.
- Assumes mean/std are meaningful for the score distribution.

## 3. Historical Percentile / Empirical Distribution

Use the historical empirical distribution of the signal to classify the current score.

```text
percentile_t = rank(score_t among historical_scores_before_t)
trade_t = percentile_t > threshold_percentile
```

This is close to rolling quantile, but expresses the signal as a percentile instead of comparing to a raw threshold.

Pros:

- Non-parametric.
- Robust to score units.
- Useful when different factors produce very different numeric scales.

Cons:

- Requires enough history.
- Can be unstable with very short lookback windows.

## 4. Walk-Forward Calibrated Threshold

Use train/validation windows to select threshold hyperparameters, then apply them online in test.

Example hyperparameters:

```text
threshold_quantile = 0.8
threshold_lookback_window = 90d
holding_horizon = 4h
```

Correct workflow:

```text
train/validation: choose q and lookback_window
test: compute threshold_t only from score history before t
```

Incorrect workflow:

```text
validation/test: compute one quantile from the full window and apply it inside that same window
```

This is the recommended structure for our evaluator.

## 5. Regime-Conditioned Threshold

Use different threshold rules under different market regimes.

Example:

```text
low_vol regime:
  threshold_quantile = 0.75

high_vol regime:
  threshold_quantile = 0.90

trend regime:
  allow momentum factors

range regime:
  disable momentum factors
```

Important rule:

```text
regime_t must be computed only from data available before or at t
```

No future volatility, future drawdown, or full-window regime label may be used.

This should be added after the basic rolling threshold is correct.

## 6. Learned Threshold Or Position Sizing

Instead of using a hand-written threshold, train a model to output:

- binary trade / no-trade decision
- long / short / flat action
- continuous position size

Example:

```text
position_t = model(features_before_t)
```

Pros:

- Can learn nonlinear threshold behavior.
- Can adapt to factor interactions and regimes.

Cons:

- Much higher overfitting risk.
- Requires stricter walk-forward validation.
- Harder to diagnose than explicit threshold rules.

This is not the recommended first implementation for the current system.

## Recommended Implementation For This Project

Implement first:

```text
per-symbol rolling quantile threshold
```

Minimum required behavior:

```text
for each symbol:
  for each timestamp t:
    history = scores for the same symbol strictly before t
    threshold_t = history over threshold_lookback_window quantile(q)
    trade_t = score_t > threshold_t
```

Required config additions:

```json
{
  "threshold_quantile": 0.8,
  "threshold_lookback_window": "90d"
}
```

Recommended search grid:

```text
threshold_quantile: 0.7, 0.8, 0.9
threshold_lookback_window: 30d, 60d, 90d, 180d
```

Evaluation rules:

- Thresholds must be computed independently per symbol.
- Thresholds must use only past scores.
- Train/validation/test windows can select hyperparameters, but cannot leak future score distribution.
- The final report should record the selected `threshold_lookback_window`.

## Current System Gap

The current evaluator has already been changed to evaluate factors independently by symbol, but thresholding still needs to be converted from whole-window quantile logic to rolling/online threshold logic.

This is the next required correction before treating evaluator results as live-trading realistic.
