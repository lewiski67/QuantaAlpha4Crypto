# Handoff / Current Status

> **每日任务在 [`docs/PLAN.md`](PLAN.md)。** 新会话开始时先读那里，再回来看本文背景。

Living document for seamless project continuity. Update at meaningful
checkpoints (not every turn): when task state, decisions, or next steps change.
Stable facts (architecture, conventions, commands) belong in `CLAUDE.md`, not here.

_Last updated: 2026-06-30_

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
- **Docs aligned to the new paradigm** (committed `e29465c`): wrote **ADR-0012**
  (paradigm) and **ADR-0013** (purge/embargo); marked ADR-0001/0002/0003/0009/0011
  superseded/amended; rewrote `CONTEXT.md`; banners on the two old design docs;
  `CLAUDE.md` + research log noted as in-transition. Code is NOT yet changed —
  `evaluation/` still has the old grid/gates; the docs now describe the target.
- **全生命周期计划写定**（`docs/PLAN.md`）：螺旋迭代 0–4 → ★RC → Phase D–F。
  当前在**迭代 0（行走骨架）**，尚未开始。

## Next steps

见 **`docs/PLAN.md`** — 当前迭代任务、验收标准、完整路线图均在那里。

关键决策备忘（不在 PLAN.md 里的）：
- propose→evaluate→feedback 循环必须接新统计评估（迭代 0–2），**不能先接旧
  `grid.py`/`gates.py` 让 loop 跑通再换**——旧 eval 产生的 feedback 本身是错的。

PLAN 增补（2026-06-30，多 horizon 评估 + 经济先验定位，未写代码）：
- 迭代 1 加 **1.5 多 horizon 评估编排**（`factor.py` 吃 `horizons` 网格返回整条 profile，
  不塌缩单点）；1.4 标注 **horizon 网格取值未定**（须按 crypto 机制尺度自定）。
- 多 horizon 纪律写明：评估≠max-over-horizon≠固定单 horizon；horizon 是因子假设的一部分，
  用「连续宽带 vs 孤立尖峰」判真伪；终审在迭代 4 扣成本组合夏普。
- 迭代 2 接上缺口：衰减曲线扫的每个 horizon **计入 Trial Registry / deflation**；
  **经济先验不建模块**——只记录事前 metadata（`mining/proposal.py`→`registry.py`/`library.py`）
  + 声明 vs 实测 horizon 一致性检查（`gates.py`）；真机制判断停 RC 人工门，evaluation 不调 LLM。
- 执行间隔（t+1 进场，标签 `close[t+1+horizon]/close[t+1]-1`）已实现（2026-06-30）：
  `_forward_returns` 加 `execution_lag_bars=1` 默认参数（positional entry + time-based exit）；
  `evaluate_directional_factor` 透传。70 tests 全绿。**迭代 0.1 完成。**
  旧测试（测 IC/alignment index/trailing window 等）显式传 `execution_lag_bars=0` 保留原语义。

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
