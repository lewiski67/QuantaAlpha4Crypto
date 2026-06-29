from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quantaalpha_crypto.evaluation.library import load_candidate_factor_library


@dataclass(frozen=True)
class CryptoFactorWorkspace:
    root: Path
    manifest_path: Path
    reports_dir: Path
    rejected_dir: Path
    factor_artifacts_dir: Path
    candidate_library_path: Path


def create_crypto_factor_workspace(
    output_dir: str | Path,
    run_id: str,
    crypto_data_universe: dict[str, Any],
    candidate_horizons: list[str],
    evaluation_grid: list[dict[str, Any]],
    walk_forward_settings: dict[str, Any],
) -> CryptoFactorWorkspace:
    """Create a deterministic research workspace for one crypto factor mining run."""
    _validate_run_id(run_id)
    root = Path(output_dir) / run_id
    reports_dir = root / "reports"
    rejected_dir = root / "rejected"
    factor_artifacts_dir = root / "factor_artifacts"
    manifest_path = root / "manifest.json"
    candidate_library_path = root / "candidate_factors.json"

    reports_dir.mkdir(parents=True, exist_ok=True)
    rejected_dir.mkdir(parents=True, exist_ok=True)
    factor_artifacts_dir.mkdir(parents=True, exist_ok=True)
    _write_json(candidate_library_path, load_candidate_factor_library(candidate_library_path))
    _write_json(
        manifest_path,
        {
            "artifact_type": "crypto_factor_workspace",
            "run_id": run_id,
            "live_strategy": False,
            "summary": "Research artifact workspace for crypto factor mining.",
            "crypto_data_universe": dict(crypto_data_universe),
            "candidate_horizons": list(candidate_horizons),
            "evaluation_grid": list(evaluation_grid),
            "walk_forward_settings": dict(walk_forward_settings),
            "artifact_paths": {
                "reports_dir": "reports",
                "rejected_dir": "rejected",
                "factor_artifacts_dir": "factor_artifacts",
                "candidate_library": "candidate_factors.json",
            },
        },
    )

    return CryptoFactorWorkspace(
        root=root,
        manifest_path=manifest_path,
        reports_dir=reports_dir,
        rejected_dir=rejected_dir,
        factor_artifacts_dir=factor_artifacts_dir,
        candidate_library_path=candidate_library_path,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, sort_keys=True)
        file.write("\n")


def _validate_run_id(run_id: str) -> None:
    run_path = Path(run_id)
    if (
        not run_id
        or run_path.is_absolute()
        or run_path.name != run_id
        or run_id in {".", ".."}
    ):
        raise ValueError("run_id must be a single relative path segment.")
