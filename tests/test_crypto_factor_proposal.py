import json

import pandas as pd

from quantaalpha_crypto import (
    CryptoPanel,
    FactorProposalCandidate,
    FactorProposalResult,
    FactorRepairResult,
    build_crypto_panel,
    create_crypto_factor_workspace,
    load_candidate_factor_library,
    run_factor_proposal_provider,
    run_factor_proposal_provider_with_repair,
)


class FakeProposalProvider:
    def __init__(self):
        self.contexts = []

    def propose(self, context):
        self.contexts.append(context)
        return FactorProposalResult(
            provider_name="fake_provider",
            prompt_context={
                "prompt_template": "deterministic_fake",
                "candidate_horizon": context.candidate_horizon,
            },
            candidates=[
                FactorProposalCandidate(
                    factor_name="momentum",
                    factor_callable_reference="fake_provider.momentum",
                    factor_callable=lambda data: data["close"],
                )
            ],
        )


class ArtifactProposalProvider:
    def propose(self, context):
        source_code = "def factor(data):\n    return data['close']\n"
        return FactorProposalResult(
            provider_name="artifact_provider",
            prompt_context={
                "prompt_template": "artifact_fake",
                "model": "fake-model",
            },
            raw_response='{"candidates": [{"factor_name": "momentum"}]}',
            parsed_response={
                "candidates": [
                    {
                        "factor_name": "momentum",
                        "factor_callable_reference": "artifact_provider.momentum",
                        "python_code": source_code,
                    }
                ]
            },
            candidates=[
                FactorProposalCandidate(
                    factor_name="momentum",
                    factor_callable_reference="artifact_provider.momentum",
                    factor_callable=lambda data: data["close"],
                    source_code=source_code,
                )
            ],
        )


class SecretPromptContextProposalProvider:
    def propose(self, context):
        source_code = "def factor(data):\n    return data['close']\n"
        return FactorProposalResult(
            provider_name="secret_provider",
            prompt_context={
                "prompt_template": "secret_fake",
                "api_key": "sk-test-should-not-be-written",
                "nested": {"authorization_token": "token-should-not-be-written"},
            },
            raw_response='{"candidates": [{"factor_name": "secret_factor"}]}',
            parsed_response={"candidates": [{"factor_name": "secret_factor"}]},
            candidates=[
                FactorProposalCandidate(
                    factor_name="secret_factor",
                    factor_callable_reference="secret_provider.secret_factor",
                    factor_callable=lambda data: data["close"],
                    source_code=source_code,
                )
            ],
        )


class DuplicateNameArtifactProposalProvider:
    def propose(self, context):
        first_source = "def factor(data):\n    return data['close']\n"
        second_source = "def factor(data):\n    return data['volume']\n"
        return FactorProposalResult(
            provider_name="duplicate_provider",
            prompt_context={"prompt_template": "duplicate_fake"},
            raw_response='{"candidates": [{"factor_name": "dup"}, {"factor_name": "dup"}]}',
            parsed_response={"candidates": [{"factor_name": "dup"}, {"factor_name": "dup"}]},
            candidates=[
                FactorProposalCandidate(
                    factor_name="dup",
                    factor_callable_reference="duplicate_provider.first",
                    factor_callable=lambda data: data["close"],
                    source_code=first_source,
                ),
                FactorProposalCandidate(
                    factor_name="dup",
                    factor_callable_reference="duplicate_provider.second",
                    factor_callable=lambda data: data["volume"],
                    source_code=second_source,
                ),
            ],
        )


class FailingArtifactProposalProvider:
    def propose(self, context):
        raise SyntaxError("invalid generated factor code")


class BrokenProposalProvider:
    def propose(self, context):
        def broken_factor(data):
            raise RuntimeError("boom")

        return FactorProposalResult(
            provider_name="broken_provider",
            prompt_context={"prompt_template": "broken_fake"},
            candidates=[
                FactorProposalCandidate(
                    factor_name="broken",
                    factor_callable_reference="broken_provider.broken",
                    factor_callable=broken_factor,
                )
            ],
        )


class RepairingProvider:
    def __init__(self):
        self.contexts = []

    def repair(self, context):
        self.contexts.append(context)
        return FactorRepairResult(
            provider_name="repair_provider",
            prompt_context={"repair_template": "deterministic_fake"},
            repaired_candidate=FactorProposalCandidate(
                factor_name="momentum_repaired",
                factor_callable_reference="repair_provider.momentum_repaired",
                factor_callable=lambda data: data["close"],
            ),
        )


