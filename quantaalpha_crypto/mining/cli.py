from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from quantaalpha_crypto.evaluation.panel import CryptoPanel, build_crypto_panel
from quantaalpha_crypto.data import load_binance_crypto_panel_data
from quantaalpha_crypto.mining.config import parse_original_flow_crypto_mining_run_config
from quantaalpha_crypto.mining.proposal import (
    FactorProposalCandidate,
    FactorProposalResult,
    FactorRepairResult,
)
from quantaalpha_crypto.mining.llm_provider import (
    AnthropicCompletionClient,
    AnthropicCryptoFactorProposalProvider,
    AnthropicCryptoFactorRepairProvider,
    DEFAULT_ANTHROPIC_THINKING,
)
from quantaalpha_crypto.mining.round import CryptoMiningRoundConfig, run_local_crypto_mining_round


class FakeCryptoProposalProvider:
    def propose(self, context):
        def broken_factor(data):
            raise RuntimeError("boom")

        return FactorProposalResult(
            provider_name="fake",
            prompt_context={
                "prompt_template": "deterministic_cli_fake",
                "candidate_horizon": context.candidate_horizon,
                "research_direction": context.research_direction,
            },
            candidates=[
                FactorProposalCandidate(
                    factor_name="momentum",
                    factor_callable_reference="fake_cli.momentum",
                    factor_callable=lambda data: _default_factor_price(data),
                ),
                FactorProposalCandidate(
                    factor_name="contrarian",
                    factor_callable_reference="fake_cli.contrarian",
                    factor_callable=lambda data: -_default_factor_price(data),
                ),
                FactorProposalCandidate(
                    factor_name="broken",
                    factor_callable_reference="fake_cli.broken",
                    factor_callable=broken_factor,
                ),
            ],
        )


class FakeCryptoRepairProvider:
    def repair(self, context):
        return FactorRepairResult(
            provider_name="fake",
            prompt_context={"repair_template": "deterministic_cli_fake"},
            repaired_candidate=FactorProposalCandidate(
                factor_name="repaired_momentum",
                factor_callable_reference="fake_cli.repaired_momentum",
                factor_callable=lambda data: _default_factor_price(data),
            ),
        )


def main(
    argv: list[str] | None = None,
    config: str | None = None,
    output_dir: str | None = None,
) -> int:
    if config is None or output_dir is None:
        parser = argparse.ArgumentParser(description="Run a local crypto factor mining round.")
        parser.add_argument("-c", "--config", required=True, help="Crypto mining round config path.")
        parser.add_argument("--output-dir", required=True, help="Output directory for run artifacts.")
        args = parser.parse_args(argv)
        config = args.config
        output_dir = args.output_dir

    try:
        config_payload = _load_config(Path(config))
        _validate_config(config_payload)
        proposal_provider = _build_proposal_provider(config_payload)
        repair_provider = _build_repair_provider(config_payload)
        feature_panel, pnl_panel = _build_fixture_panels(config_payload)
        result = run_local_crypto_mining_round(
            config=CryptoMiningRoundConfig(
                output_dir=output_dir,
                run_id=config_payload["run_id"],
                crypto_data_universe=config_payload["crypto_data_universe"],
                candidate_horizons=config_payload["candidate_horizons"],
                candidate_horizon=config_payload["candidate_horizon"],
                evaluation_grid=config_payload["evaluation_grid"],
                walk_forward_settings=config_payload["walk_forward_settings"],
                feature_data_dependencies=config_payload["feature_data_dependencies"],
                pnl_data_dependencies=config_payload["pnl_data_dependencies"],
                max_repair_attempts=config_payload["max_repair_attempts"],
            ),
            proposal_provider=proposal_provider,
            repair_provider=repair_provider,
            feature_panel=feature_panel,
            pnl_panel=pnl_panel,
        )
    except Exception as error:
        print(f"Invalid crypto mining config: {error}", file=sys.stderr)
        return 1

    print(f"workspace: {result.workspace.root}")
    print(f"manifest: {result.workspace.manifest_path}")
    print(f"candidate_library: {result.workspace.candidate_library_path}")
    return 0


def original_flow_main(
    argv: list[str] | None = None,
    config: str | None = None,
) -> int:
    if config is None:
        parser = argparse.ArgumentParser(description="Run Original-flow Crypto Mining.")
        parser.add_argument("-c", "--config", required=True, help="Original-flow crypto mining config path.")
        args = parser.parse_args(argv)
        config = args.config

    try:
        _print_progress("config_load_start")
        config_payload = _load_config(Path(config))
        run_config = parse_original_flow_crypto_mining_run_config(config_payload)
        _print_progress("config_load_done")
        proposal_provider = _build_proposal_provider(config_payload)
        repair_provider = _build_repair_provider(config_payload)
        started_at = perf_counter()
        _print_progress("data_load_start")
        panel_data = load_binance_crypto_panel_data(run_config.data_adapter)
        _print_progress(f"data_load_done {perf_counter() - started_at:.3f}s rows={len(panel_data.feature_panel.data)}")
        _print_progress("mining_round_start")
        result = run_local_crypto_mining_round(
            config=run_config.to_local_round_config(),
            proposal_provider=proposal_provider,
            repair_provider=repair_provider,
            feature_panel=panel_data.feature_panel,
            pnl_panel=panel_data.pnl_panel,
            progress_callback=_print_progress,
        )
        _print_progress("mining_round_done")
    except Exception as error:
        print(f"Invalid original-flow crypto mining config: {error}", file=sys.stderr)
        return 1

    print(f"workspace: {result.workspace.root}")
    print(f"manifest: {result.workspace.manifest_path}")
    print(f"reports: {result.workspace.reports_dir}")
    print(f"rejected: {result.workspace.rejected_dir}")
    print(f"candidate_library: {result.workspace.candidate_library_path}")
    return 0


