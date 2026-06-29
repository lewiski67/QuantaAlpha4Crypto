# Use walk-forward validation for factor generalization

We will judge crypto factor generalization with walk-forward validation instead of a single train/validation/test split. This records the deliberate choice to test factors across multiple time-ordered market regimes because crypto market behavior can shift quickly and a single holdout period can make overfit factors look stable.