class ArtifactRepairingProvider:
    def repair(self, context):
        source_code = "def factor(data):\n    return data['close']\n"
        return FactorRepairResult(
            provider_name="artifact_repair_provider",
            prompt_context={
                "repair_template": "artifact_repair_fake",
                "model": "fake-repair-model",
            },
            raw_response='{"repaired_candidate": {"factor_name": "repaired"}}',
            parsed_response={
                "repaired_candidate": {
                    "factor_name": "repaired",
                    "factor_callable_reference": "artifact_repair_provider.repaired",
                    "python_code": source_code,
                }
            },
            repaired_candidate=FactorProposalCandidate(
                factor_name="repaired",
                factor_callable_reference="artifact_repair_provider.repaired",
                factor_callable=lambda data: data["close"],
                source_code=source_code,
            ),
        )


class UnrepairedProvider:
    def repair(self, context):
        return FactorRepairResult(
            provider_name="repair_provider",
            prompt_context={"repair_template": "deterministic_fake"},
            repaired_candidate=None,
        )


class SameNameRetryRepairProvider:
    def __init__(self):
        self.calls = 0

    def repair(self, context):
        self.calls += 1
        if self.calls == 1:
            def still_broken(data):
                raise RuntimeError("second")

            return FactorRepairResult(
                provider_name="repair_provider",
                prompt_context={"repair_template": "same_name_retry"},
                repaired_candidate=FactorProposalCandidate(
                    factor_name="broken",
                    factor_callable_reference="repair_provider.still_broken",
                    factor_callable=still_broken,
                ),
            )
        return FactorRepairResult(
            provider_name="repair_provider",
            prompt_context={"repair_template": "same_name_retry"},
            repaired_candidate=FactorProposalCandidate(
                factor_name="fixed",
                factor_callable_reference="repair_provider.fixed",
                factor_callable=lambda data: data["close"],
            ),
        )


def test_proposal_provider_candidates_are_evaluated_through_gates_and_recorded(tmp_path):
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
                for minute in range(8)
                for timestamp, symbol, close in [
                    (
                        f"2026-01-01 00:0{minute}:00",
                        "BTCUSDT",
                        100 + minute * 10,
                    ),
                    (
                        f"2026-01-01 00:0{minute}:00",
                        "ETHUSDT",
                        100 - minute * 5,
                    ),
                ]
            ]
        )
    )
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    pnl_panel = CryptoPanel(data=panel_data, data_role="pnl", data_product="spot")
    evaluation_grid = [
        {
            "action": "spot_long",
            "threshold_quantile": 0.8,
            "holding_horizon": "1min",
            "leverage": 1.0,
        }
    ]
    walk_forward_settings = {
        "train_window": "2min",
        "validation_window": "2min",
        "test_window": "2min",
        "step": "2min",
    }
    workspace = create_crypto_factor_workspace(
        output_dir=tmp_path,
        run_id="run_001",
        crypto_data_universe={
            "feature_data": ["fixture_spot_1m_ohlcv"],
            "pnl_data": ["fixture_spot_1m_ohlcv"],
        },
        candidate_horizons=["1min"],
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
    )

    provider = FakeProposalProvider()
    result = run_factor_proposal_provider(
        workspace=workspace,
        provider=provider,
        feature_panel=feature_panel,
        pnl_panel=pnl_panel,
        candidate_horizon="1min",
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        research_direction="liquidity shock reversal",
    )

    assert [(factor.factor_name, factor.symbol) for factor in result.factors] == [
        ("momentum", "BTCUSDT"),
        ("momentum", "ETHUSDT"),
    ]
    assert result.factors[0].gate_status == "strong"
    assert result.factors[0].library_entry_stored is True
    assert result.factors[1].gate_status == "rejected"
    assert result.factors[1].library_entry_stored is False
    assert (workspace.reports_dir / "momentum__BTCUSDT.json").exists()
    assert (workspace.reports_dir / "momentum__ETHUSDT.json").exists()
    assert provider.contexts[0].available_columns == ["open", "high", "low", "close", "volume"]
    assert provider.contexts[0].research_direction == "liquidity shock reversal"

    library = load_candidate_factor_library(workspace.candidate_library_path)
    assert [entry["factor_callable_reference"] for entry in library["entries"]] == [
        "fake_provider.momentum"
    ]
    assert [entry["symbol"] for entry in library["entries"]] == ["BTCUSDT"]

    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    proposal_run = manifest["proposal_runs"][0]
    assert proposal_run["provider_name"] == "fake_provider"
    assert proposal_run["prompt_context"]["prompt_template"] == "deterministic_fake"
    assert proposal_run["prompt_context"]["candidate_horizon"] == "1min"
    assert proposal_run["context"]["available_columns"] == ["open", "high", "low", "close", "volume"]
    assert proposal_run["context"]["research_direction"] == "liquidity shock reversal"
    assert proposal_run["candidate_count"] == 1
    assert proposal_run["candidates"] == [
        {
            "factor_name": "momentum",
            "factor_callable_reference": "fake_provider.momentum",
        }
    ]
    assert proposal_run["live_strategy"] is False


