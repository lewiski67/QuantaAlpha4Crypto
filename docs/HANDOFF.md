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
- Root design notes moved to `docs/design/`. `dynamic_threshold_methods.md` later
  deleted (obsolete under the new paradigm — no thresholds in discovery).
  `strategy_core_architecture_plan.md` kept (superseded on methodology, retained
  for deployment-layer detail). `CLAUDE.md` updated with PRD/HANDOFF conventions.
- **Methodology overhaul decided AND documented** (see
  `docs/design/factor-system-architecture.md`). Time-series (per-symbol) not
  cross-sectional; pure statistical screening (no grid/threshold/strategy-Sharpe
  at the factor layer); market neutralization (external BTC/index proxy) +
  autocorrelation-corrected t-stats + walk-forward purge/embargo;
  orthogonality/incremental-IC intake against a new Base Factor Model;
  multiple-testing deflation via a Trial Registry. Thresholds, sizing, regime,
  risk all move to a future portfolio-construction layer (regime dissolves into
  the risk model, no explicit filter). **NautilusTrader is the committed single
  backtest/live engine** (decided 2026-06-29; not for discovery; promote to an
  ADR when that layer is built). Improved evolutionary search is designed but
  deferred (design doc §3.12).
- **Docs aligned to the new paradigm** (pending commit): wrote **ADR-0012**
  (paradigm) and **ADR-0013** (purge/embargo); marked ADR-0001/0002/0003/0009/0011
  superseded/amended; rewrote `CONTEXT.md`; banners on the two old design docs;
  `CLAUDE.md` + research log noted as in-transition. Code is NOT yet changed —
  `evaluation/` still has the old grid/gates; the docs now describe the target.

## Next steps (priority order)

Methodology track (the big one — follow `docs/design/factor-system-architecture.md` §5).
Docs/ADRs are now done; remaining work is code. **User's chosen entry point: the
factor generation/evaluation loop (discovery)** — i.e. steps 1–2 below.
**Decided:** scaffold the propose→evaluate→feedback loop, but wire its evaluate
ring to the NEW statistical evaluation (steps 1–2), not to the old `grid.py`/
`gates.py`. Do not get the loop green on old eval and swap later — the feedback
would be old-paradigm and untrustworthy. (Design doc §5, "On the mining loop".)

1. Fix discovery correctness: t+1 execution, vol-normalized label, market
   neutralization (needs a minimal Base Factor Model), autocorr-corrected
   t-stats, walk-forward purge/embargo. Subsumes the old threshold look-ahead item.
2. Rewrite Research Gate to a pure-statistical predicate (drop strategy-Sharpe
   clauses, add deflation via a Trial Registry); harden library intake with
   orthogonality on stored factor return streams.
3. Build out the deployment layer (portfolio construction → Trading Gate
   predicate → single NautilusTrader engine) only after discovery is correct.

Housekeeping track (independent, small):

4. Move prompts out of `mining/llm_provider.py` into a `prompts.yaml`.
5. Normalize `tests/` filenames to `test_<module>.py`.

## Open decisions

- **Rename the project?** "QuantaAlpha" is inherited from the dead A-share/Qlib
  system this no longer resembles. Not wrong semantically (quant + alpha), but
  creates a "same product as old QuantaAlpha" false impression. Deferred: a
  rename is high-cost, zero-functional-value churn (package name, pyproject,
  console script, CLI command names, repo dir, git remote, all docs/tests).
  Re-evaluate **after the methodology migration lands**, as one deliberate pass —
  not now, where it would tangle with the evaluation/ rewrite.
- Whether to delete the merged `crypto-migration` branch (already in `main`).
- Whether the removed Codex `engineering-workflow` skill is worth recovering
  (recoverable: `git show 92b40de:.codex/skills/engineering-workflow/SKILL.md`).

## Known cleanup debt

Tracked in `CLAUDE.md` under "Known cleanup debt". Keep the two in sync: this
file holds the *plan/status*, `CLAUDE.md` holds the *standing list*.
