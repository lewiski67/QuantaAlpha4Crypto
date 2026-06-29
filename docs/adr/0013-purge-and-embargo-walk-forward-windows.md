# Purge and embargo walk-forward windows

Date: 2026-06-29
Status: Accepted
Amends: ADR-0002 (walk-forward validation), ADR-0003 (180d/30d/30d windows)
Reference: `docs/design/factor-system-architecture.md` §3.5

## Context

Forward-return labels span a holding horizon `h`. In a plain rolling
train/validation/test split, training samples whose label window overlaps the
test period share information with the test set, and samples adjacent to the
train/test boundary are autocorrelated with it. Both leak future information at
window edges and inflate apparent out-of-sample performance. ADR-0002/0003
specified the rolling windows but not this correction.

Separately, overlapping forward returns are autocorrelated by construction, so
the effective independent sample is far smaller than the row count, and naive
t-stats overstate significance.

## Decision

Walk-forward validation must:

- **Purge** training samples whose label window `[t, t+h]` overlaps the
  validation/test period.
- **Embargo** a buffer of length on the order of `h` immediately after each
  train/test boundary, excluding those samples from training.
- Compute significance with **autocorrelation-corrected** estimators
  (Newey-West or block bootstrap), not naive t-stats.

The 180d/30d/30d/30d-step defaults from ADR-0003 stand, with the caveat that, for
co-moving symbols, windows are not independent and "survived N windows" is weaker
evidence than in a broad cross-section.

## Consequences

- `evaluation/walk_forward.py` gains purge + embargo around boundaries.
- `evaluation/metrics.py` gains autocorrelation-corrected significance helpers.
- `IC Stability` and `Walk-forward Validation` in `CONTEXT.md` are updated to
  require Purge/Embargo and corrected significance.
