import json

import pandas as pd

from quantaalpha_crypto import (
    build_round_feedback_context,
    CryptoPanel,
    CryptoMiningRoundConfig,
    FactorProposalCandidate,
    FactorProposalResult,
    FactorRepairResult,
    build_crypto_panel,
    load_candidate_factor_library,
    run_local_crypto_mining_round,
)


class FakeRoundProposalProvider:
    def propose(self, context):
        def broken_factor(data):
            raise RuntimeError("boom")

        return FactorProposalResult(
            provider_name="fake_round_provider",
            prompt_context={"prompt_template": "deterministic_round"},
            candidates=[
                FactorProposalCandidate(
                    factor_name="momentum",
                    factor_callable_reference="fake_round.momentum",
                    factor_callable=lambda data: data["close"],
                ),
                FactorProposalCandidate(
                    factor_name="contrarian",
                    factor_callable_reference="fake_round.contrarian",
                    factor_callable=lambda data: -data["close"],
                ),
                FactorProposalCandidate(
                    factor_name="broken",
                    factor_callable_reference="fake_round.broken",
                    factor_callable=broken_factor,
                ),
            ],
        )


class FakeRoundRepairProvider:
    def repair(self, context):
        return FactorRepairResult(
            provider_name="fake_round_repair",
            prompt_context={"repair_template": "deterministic_round"},
            repaired_candidate=FactorProposalCandidate(
                factor_name="repaired_momentum",
                factor_callable_reference="fake_round.repaired_momentum",
                factor_callable=lambda data: data["close"],
            ),
        )


class FollowUpProposalProvider:
    def __init__(self):
        self.contexts = []

    def propose(self, context):
        self.contexts.append(context)
        return FactorProposalResult(
            provider_name="followup_provider",
            prompt_context={"prompt_template": "followup_round"},
            candidates=[
                FactorProposalCandidate(
                    factor_name="followup_momentum",
                    factor_callable_reference="followup.momentum",
                    factor_callable=lambda data: data["close"],
                )
            ],
        )


def test_local_crypto_mining_round_writes_complete_research_artifact(tmp_path):
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

    result = run_local_crypto_mining_round(
        config=CryptoMiningRoundConfig(
            output_dir=tmp_path,
            run_id="round_001",
            crypto_data_universe={
                "feature_data": ["fixture_spot_1m_ohlcv"],
                "pnl_data": ["fixture_spot_1m_ohlcv"],
            },
            candidate_horizon="1min",
            feature_data_dependencies=["fixture_spot_1m_ohlcv"],
            pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
            max_repair_attempts=1,
            research_direction="liquidity shock reversal",
            input_lookback_window="2min",
        ),
        proposal_provider=FakeRoundProposalProvider(),
        repair_provider=FakeRoundRepairProvider(),
        feature_panel=feature_panel,
    )

    assert result.workspace.root == tmp_path / "round_001"
    assert [(factor.factor_name, factor.symbol) for factor in result.batch_result.factors] == [
        ("momentum", "BTCUSDT"),
        ("momentum", "ETHUSDT"),
        ("contrarian", "BTCUSDT"),
        ("contrarian", "ETHUSDT"),
        ("broken", "BTCUSDT"),
        ("broken", "ETHUSDT"),
        ("repaired_momentum", "BTCUSDT"),
        ("repaired_momentum", "ETHUSDT"),
    ]
    # New paradigm: all non-failed factors are "candidate" (placeholder)
    assert [factor.gate_status for factor in result.batch_result.factors] == [
        "candidate",
        "candidate",
        "candidate",
        "candidate",
        "execution_failed",
        "execution_failed",
        "candidate",
        "candidate",
    ]

    assert (result.workspace.reports_dir / "momentum__BTCUSDT.json").exists()
    assert (result.workspace.reports_dir / "momentum__ETHUSDT.json").exists()
    assert (result.workspace.reports_dir / "contrarian__BTCUSDT.json").exists()
    assert (result.workspace.reports_dir / "contrarian__ETHUSDT.json").exists()
    assert (result.workspace.reports_dir / "repaired_momentum__BTCUSDT.json").exists()
    assert (result.workspace.reports_dir / "repaired_momentum__ETHUSDT.json").exists()
    assert (result.workspace.rejected_dir / "broken__BTCUSDT.json").exists()
    assert (result.workspace.rejected_dir / "broken__ETHUSDT.json").exists()

    # Library storage is deferred to iteration 2
    library = load_candidate_factor_library(result.workspace.candidate_library_path)
    assert library["entries"] == []

    manifest = json.loads(result.workspace.manifest_path.read_text(encoding="utf-8"))
    assert manifest["artifact_type"] == "crypto_factor_workspace"
    assert manifest["live_strategy"] is False
    assert manifest["proposal_runs"][0]["provider_name"] == "fake_round_provider"
    assert manifest["proposal_runs"][0]["context"]["research_direction"] == "liquidity shock reversal"
    assert manifest["repair_runs"][0]["attempts"][0]["provider_name"] == "fake_round_repair"
    assert manifest["mining_round"]["artifact_type"] == "local_crypto_mining_round"
    assert manifest["mining_round"]["status"] == "completed"
    assert manifest["mining_round"]["live_strategy"] is False
    assert manifest["mining_round"]["result_counts"] == {
        "accepted": 0,
        "execution_failed": 2,
        "rejected": 0,
        "total": 8,
    }
    assert manifest["mining_round"]["timing"]["total_seconds"] >= 0.0
    assert manifest["mining_round"]["factor_results"][0]["timing"]["total_seconds"] >= 0.0
    assert manifest["mining_round"]["workflow_steps"] == [
        "create_workspace",
        "propose_candidates",
        "evaluate_candidates",
        "repair_execution_failures",
        "write_reports_and_library",
    ]
    assert "live strategy" not in json.dumps(manifest).lower()


