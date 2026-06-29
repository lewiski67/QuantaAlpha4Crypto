# QuantaAlpha Crypto — Project Instructions

Crypto-native factor research system targeting Binance. Migrated in-place
from the original Qlib / A-share / daily-frequency QuantaAlpha (now
reference-only under `old/`, gitignored).

## Architecture (do not break)

Active package: `quantaalpha_crypto/`, with one enforced dependency direction:

```
mining/  ->  evaluation/  ->  data.py
```

- `data.py` — Binance local data adapter; builds `CryptoPanel` from spot
  candles, USD-M futures, mark/premium/funding. No downloads, no orders, no Qlib.
- `evaluation/` — pure factor judge: panel build, Factor Callable evaluation,
  fixed Evaluation Grid, walk-forward, Research/Trading gates, reports,
  Candidate Factor Library. **Must not** import `mining/`, call an LLM, or
  generate/repair factors. `tests/test_crypto_module_boundaries.py` guards this.
- `mining/` — LLM orchestration around the evaluator: workspaces, batch runs,
  proposal/repair providers (Anthropic), CLI. Delegates all acceptance to
  `evaluation/`.

Two-layer gates, never collapse them: **Research Gate** (mining intake; gross
signal allowed pre-cost) vs **Trading Gate** (formal tradability; net-positive
after Binance fees/funding/slippage). See `docs/adr/0011-*` and `CONTEXT.md`.

> **Methodology in transition.** The bullets above describe the *current code*.
> The target methodology was overhauled (ADR-0012/0013, `CONTEXT.md`, and
> `docs/design/factor-system-architecture.md`): time-series per-symbol,
> market-neutral, **pure-statistical** discovery with **zero free trading
> parameters** in the factor layer. The "fixed Evaluation Grid" and single-factor
> Sharpe gate are being retired; thresholds/sizing/regime/risk move to a
> deployment layer. Read the design doc before changing `evaluation/`.

## Authoritative references

- `CONTEXT.md` — controlled domain language. Use these exact terms (Effective
  Factor, Directional Factor, Factor Callable, Research/Trading Gate, Crypto
  Panel, Holding Horizon vs Update vs Rebalance Frequency, …). Avoid the listed
  synonyms.
- `docs/adr/` — architecture decisions (13 ADRs; 0012 = paradigm, 0013 =
  purge/embargo are the current methodology). Read before changing evaluation
  methodology. `docs/design/factor-system-architecture.md` is the authoritative
  target design.
- PRDs and task breakdowns live as **GitHub Issues** (via `gh`), not local
  files — see `docs/agents/issue-tracker.md`. Use `to-prd`/`to-issues` and
  publish there; do not re-create `docs/prd/` or `docs/tasks/`.
- `docs/research/` — tested & queued research directions; check before
  proposing a new one.
- `quantaalpha_crypto/README.md` — module roles + research-direction template.

## Commands

Run tests:

```bash
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -o cache_dir=/tmp/pytest_cache_quantaalpha tests -q
```

Mining CLI:

```bash
python -m quantaalpha_crypto.mining.cli --config configs/crypto_original_flow_smoke.example.json --output-dir artifacts/
```

## Working conventions

- Current task state, next steps, and open decisions live in `docs/HANDOFF.md`.
  Read it at the start of a session; **update it after every meaningful
  checkpoint** (commit, decision, convention change) — unconditionally, regardless
  of task size.
- Default branch is `main`. The crypto migration already lives here.
- `old/` and `/artifacts/` are gitignored — never re-add them or import from `old/`.
- Packaging is `quantaalpha-crypto` (`pyproject.toml`), entry point
  `quantaalpha_crypto.mining.cli:main`. Keep these aligned with the package.
- Prefer importing from the explicit module (`quantaalpha_crypto.evaluation`,
  `quantaalpha_crypto.mining`) over the top-level re-exports when role matters.
- PRDs and task breakdowns go to **GitHub Issues** via `to-prd`/`to-issues` +
  `gh` — do not create local `docs/prd/` or `docs/tasks/` files. Use
  selectively: only for new subsystems or genuinely uncertain scope. Routine
  refactors, bugfixes, and small features go straight to implementation with a
  one-line HANDOFF entry.

## Known cleanup debt (not yet fixed)

- Shared metric primitives live in `evaluation/metrics.py` and shared mining
  helpers in `mining/_utils.py` — use those, do not re-inline `_simple_sharpe`,
  `_forward_returns`, `_redact_secrets`, `_progress`, etc. `_simple_sharpe` uses
  grid semantics (empty -> NaN, zero-vol loss -> -inf); keep it that way.
- Prompts are hardcoded in `mining/llm_provider.py`; original convention was a
  `prompts.yaml`.
- `tests/` filename prefixes are inconsistent (`test_crypto_*` / `test_factor_*`
  / `test_binance_*`); prefer `test_<module>.py`.

## Agent skills

- Issues: GitHub Issues; external PRs are a triage surface. See `docs/agents/issue-tracker.md`.
- Triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.
- Domain docs: single-context layout. See `docs/agents/domain.md`.
