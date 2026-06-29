# Separate feature data from PnL data

The crypto factor system will allow all available historical data to be used as feature data, but PnL must be computed from product-specific Binance execution data. Spot strategies use Binance spot price data, while USD-margined perpetual long and short strategies require futures or mark price data plus funding; spot candles must not be silently reused as perpetual PnL data.