def test_proposal_provider_persists_factor_artifacts_before_evaluation(tmp_path):
    feature_panel, pnl_panel, workspace, evaluation_grid, walk_forward_settings = _fixture_run(tmp_path)

    run_factor_proposal_provider(
        workspace=workspace,
        provider=ArtifactProposalProvider(),
        feature_panel=feature_panel,
        pnl_panel=pnl_panel,
        candidate_horizon="1min",
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        input_lookback_window="4h",
        update_frequency="15min",
    )

    artifacts = list(workspace.factor_artifacts_dir.glob("*.json"))
    assert len(artifacts) == 1

    artifact = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert artifact["artifact_type"] == "llm_factor_artifact"
    assert artifact["provider_name"] == "artifact_provider"
    assert artifact["model"] == "fake-model"
    assert artifact["factor_name"] == "momentum"
    assert artifact["factor_callable_reference"] == "artifact_provider.momentum"
    assert artifact["generated_source"] == "def factor(data):\n    return data['close']\n"
    assert len(artifact["source_hash"]) == 40
    assert artifact["compile_status"] == "compiled"
    assert artifact["raw_response"] == '{"candidates": [{"factor_name": "momentum"}]}'
    assert artifact["parsed_response"]["candidates"][0]["factor_name"] == "momentum"
    assert artifact["timing"] == {
        "input_lookback_window": "4h",
        "update_frequency": "15min",
        "rebalance_frequency": None,
        "candidate_horizon": "1min",
    }
    assert "api_key" not in json.dumps(artifact).lower()

    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    assert manifest["artifact_paths"]["factor_artifacts_dir"] == "factor_artifacts"
    assert manifest["proposal_runs"][0]["candidates"][0]["factor_artifact_reference"] == (
        f"factor_artifacts/{artifacts[0].name}"
    )


def test_proposal_provider_redacts_secret_prompt_context_from_artifacts_and_manifest(tmp_path):
    feature_panel, pnl_panel, workspace, evaluation_grid, walk_forward_settings = _fixture_run(tmp_path)

    run_factor_proposal_provider(
        workspace=workspace,
        provider=SecretPromptContextProposalProvider(),
        feature_panel=feature_panel,
        pnl_panel=pnl_panel,
        candidate_horizon="1min",
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        research_direction="liquidity shock reversal",
    )

    manifest_text = workspace.manifest_path.read_text(encoding="utf-8")
    artifact_text = next(workspace.factor_artifacts_dir.glob("*.json")).read_text(encoding="utf-8")

    assert "sk-test-should-not-be-written" not in manifest_text
    assert "token-should-not-be-written" not in manifest_text
    assert "sk-test-should-not-be-written" not in artifact_text
    assert "token-should-not-be-written" not in artifact_text
    assert "[REDACTED]" in manifest_text
    assert "[REDACTED]" in artifact_text


def test_proposal_provider_manifest_keeps_distinct_artifact_references_for_duplicate_names(tmp_path):
    feature_panel, pnl_panel, workspace, evaluation_grid, walk_forward_settings = _fixture_run(tmp_path)

    run_factor_proposal_provider(
        workspace=workspace,
        provider=DuplicateNameArtifactProposalProvider(),
        feature_panel=feature_panel,
        pnl_panel=pnl_panel,
        candidate_horizon="1min",
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        research_direction="liquidity shock reversal",
    )

    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    references = [
        candidate["factor_artifact_reference"]
        for candidate in manifest["proposal_runs"][0]["candidates"]
    ]

    assert len(references) == 2
    assert len(set(references)) == 2
    assert [
        json.loads((workspace.root / reference).read_text(encoding="utf-8"))["factor_callable_reference"]
        for reference in references
    ] == ["duplicate_provider.first", "duplicate_provider.second"]


