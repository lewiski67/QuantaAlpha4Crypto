# Use 180d/30d/30d walk-forward windows by default

Status: Amended by `docs/adr/0013-purge-and-embargo-walk-forward-windows.md`. The windows stand, but require purge + embargo at boundaries; note that co-moving symbols make windows non-independent, weakening "survived N windows" as evidence. "Parameter selection" below is superseded by ADR-0012 (no factor-layer parameter selection).

The first-stage crypto factor evaluator will use 180 days for training, 30 days for validation, 30 days for testing, and roll forward by 30 days. This gives each directional factor enough history for parameter selection while requiring repeated out-of-sample survival across changing market regimes.
