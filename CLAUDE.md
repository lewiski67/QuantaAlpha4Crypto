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

## Authoritative references

- `CONTEXT.md` — controlled domain language. Use these exact terms (Effective
  Factor, Directional Factor, Factor Callable, Research/Trading Gate, Crypto
  Panel, Holding Horizon vs Update vs Rebalance Frequency, …). Avoid the listed
  synonyms.
- `docs/adr/` — architecture decisions (11 ADRs). Read before changing
  evaluation methodology (grid, walk-forward, cost model, gates).
- `docs/prd/`, `docs/tasks/` — product/task specs. `docs/research/` — tested &
  queued research directions; check before proposing a new one.
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

- Default branch is `main`. The crypto migration already lives here.
- `old/` and `/artifacts/` are gitignored — never re-add them or import from `old/`.
- Packaging is `quantaalpha-crypto` (`pyproject.toml`), entry point
  `quantaalpha_crypto.mining.cli:main`. Keep these aligned with the package.
- Prefer importing from the explicit module (`quantaalpha_crypto.evaluation`,
  `quantaalpha_crypto.mining`) over the top-level re-exports when role matters.

## Known cleanup debt (not yet fixed)

- Duplicated primitives, missing shared modules: `_simple_sharpe`
  (`evaluation/grid.py` + `evaluation/portfolio.py`), `_forward_returns`
  (`grid.py` + `factor.py`), `_redact_secrets` (`mining/proposal.py` +
  `mining/round.py`). Extract to `evaluation/metrics.py` and `mining/_utils.py`.
- Prompts are hardcoded in `mining/llm_provider.py`; original convention was a
  `prompts.yaml`.
- `tests/` filename prefixes are inconsistent (`test_crypto_*` / `test_factor_*`
  / `test_binance_*`); prefer `test_<module>.py`.

## Agent skills

- Issues: GitHub Issues; external PRs are a triage surface. See `docs/agents/issue-tracker.md`.
- Triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.
- Domain docs: single-context layout. See `docs/agents/domain.md`.
