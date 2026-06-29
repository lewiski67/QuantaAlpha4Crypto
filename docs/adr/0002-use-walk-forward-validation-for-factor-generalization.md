# Use walk-forward validation for factor generalization

Status: Amended by `docs/adr/0013-purge-and-embargo-walk-forward-windows.md` (windows must purge + embargo overlapping labels; significance must be autocorrelation-corrected).

We will judge crypto factor generalization with walk-forward validation instead of a single train/validation/test split. This records the deliberate choice to test factors across multiple time-ordered market regimes because crypto market behavior can shift quickly and a single holdout period can make overfit factors look stable.