def test_proposal_provider_parse_or_compile_failure_becomes_rejected_diagnostic(tmp_path):
    feature_panel, pnl_panel, workspace, evaluation_grid, walk_forward_settings = _fixture_run(tmp_path)

    result = run_factor_proposal_provider(
        workspace=workspace,
        provider=FailingArtifactProposalProvider(),
        feature_panel=feature_panel,
        pnl_panel=pnl_panel,
        candidate_horizon="1min",
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        input_lookback_window="4h",
        update_frequency="15min",
    )

    assert result.factors[0].gate_status == "execution_failed"
    assert result.factors[0].failure_reasons == ["factor_proposal_failed"]
    assert result.factors[0].diagnostic_reference is not None
    diagnostic = json.loads((workspace.root / result.factors[0].diagnostic_reference).read_text(encoding="utf-8"))
    assert diagnostic["artifact_type"] == "rejected_factor_diagnostic"
    assert diagnostic["factor_name"] == "provider_proposal"
    assert diagnostic["error_type"] == "SyntaxError"
    assert diagnostic["error_message"] == "invalid generated factor code"


def test_repair_loop_retries_failed_generated_callable_and_evaluates_repaired_candidate(tmp_path):
    feature_panel, pnl_panel, workspace, evaluation_grid, walk_forward_settings = _fixture_run(tmp_path)
    repair_provider = RepairingProvider()

    result = run_factor_proposal_provider_with_repair(
        workspace=workspace,
        provider=BrokenProposalProvider(),
        repair_provider=repair_provider,
        max_repair_attempts=2,
        feature_panel=feature_panel,
        pnl_panel=pnl_panel,
        candidate_horizon="1min",
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        research_direction="liquidity shock reversal",
    )

    assert [(factor.factor_name, factor.symbol) for factor in result.factors] == [
        ("broken", "BTCUSDT"),
        ("broken", "ETHUSDT"),
        ("momentum_repaired", "BTCUSDT"),
        ("momentum_repaired", "ETHUSDT"),
    ]
    assert result.factors[0].gate_status == "execution_failed"
    assert result.factors[0].diagnostic_reference == "rejected/broken__BTCUSDT.json"
    assert result.factors[1].gate_status == "execution_failed"
    assert result.factors[1].diagnostic_reference == "rejected/broken__ETHUSDT.json"
    assert result.factors[2].gate_status == "strong"
    assert result.factors[2].library_entry_stored is True
    assert result.factors[3].gate_status == "rejected"
    assert result.factors[3].library_entry_stored is False
    assert (workspace.reports_dir / "momentum_repaired__BTCUSDT.json").exists()
    assert (workspace.reports_dir / "momentum_repaired__ETHUSDT.json").exists()
    assert repair_provider.contexts[0].diagnostic["error_type"] == "RuntimeError"
    assert repair_provider.contexts[0].diagnostic["error_message"] == "boom"
    assert repair_provider.contexts[0].available_columns == ["open", "high", "low", "close", "volume"]
    assert repair_provider.contexts[0].research_direction == "liquidity shock reversal"

    library = load_candidate_factor_library(workspace.candidate_library_path)
    assert [entry["factor_callable_reference"] for entry in library["entries"]] == [
        "repair_provider.momentum_repaired"
    ]
    assert [entry["symbol"] for entry in library["entries"]] == ["BTCUSDT"]

    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    repair_attempt = manifest["repair_runs"][0]["attempts"][0]
    assert repair_attempt["provider_name"] == "repair_provider"
    assert repair_attempt["attempt_number"] == 1
    assert repair_attempt["diagnostic_reference"] == "rejected/broken__BTCUSDT.json"
    assert repair_attempt["repaired_candidate"] == {
        "factor_name": "momentum_repaired",
        "factor_callable_reference": "repair_provider.momentum_repaired",
    }
    assert repair_attempt["live_strategy"] is False


