from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from quantaalpha_crypto.data import BinanceLocalDataConfig
from quantaalpha_crypto.mining.round import CryptoMiningRoundConfig

DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"


@dataclass(frozen=True)
class FactorTimingConfig:
    input_lookback_window: str
    update_frequency: str
    rebalance_frequency: str


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str | None = None


@dataclass(frozen=True)
class OriginalFlowCryptoMiningRunConfig:
    output_dir: str | Path
    run_id: str
    data_adapter: BinanceLocalDataConfig
    provider: ProviderConfig
    repair_provider: ProviderConfig
    candidate_horizon: str
    timing: FactorTimingConfig
    max_repair_attempts: int
    research_direction: str | None = None

    def to_local_round_config(self) -> CryptoMiningRoundConfig:
        dependencies = [self.data_adapter.dependency_name]
        return CryptoMiningRoundConfig(
            output_dir=self.output_dir,
            run_id=self.run_id,
            crypto_data_universe={
                "feature_data": dependencies,
                "pnl_data": dependencies,
            },
            candidate_horizon=self.candidate_horizon,
            feature_data_dependencies=dependencies,
            pnl_data_dependencies=dependencies,
            max_repair_attempts=self.max_repair_attempts,
            input_lookback_window=self.timing.input_lookback_window,
            research_direction=self.research_direction,
        )


def parse_original_flow_crypto_mining_run_config(
    payload: dict[str, Any],
) -> OriginalFlowCryptoMiningRunConfig:
    """Parse and validate Original-flow Crypto Mining config."""
    _require_fields(
        payload,
        [
            "output_dir",
            "run_id",
            "data_adapter",
            "provider",
            "repair_provider",
            "candidate_horizon",
            "input_lookback_window",
            "update_frequency",
            "rebalance_frequency",
            "max_repair_attempts",
        ],
    )

    timing = FactorTimingConfig(
        input_lookback_window=str(payload["input_lookback_window"]),
        update_frequency=str(payload["update_frequency"]),
        rebalance_frequency=str(payload["rebalance_frequency"]),
    )
    _validate_positive_timedelta(timing.input_lookback_window, "input_lookback_window")
    _validate_positive_timedelta(timing.update_frequency, "update_frequency")
    _validate_positive_timedelta(timing.rebalance_frequency, "rebalance_frequency")

    data_adapter = _parse_data_adapter(payload["data_adapter"])
    return OriginalFlowCryptoMiningRunConfig(
        output_dir=payload["output_dir"],
        run_id=str(payload["run_id"]),
        data_adapter=data_adapter,
        provider=_parse_provider(payload, "provider"),
        repair_provider=_parse_provider(payload, "repair_provider"),
        candidate_horizon=str(payload["candidate_horizon"]),
        timing=timing,
        max_repair_attempts=_parse_non_negative_int(payload["max_repair_attempts"], "max_repair_attempts"),
        research_direction=_parse_optional_non_empty_string(
            payload.get("research_direction"), "research_direction"
        ),
    )


def _parse_data_adapter(payload: dict[str, Any]) -> BinanceLocalDataConfig:
    _require_fields(payload, ["data_path", "symbols", "frequency"])
    data_path = payload["data_path"]
    if isinstance(data_path, list):
        parsed_data_path = [Path(path) for path in data_path]
    else:
        parsed_data_path = Path(data_path)
    return BinanceLocalDataConfig(
        data_path=parsed_data_path,
        symbols=[str(symbol) for symbol in payload["symbols"]],
        frequency=str(payload["frequency"]),
        start_time=payload.get("start_time"),
        end_time=payload.get("end_time"),
        product_type=payload.get("product_type", "spot"),
        dependency_name=payload.get("dependency_name", "binance_local_ohlcv"),
        source_format=payload.get("source_format", "csv"),
    )


def _parse_provider(payload: dict[str, Any], field_name: str) -> ProviderConfig:
    provider_name = str(payload[field_name])
    if provider_name not in ("fake", "anthropic"):
        raise ValueError(f"{field_name} must be one of: fake, anthropic.")
    model = payload.get("model")
    if provider_name == "anthropic" and model is None:
        model = DEFAULT_ANTHROPIC_MODEL
    return ProviderConfig(name=provider_name, model=model)


def _require_fields(payload: dict[str, Any], fields: list[str]) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")


def _validate_positive_timedelta(value: str, field_name: str) -> None:
    try:
        delta = pd.Timedelta(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a valid positive timedelta.") from error
    if delta <= pd.Timedelta(0):
        raise ValueError(f"{field_name} must be a valid positive timedelta.")


def _parse_non_negative_int(value: Any, field_name: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return parsed


def _parse_optional_non_empty_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    parsed = str(value).strip()
    if not parsed:
        raise ValueError(f"{field_name} must be a non-empty string when provided.")
    return parsed
