from pathlib import Path

import pytest

from quantaalpha_crypto import (
    OriginalFlowCryptoMiningRunConfig,
    parse_original_flow_crypto_mining_run_config,
)


def test_original_flow_crypto_mining_config_parses_fake_provider_run():
    config = parse_original_flow_crypto_mining_run_config(
        {
            "output_dir": "/tmp/quantaalpha_runs",
            "run_id": "original_flow_001",
            "data_adapter": {
                "data_path": ["data/binance/BTCUSDT.csv", "data/binance/ETHUSDT.csv"],
                "symbols": ["BTCUSDT", "ETHUSDT"],
                "frequency": "1min",
                "start_time": "2026-01-01 00:00:00",
                "end_time": "2026-01-02 00:00:00",
                "product_type": "spot",
                "dependency_name": "binance_spot_1m_ohlcv",
                "source_format": "binance_spot_candles_jsonl",
            },
            "provider": "fake",
            "repair_provider": "fake",
            "candidate_horizon": "1min",
            "input_lookback_window": "4h",
            "update_frequency": "15min",
            "rebalance_frequency": "1h",
            "research_direction": "liquidity shock reversal",
            "max_repair_attempts": 2,
        }
    )

    assert isinstance(config, OriginalFlowCryptoMiningRunConfig)
    assert config.run_id == "original_flow_001"
    assert config.data_adapter.symbols == ["BTCUSDT", "ETHUSDT"]
    assert config.data_adapter.data_path == [
        Path("data/binance/BTCUSDT.csv"),
        Path("data/binance/ETHUSDT.csv"),
    ]
    assert config.data_adapter.source_format == "binance_spot_candles_jsonl"
    assert config.provider.name == "fake"
    assert config.repair_provider.name == "fake"
    assert config.timing.input_lookback_window == "4h"
    assert config.timing.update_frequency == "15min"
    assert config.timing.rebalance_frequency == "1h"
    assert config.research_direction == "liquidity shock reversal"

    round_config = config.to_local_round_config()
    assert round_config.crypto_data_universe == {
        "feature_data": ["binance_spot_1m_ohlcv"],
        "pnl_data": ["binance_spot_1m_ohlcv"],
    }
    assert round_config.feature_data_dependencies == ["binance_spot_1m_ohlcv"]
    assert round_config.pnl_data_dependencies == ["binance_spot_1m_ohlcv"]
    assert round_config.input_lookback_window == "4h"
    assert round_config.research_direction == "liquidity shock reversal"


def test_original_flow_crypto_mining_config_rejects_empty_research_direction():
    payload = _minimal_payload()
    payload["research_direction"] = " "

    with pytest.raises(ValueError, match="research_direction"):
        parse_original_flow_crypto_mining_run_config(payload)


def test_original_flow_crypto_mining_config_rejects_missing_timing_semantics():
    payload = _minimal_payload()
    del payload["rebalance_frequency"]

    with pytest.raises(ValueError, match="rebalance_frequency"):
        parse_original_flow_crypto_mining_run_config(payload)


def test_original_flow_crypto_mining_config_accepts_anthropic_opus_4_8_provider():
    payload = _minimal_payload()
    payload["provider"] = "anthropic"
    payload["repair_provider"] = "anthropic"
    payload["model"] = "claude-opus-4-8"

    config = parse_original_flow_crypto_mining_run_config(payload)

    assert config.provider.name == "anthropic"
    assert config.provider.model == "claude-opus-4-8"
    assert config.repair_provider.name == "anthropic"
    assert config.repair_provider.model == "claude-opus-4-8"


def _minimal_payload():
    return {
        "output_dir": "/tmp/quantaalpha_runs",
        "run_id": "original_flow_001",
        "data_adapter": {
            "data_path": "data/binance/BTCUSDT.csv",
            "symbols": ["BTCUSDT"],
            "frequency": "1min",
            "product_type": "spot",
            "dependency_name": "binance_spot_1m_ohlcv",
        },
        "provider": "fake",
        "repair_provider": "fake",
        "candidate_horizon": "1min",
        "input_lookback_window": "4h",
        "update_frequency": "15min",
        "rebalance_frequency": "1h",
        "max_repair_attempts": 2,
    }
