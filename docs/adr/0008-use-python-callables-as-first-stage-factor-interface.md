# Use Python callables as the first-stage factor interface

Directional factors will initially use a Python callable interface: `factor(panel) -> score Series[(timestamp, symbol)]`. This keeps factor generation separate from trading-rule selection, lets hand-written and LLM-generated factors share one contract, and allows the evaluator to enforce no-lookahead, fixed-grid parameter selection, Binance cost modeling, and walk-forward validation consistently.
