# Model Binance-specific trading costs

The crypto factor evaluator will model trading costs for Binance specifically, preferring account-level or symbol-level fees and historical funding where available, with conservative public defaults only as a fallback. This keeps backtests aligned with the intended execution venue and avoids validating factors under exchange-agnostic cost assumptions that may not survive real Binance spot or USD-margined perpetual trading.
