from __future__ import annotations

import json
import re

from quantaalpha_crypto.evaluation.portfolio import (
    PortfolioBacktestResult,
    portfolio_backtest_result_to_dict,
)
from quantaalpha_crypto.mining.workspace import CryptoFactorWorkspace


def write_portfolio_backtest_result(
    workspace: CryptoFactorWorkspace,
    result: PortfolioBacktestResult,
    name: str,
) -> str:
    """Persist a portfolio backtest result as a research artifact."""
    reference = _artifact_reference(workspace, name)
    payload = portfolio_backtest_result_to_dict(result)
    payload["artifact_path"] = reference
    path = workspace.root / reference
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, sort_keys=True)
        file.write("\n")
    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("portfolio_backtests", []).append(
        {
            "artifact_type": "portfolio_backtest_reference",
            "name": name,
            "artifact_path": reference,
            "metrics": result.metrics,
            "timing": result.timing,
            "live_strategy": False,
        }
    )
    with workspace.manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, sort_keys=True)
        file.write("\n")
    return reference


def _artifact_reference(workspace: CryptoFactorWorkspace, name: str) -> str:
    artifact_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._-") or "portfolio"
    reference = f"portfolio_backtests/{artifact_stem}.json"
    suffix = 2
    while (workspace.root / reference).exists():
        reference = f"portfolio_backtests/{artifact_stem}_{suffix}.json"
        suffix += 1
    return reference
