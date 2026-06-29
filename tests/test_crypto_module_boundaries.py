import ast
from pathlib import Path


def test_crypto_mining_modules_do_not_import_private_evaluation_symbols():
    mining_files = Path("quantaalpha_crypto/mining").glob("*.py")
    offenders = []
    for path in mining_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.startswith("quantaalpha_crypto.evaluation")
                and any(alias.name.startswith("_") for alias in node.names)
            ):
                offenders.append(str(path))

    assert offenders == []


def test_quantaalpha_crypto_runtime_does_not_import_legacy_crypto_package():
    runtime_files = list(Path("quantaalpha_crypto").glob("**/*.py"))
    offenders = [
        str(path)
        for path in runtime_files
        if "quantaalpha.crypto" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
