# Handoff / Current Status

Living document for seamless project continuity. Update at meaningful
checkpoints (not every turn): when task state, decisions, or next steps change.
Stable facts (architecture, conventions, commands) belong in `CLAUDE.md`, not here.

_Last updated: 2026-06-29_

## Current state

- Crypto migration landed on `main` and is **pushed to `origin/main`**.
- Project handed from Codex to Claude Code. `.codex/` and empty `.agents/`
  removed; `AGENTS.md` renamed to `CLAUDE.md`.
- Duplicate-code debt paid down (commits `3e7e962`, `8986586`): shared helpers
  now live in `mining/_utils.py` (`_redact_secrets`, `_progress`) and
  `evaluation/metrics.py` (`_simple_sharpe`, `_forward_returns`, `_rank_ic`,
  `_max_drawdown`, `_annualization_factor`). `_simple_sharpe` unified on grid
  semantics per user decision (empty -> NaN, zero-vol loss -> -inf); this
  changed portfolio backtest sharpe for degenerate cases.
- 102 tests pass. `old/` and `/artifacts/` gitignored, reference-only.
- Local `docs/prd/` and `docs/tasks/` removed — Codex-era deviation; PRDs and
  task breakdowns now go to GitHub Issues via `to-prd`/`to-issues` + `gh`.
  Recover from git `92b40de` if needed.
- Root design notes moved to `docs/design/` (`dynamic_threshold_methods.md`,
  `strategy_core_architecture_plan.md`). `CLAUDE.md` updated with PRD/HANDOFF
  conventions. Pending commit.

## Next steps (priority order)

1. Move prompts out of `mining/llm_provider.py` into a `prompts.yaml`.
2. Normalize `tests/` filenames to `test_<module>.py` (currently mixed
   `test_crypto_*` / `test_factor_*` / `test_binance_*`).
3. Fix threshold look-ahead gap: `dynamic_threshold_methods.md` documents that
   the evaluator still uses whole-window quantile thresholds (look-ahead bias).
   Needs per-symbol rolling quantile threshold before results are live-realistic.

## Open decisions

- Whether to delete the merged `crypto-migration` branch (already in `main`).
- Whether the removed Codex `engineering-workflow` skill is worth recovering
  (recoverable: `git show 92b40de:.codex/skills/engineering-workflow/SKILL.md`).

## Known cleanup debt

Tracked in `CLAUDE.md` under "Known cleanup debt". Keep the two in sync: this
file holds the *plan/status*, `CLAUDE.md` holds the *standing list*.
