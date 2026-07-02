import json
import subprocess
import sys
import tomllib
from pathlib import Path

from quantaalpha_crypto.mining.cli import (
    _build_proposal_provider,
    _build_repair_provider,
    main as crypto_mine_main,
    original_flow_main,
    real_smoke_main,
)
from quantaalpha_crypto.mining.llm_provider import (
    AnthropicCryptoFactorProposalProvider,
    AnthropicCryptoFactorRepairProvider,
)


def test_crypto_mining_cli_runs_fake_local_round_from_config(tmp_path):
    config_path = tmp_path / "crypto_round.json"
    output_dir = tmp_path / "artifacts"
    config_path.write_text(
        json.dumps(
            {
                "run_id": "cli_round",
                "crypto_data_universe": {
                    "feature_data": ["fixture_spot_1m_ohlcv"],
                    "pnl_data": ["fixture_spot_1m_ohlcv"],
                },
                "candidate_horizon": "1min",
                "feature_data_dependencies": ["fixture_spot_1m_ohlcv"],
                "pnl_data_dependencies": ["fixture_spot_1m_ohlcv"],
                "max_repair_attempts": 1,
                "input_lookback_window": "2min",
                "provider": "fake",
                "repair_provider": "fake",
                "fixture": "deterministic_spot_1m",
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "quantaalpha_crypto.mining.cli",
            "-c",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "workspace:" in completed.stdout
    assert (output_dir / "cli_round" / "manifest.json").exists()
    assert (output_dir / "cli_round" / "candidate_factors.json").exists()
    assert (output_dir / "cli_round" / "reports" / "momentum__BTCUSDT.json").exists()
    assert (output_dir / "cli_round" / "reports" / "momentum__ETHUSDT.json").exists()
    assert (output_dir / "cli_round" / "rejected" / "broken__BTCUSDT.json").exists()
    assert (output_dir / "cli_round" / "rejected" / "broken__ETHUSDT.json").exists()


def test_crypto_mining_cli_exits_nonzero_on_invalid_config(tmp_path):
    config_path = tmp_path / "invalid.json"
    config_path.write_text("{}", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "quantaalpha_crypto.mining.cli",
            "-c",
            str(config_path),
            "--output-dir",
            str(tmp_path / "artifacts"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "Invalid crypto mining config" in completed.stderr
    assert "run_id" in completed.stderr


def test_crypto_mining_cli_main_accepts_fire_style_keyword_arguments(tmp_path):
    config_path = tmp_path / "crypto_round.json"
    output_dir = tmp_path / "artifacts"
    config_path.write_text(
        json.dumps(
            {
                "run_id": "fire_round",
                "crypto_data_universe": {
                    "feature_data": ["fixture_spot_1m_ohlcv"],
                    "pnl_data": ["fixture_spot_1m_ohlcv"],
                },
                "candidate_horizon": "1min",
                "feature_data_dependencies": ["fixture_spot_1m_ohlcv"],
                "pnl_data_dependencies": ["fixture_spot_1m_ohlcv"],
                "max_repair_attempts": 1,
                "input_lookback_window": "2min",
                "provider": "fake",
                "repair_provider": "fake",
                "fixture": "deterministic_spot_1m",
            }
        ),
        encoding="utf-8",
    )

    assert crypto_mine_main(config=str(config_path), output_dir=str(output_dir)) == 0
    assert (output_dir / "fire_round" / "manifest.json").exists()


def test_crypto_mining_cli_can_construct_anthropic_providers():
    config = {
        "provider": "anthropic",
        "repair_provider": "anthropic",
        "model": "claude-opus-4-8",
        "anthropic_timeout_seconds": 600,
    }

    proposal_provider = _build_proposal_provider(config)
    repair_provider = _build_repair_provider(config)

    assert isinstance(proposal_provider, AnthropicCryptoFactorProposalProvider)
    assert isinstance(repair_provider, AnthropicCryptoFactorRepairProvider)
    assert proposal_provider.model == "claude-opus-4-8"
    assert repair_provider.model == "claude-opus-4-8"
    assert proposal_provider.max_tokens == 64000
    assert repair_provider.max_tokens == 64000
    assert proposal_provider.effort == "max"
    assert repair_provider.effort == "max"
    assert proposal_provider.completion_client.timeout_seconds == 600
    assert repair_provider.completion_client.timeout_seconds == 600


def test_crypto_mining_original_flow_cli_runs_fake_provider_with_binance_adapter(tmp_path):
    data_path = tmp_path / "binance.csv"
    data_path.write_text(
        "\n".join(
            [
                "timestamp,symbol,open,high,low,close,volume",
                "2026-01-01 00:00:00,BTCUSDT,100,100,100,100,10",
                "2026-01-01 00:00:00,ETHUSDT,100,100,100,100,10",
                "2026-01-01 00:01:00,BTCUSDT,110,110,110,110,10",
                "2026-01-01 00:01:00,ETHUSDT,90,90,90,90,10",
                "2026-01-01 00:02:00,BTCUSDT,121,121,121,121,10",
                "2026-01-01 00:02:00,ETHUSDT,81,81,81,81,10",
                "2026-01-01 00:03:00,BTCUSDT,133.1,133.1,133.1,133.1,10",
                "2026-01-01 00:03:00,ETHUSDT,72.9,72.9,72.9,72.9,10",
            ]
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "original_flow.json"
    output_dir = tmp_path / "artifacts"
    config_path.write_text(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "run_id": "original_cli_round",
                "data_adapter": {
                    "data_path": str(data_path),
                    "symbols": ["BTCUSDT", "ETHUSDT"],
                    "frequency": "1min",
                    "product_type": "spot",
                    "dependency_name": "binance_fixture_1m",
                },
                "provider": "fake",
                "repair_provider": "fake",
                "candidate_horizon": "1min",
                "input_lookback_window": "4h",
                "update_frequency": "15min",
                "rebalance_frequency": "1h",
                "max_repair_attempts": 1,
            }
        ),
        encoding="utf-8",
    )

    assert original_flow_main(config=str(config_path)) == 0

    run_dir = output_dir / "original_cli_round"
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mining_round"]["status"] == "completed"
    assert manifest["proposal_runs"][0]["context"]["input_lookback_window"] == "4h"
    assert (run_dir / "candidate_factors.json").exists()
    momentum_report = json.loads((run_dir / "reports" / "momentum__BTCUSDT.json").read_text(encoding="utf-8"))
    # New paradigm: report has ic/rank_ic instead of walk_forward_windows
    assert "ic" in momentum_report
    assert "rank_ic" in momentum_report


def test_pyproject_exposes_standalone_crypto_cli():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["quantaalpha-crypto"] == "quantaalpha_crypto.mining.cli:main"


def test_real_smoke_cli_requires_explicit_live_llm_allowance(tmp_path):
    config_path = tmp_path / "smoke.json"
    config_path.write_text(
        json.dumps(
            {
                "output_dir": str(tmp_path / "artifacts"),
                "run_id": "manual_real_smoke",
                "data_adapter": {
                    "data_path": str(tmp_path / "binance.csv"),
                    "symbols": ["BTCUSDT"],
                    "frequency": "1min",
                },
                "provider": "anthropic",
                "repair_provider": "anthropic",
                "candidate_horizon": "1min",
                "input_lookback_window": "4h",
                "update_frequency": "15min",
                "rebalance_frequency": "1h",
                "max_repair_attempts": 1,
            }
        ),
        encoding="utf-8",
    )

    assert real_smoke_main(config=str(config_path), allow_live_llm=False) == 1


def test_real_smoke_cli_rejects_non_anthropic_config_before_live_call(tmp_path):
    config_path = tmp_path / "smoke.json"
    config_path.write_text(
        json.dumps(
            {
                "output_dir": str(tmp_path / "artifacts"),
                "run_id": "manual_real_smoke",
                "data_adapter": {
                    "data_path": str(tmp_path / "binance.csv"),
                    "symbols": ["BTCUSDT"],
                    "frequency": "1min",
                },
                "provider": "fake",
                "repair_provider": "fake",
                "candidate_horizon": "1min",
                "input_lookback_window": "4h",
                "update_frequency": "15min",
                "rebalance_frequency": "1h",
                "max_repair_attempts": 1,
            }
        ),
        encoding="utf-8",
    )

    assert real_smoke_main(config=str(config_path), allow_live_llm=True) == 1