def real_smoke_main(
    argv: list[str] | None = None,
    config: str | None = None,
    allow_live_llm: bool = False,
) -> int:
    if config is None:
        parser = argparse.ArgumentParser(description="Run manual real crypto original-flow smoke.")
        parser.add_argument("-c", "--config", required=True, help="Real smoke config path.")
        parser.add_argument(
            "--allow-live-llm",
            action="store_true",
            help="Allow a live Anthropic API call. This command is not for CI.",
        )
        args = parser.parse_args(argv)
        config = args.config
        allow_live_llm = args.allow_live_llm

    try:
        config_payload = _load_config(Path(config))
        _validate_real_smoke_config(config_payload, allow_live_llm=allow_live_llm)
    except Exception as error:
        print(f"Invalid real crypto smoke config: {error}", file=sys.stderr)
        return 1

    return original_flow_main(config=config)


def _load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"config file not found: {path}")
    if path.suffix.lower() != ".json":
        raise ValueError("only JSON config files are supported by the local crypto mining CLI.")
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_real_smoke_config(config: dict[str, Any], allow_live_llm: bool) -> None:
    if not allow_live_llm:
        raise ValueError("real smoke requires --allow-live-llm and is not required for CI.")
    if config.get("provider") != "anthropic" or config.get("repair_provider") != "anthropic":
        raise ValueError("real smoke requires provider='anthropic' and repair_provider='anthropic'.")
    parse_original_flow_crypto_mining_run_config(config)


def _print_progress(message: str) -> None:
    print(f"[crypto-progress] {message}", file=sys.stderr, flush=True)


def _default_factor_price(data: pd.DataFrame) -> pd.Series:
    for column in ("futures_close", "spot_close", "close"):
        if column in data:
            return data[column]
    raise ValueError("factor data requires futures_close, spot_close, or close")


def _validate_config(config: dict[str, Any]) -> None:
    required_fields = [
        "run_id",
        "crypto_data_universe",
        "candidate_horizons",
        "candidate_horizon",
        "evaluation_grid",
        "walk_forward_settings",
        "feature_data_dependencies",
        "pnl_data_dependencies",
        "max_repair_attempts",
    ]
    missing = [field for field in required_fields if field not in config]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")


def _build_proposal_provider(config: dict[str, Any]):
    provider = config.get("provider")
    if provider == "fake":
        return FakeCryptoProposalProvider()
    if provider == "anthropic":
        return AnthropicCryptoFactorProposalProvider(
            completion_client=AnthropicCompletionClient(
                timeout_seconds=int(config.get("anthropic_timeout_seconds", 120))
            ),
            model=config.get("model", "claude-opus-4-8"),
            max_tokens=int(config.get("anthropic_max_tokens", 64000)),
            effort=config.get("anthropic_effort", "max"),
            thinking=_anthropic_thinking(config),
        )
    raise ValueError("provider must be one of: fake, anthropic.")


def _build_repair_provider(config: dict[str, Any]):
    repair_provider = config.get("repair_provider")
    if repair_provider == "fake":
        return FakeCryptoRepairProvider()
    if repair_provider == "anthropic":
        return AnthropicCryptoFactorRepairProvider(
            completion_client=AnthropicCompletionClient(
                timeout_seconds=int(config.get("anthropic_timeout_seconds", 120))
            ),
            model=config.get("model", "claude-opus-4-8"),
            max_tokens=int(config.get("anthropic_max_tokens", 64000)),
            effort=config.get("anthropic_effort", "max"),
            thinking=_anthropic_thinking(config),
        )
    raise ValueError("repair_provider must be one of: fake, anthropic.")


def _anthropic_thinking(config: dict[str, Any]) -> dict[str, Any] | None:
    if "anthropic_thinking" in config:
        return config["anthropic_thinking"]
    return DEFAULT_ANTHROPIC_THINKING


def _build_fixture_panels(config: dict[str, Any]) -> tuple[CryptoPanel, CryptoPanel]:
    if config.get("fixture") != "deterministic_spot_1m":
        raise ValueError("only fixture='deterministic_spot_1m' is supported by the local crypto mining CLI.")
    panel_data = build_crypto_panel(
        pd.DataFrame(
            [
                {
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 10,
                }
                for timestamp, btc_close, eth_close in [
                    ("2026-01-01 00:00:00", 100, 100),
                    ("2026-01-01 00:01:00", 110, 90),
                    ("2026-01-01 00:02:00", 121, 81),
                    ("2026-01-01 00:03:00", 133.1, 72.9),
                ]
                for symbol, close in [("BTCUSDT", btc_close), ("ETHUSDT", eth_close)]
            ]
        )
    )
    return (
        CryptoPanel(data=panel_data, data_role="feature"),
        CryptoPanel(data=panel_data, data_role="pnl", data_product="spot"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
