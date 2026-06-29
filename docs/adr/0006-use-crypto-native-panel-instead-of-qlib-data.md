# Use a crypto-native panel instead of Qlib data

The refactored system will use a timestamp-by-symbol crypto panel as its canonical data representation instead of adapting Binance and macro data into Qlib's daily stock format. This is a deliberate boundary change: QuantaAlpha's LLM-driven factor generation ideas may be reused, but the data and evaluation layers need crypto-native support for minute bars, spot and perpetual products, funding, Binance costs, and walk-forward trading evaluation.
