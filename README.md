# QuantaAlpha Crypto

Standalone crypto strategy candidate mining and evaluation project.

The active package is:

```text
quantaalpha_crypto/
```

The original QuantaAlpha project has been moved under:

```text
old/quantaalpha_original/
```

`old/` is reference-only. Runtime code, tests, and packaging should not import from it.

## Main Entry Points

Run the crypto mining CLI:

```bash
python -m quantaalpha_crypto.mining.cli --config configs/crypto_original_flow_smoke.example.json --output-dir artifacts/
```

Installed console command:

```bash
quantaalpha-crypto --config configs/crypto_original_flow_smoke.example.json --output-dir artifacts/
```

## Current Architecture

See:

- `strategy_core_architecture_plan.md`
- `dynamic_threshold_methods.md`
- `quantaalpha_crypto/README.md`

## Tests

```bash
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -o cache_dir=/tmp/pytest_cache_quantaalpha tests -q
```
