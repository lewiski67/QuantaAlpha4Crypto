import json

import pytest

from quantaalpha_crypto import create_crypto_factor_workspace


def test_crypto_factor_workspace_creates_manifest_and_artifact_paths(tmp_path):
    workspace = create_crypto_factor_workspace(
        output_dir=tmp_path,
        run_id="run_001",
        crypto_data_universe={
            "feature_data": ["binance_spot_1m_ohlcv"],
            "pnl_data": ["binance_futures_1m_mark"],
        },
    )

    assert workspace.root == tmp_path / "run_001"
    assert workspace.reports_dir == workspace.root / "reports"
    assert workspace.rejected_dir == workspace.root / "rejected"
    assert workspace.factor_artifacts_dir == workspace.root / "factor_artifacts"
    assert workspace.candidate_library_path == workspace.root / "candidate_factors.json"
    assert workspace.manifest_path == workspace.root / "manifest.json"
    assert workspace.reports_dir.is_dir()
    assert workspace.rejected_dir.is_dir()
    assert workspace.factor_artifacts_dir.is_dir()
    assert workspace.candidate_library_path.exists()

    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    assert manifest == {
        "artifact_type": "crypto_factor_workspace",
        "run_id": "run_001",
        "live_strategy": False,
        "summary": "Research artifact workspace for crypto factor mining.",
        "crypto_data_universe": {
            "feature_data": ["binance_spot_1m_ohlcv"],
            "pnl_data": ["binance_futures_1m_mark"],
        },
        "artifact_paths": {
            "reports_dir": "reports",
            "rejected_dir": "rejected",
            "factor_artifacts_dir": "factor_artifacts",
            "candidate_library": "candidate_factors.json",
        },
    }
    assert "live strategy" not in json.dumps(manifest).lower()


def test_crypto_factor_workspace_creation_is_deterministic(tmp_path):
    first = create_crypto_factor_workspace(
        output_dir=tmp_path,
        run_id="run_001",
        crypto_data_universe={"feature_data": [], "pnl_data": []},
    )
    second = create_crypto_factor_workspace(
        output_dir=tmp_path,
        run_id="run_001",
        crypto_data_universe={"feature_data": [], "pnl_data": []},
    )

    assert first == second
    assert first.manifest_path.read_text(encoding="utf-8") == second.manifest_path.read_text(
        encoding="utf-8"
    )


def test_crypto_factor_workspace_rejects_run_id_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="run_id"):
        create_crypto_factor_workspace(
            output_dir=tmp_path,
            run_id="../escape",
            crypto_data_universe={"feature_data": [], "pnl_data": []},
        )