def test_local_crypto_mining_round_feeds_previous_round_results_to_next_proposal(tmp_path):
    feature_panel, pnl_panel, config = _fixture_round_inputs(tmp_path)
    first_round = run_local_crypto_mining_round(
        config=config,
        proposal_provider=FakeRoundProposalProvider(),
        repair_provider=FakeRoundRepairProvider(),
        feature_panel=feature_panel,
    )

    previous_round_feedback = build_round_feedback_context(first_round.workspace)
    followup_provider = FollowUpProposalProvider()

    run_local_crypto_mining_round(
        config=CryptoMiningRoundConfig(
            output_dir=tmp_path,
            run_id="round_002",
            crypto_data_universe=config.crypto_data_universe,
            candidate_horizon=config.candidate_horizon,
            feature_data_dependencies=config.feature_data_dependencies,
            pnl_data_dependencies=config.pnl_data_dependencies,
            max_repair_attempts=0,
            input_lookback_window="2min",
        ),
        proposal_provider=followup_provider,
        repair_provider=FakeRoundRepairProvider(),
        feature_panel=feature_panel,
        previous_round_feedback=previous_round_feedback,
    )

    feedback = followup_provider.contexts[0].previous_round_feedback
    # New paradigm: no accepted factors (library storage deferred), all non-failed go to "rejected"
    assert feedback["result_counts"] == {
        "accepted": 0,
        "execution_failed": 2,
        "rejected": 0,
        "total": 8,
    }
    # Non-failed, non-accepted factors appear in "rejected" bucket of feedback
    assert len(feedback["accepted"]) == 0
    assert len(feedback["execution_failed"]) > 0
    assert feedback["execution_failed"][0]["diagnostic"]["error_message"] == "boom"
    assert "api_key" not in json.dumps(feedback).lower()


def test_local_crypto_mining_round_redacts_previous_feedback_before_provider_and_manifest(tmp_path):
    feature_panel, pnl_panel, config = _fixture_round_inputs(tmp_path)
    followup_provider = FollowUpProposalProvider()

    result = run_local_crypto_mining_round(
        config=config,
        proposal_provider=followup_provider,
        repair_provider=FakeRoundRepairProvider(),
        feature_panel=feature_panel,
        previous_round_feedback={
            "accepted": [{"factor_name": "safe"}],
            "api_key": "sk-should-not-reach-provider",
            "nested": {"authorization_token": "token-should-not-be-written"},
        },
    )

    provider_feedback = followup_provider.contexts[0].previous_round_feedback
    manifest_text = result.workspace.manifest_path.read_text(encoding="utf-8")

    assert provider_feedback["api_key"] == "[REDACTED]"
    assert provider_feedback["nested"]["authorization_token"] == "[REDACTED]"
    assert "sk-should-not-reach-provider" not in manifest_text
    assert "token-should-not-be-written" not in manifest_text


def _fixture_round_inputs(tmp_path):
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
    return (
        feature_panel,
        pnl_panel,
        CryptoMiningRoundConfig(
            output_dir=tmp_path,
            run_id="round_001",
            crypto_data_universe={
                "feature_data": ["fixture_spot_1m_ohlcv"],
                "pnl_data": ["fixture_spot_1m_ohlcv"],
            },
            candidate_horizon="1min",
            feature_data_dependencies=["fixture_spot_1m_ohlcv"],
            pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
            max_repair_attempts=1,
            input_lookback_window="2min",
        ),
    )
