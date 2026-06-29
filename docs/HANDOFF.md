# Handoff / Current Status

Living document for seamless project continuity. Update at meaningful
checkpoints (not every turn): when task state, decisions, or next steps change.
Stable facts (architecture, conventions, commands) belong in `CLAUDE.md`, not here.

_Last updated: 2026-06-29_

## Current state

- Crypto migration landed on `main`. Local `main` is **3 commits ahead of
  `origin/main`, not yet pushed**:
  - `c96379d` Rewrite CLAUDE.md for Claude Code handover
  - `8ce9a92` Hand project to Claude Code; drop Codex tooling
  - `92b40de` Migrate to crypto-native package (quantaalpha_crypto)
- Project handed from Codex to Claude Code. `.codex/` and empty `.agents/`
  removed; `AGENTS.md` renamed to `CLAUDE.md`.
- `old/` (original QuantaAlpha) and `/artifacts/` are gitignored, reference-only.
- Working tree is clean.

## Next steps (priority order)

1. `git push origin main` (outward action — confirm before pushing).
2. Pay down duplicate-code debt: extract `evaluation/metrics.py`
   (`_simple_sharpe`, `_forward_returns`, `_rank_ic`, `_max_drawdown`,
   annualization) and `mining/_utils.py` (`_redact_secrets`, `_progress`).
   The duplicated `_redact_secrets` is the riskiest (secret-leak surface).
3. Move prompts out of `mining/llm_provider.py` into a `prompts.yaml`.
4. Normalize `tests/` filenames to `test_<module>.py` (currently mixed
   `test_crypto_*` / `test_factor_*` / `test_binance_*`).
5. Optional: move root design notes into `docs/design/`
   (`strategy_core_architecture_plan.md`, `dynamic_threshold_methods.md`);
   `CONTEXT.md` could move under `docs/` too.

## Open decisions

- Whether to delete the merged `crypto-migration` branch (already in `main`).
- Whether the removed Codex `engineering-workflow` skill is worth recovering
  (recoverable: `git show 92b40de:.codex/skills/engineering-workflow/SKILL.md`).

## Known cleanup debt

Tracked in `CLAUDE.md` under "Known cleanup debt". Keep the two in sync: this
file holds the *plan/status*, `CLAUDE.md` holds the *standing list*.