def test_repair_provider_persists_repaired_factor_artifact(tmp_path):
    feature_panel, pnl_panel, workspace, evaluation_grid, walk_forward_settings = _fixture_run(tmp_path)

    run_factor_proposal_provider_with_repair(
        workspace=workspace,
        provider=BrokenProposalProvider(),
        repair_provider=ArtifactRepairingProvider(),
        max_repair_attempts=1,
        feature_panel=feature_panel,
        pnl_panel=pnl_panel,
        candidate_horizon="1min",
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        input_lookback_window="4h",
        update_frequency="15min",
    )

    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    repaired_candidate = manifest["repair_runs"][0]["attempts"][0]["repaired_candidate"]
    artifact_reference = repaired_candidate["factor_artifact_reference"]
    artifact = json.loads((workspace.root / artifact_reference).read_text(encoding="utf-8"))

    assert repaired_candidate["factor_name"] == "repaired"
    assert artifact["provider_name"] == "artifact_repair_provider"
    assert artifact["model"] == "fake-repair-model"
    assert artifact["factor_callable_reference"] == "artifact_repair_provider.repaired"
    assert artifact["generated_source"] == "def factor(data):\n    return data['close']\n"
    assert artifact["compile_status"] == "compiled"
    assert artifact["timing"]["input_lookback_window"] == "4h"
    assert artifact["timing"]["update_frequency"] == "15min"
    assert artifact["timing"]["candidate_horizon"] == "1min"


def test_repair_loop_preserves_unrepaired_failure_without_library_entry(tmp_path):
    feature_panel, pnl_panel, workspace, evaluation_grid, walk_forward_settings = _fixture_run(tmp_path)

    result = run_factor_proposal_provider_with_repair(
        workspace=workspace,
        provider=BrokenProposalProvider(),
        repair_provider=UnrepairedProvider(),
        max_repair_attempts=1,
        feature_panel=feature_panel,
        pnl_panel=pnl_panel,
        candidate_horizon="1min",
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
    )

    assert [(factor.factor_name, factor.symbol) for factor in result.factors] == [
        ("broken", "BTCUSDT"),
        ("broken", "ETHUSDT"),
    ]
    assert result.factors[0].gate_status == "execution_failed"
    assert (workspace.rejected_dir / "broken__BTCUSDT.json").exists()
    assert (workspace.rejected_dir / "broken__ETHUSDT.json").exists()

    library = load_candidate_factor_library(workspace.candidate_library_path)
    assert library["entries"] == []

    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    repair_attempt = manifest["repair_runs"][0]["attempts"][0]
    assert repair_attempt["status"] == "unrepaired"
    assert repair_attempt["repaired_candidate"] is None


def test_repair_loop_preserves_multiple_failed_attempt_diagnostics(tmp_path):
    feature_panel, pnl_panel, workspace, evaluation_grid, walk_forward_settings = _fixture_run(tmp_path)

    result = run_factor_proposal_provider_with_repair(
        workspace=workspace,
        provider=BrokenProposalProvider(),
        repair_provider=SameNameRetryRepairProvider(),
        max_repair_attempts=2,
        feature_panel=feature_panel,
        pnl_panel=pnl_panel,
        candidate_horizon="1min",
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
    )

    failed_references = [
        factor.diagnostic_reference
        for factor in result.factors
        if factor.gate_status == "execution_failed"
    ]
    assert len(failed_references) == 4
    assert len(set(failed_references)) == 4
    assert all(reference is not None for reference in failed_references)
    assert [
        json.loads((workspace.root / reference).read_text(encoding="utf-8"))["error_message"]
        for reference in failed_references
    ] == ["boom", "boom", "second", "second"]
    assert ("fixed", "BTCUSDT", "strong") in [
        (factor.factor_name, factor.symbol, factor.gate_status)
        for factor in result.factors
    ]


def _fixture_run(tmp_path):
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
                for minute in range(8)
                for timestamp, symbol, close in [
                    (
                        f"2026-01-01 00:0{minute}:00",
                        "BTCUSDT",
                        100 + minute * 10,
                    ),
                    (
                        f"2026-01-01 00:0{minute}:00",
                        "ETHUSDT",
                        100 - minute * 5,
                    ),
                ]
            ]
        )
    )
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    pnl_panel = CryptoPanel(data=panel_data, data_role="pnl", data_product="spot")
    evaluation_grid = [
        {
            "action": "spot_long",
            "threshold_quantile": 0.8,
            "holding_horizon": "1min",
            "leverage": 1.0,
        }
    ]
    walk_forward_settings = {
        "train_window": "2min",
        "validation_window": "2min",
        "test_window": "2min",
        "step": "2min",
    }
    workspace = create_crypto_factor_workspace(
        output_dir=tmp_path,
        run_id="run_001",
        crypto_data_universe={
            "feature_data": ["fixture_spot_1m_ohlcv"],
            "pnl_data": ["fixture_spot_1m_ohlcv"],
        },
        candidate_horizons=["1min"],
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
    )
    return feature_panel, pnl_panel, workspace, evaluation_grid, walk_forward_settings
