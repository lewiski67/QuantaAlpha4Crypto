# Use 180d/30d/30d walk-forward windows by default

The first-stage crypto factor evaluator will use 180 days for training, 30 days for validation, 30 days for testing, and roll forward by 30 days. This gives each directional factor enough history for parameter selection while requiring repeated out-of-sample survival across changing market regimes.
