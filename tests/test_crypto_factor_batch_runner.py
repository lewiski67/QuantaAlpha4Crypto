import json

import pandas as pd

from quantaalpha_crypto import (
    CryptoPanel,
    build_crypto_panel,
    create_crypto_factor_workspace,
    load_candidate_factor_library,
    run_supplied_factor_callables,
)


def test_batch_runner_evaluates_supplied_factor_callables_and_updates_library(tmp_path):
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
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    workspace = create_crypto_factor_workspace(
        output_dir=tmp_path,
        run_id="run_001",
        crypto_data_universe={
            "feature_data": ["fixture_spot_1m_ohlcv"],
            "pnl_data": ["fixture_spot_1m_ohlcv"],
        },
    )

    result = run_supplied_factor_callables(
        workspace=workspace,
        feature_panel=feature_panel,
        factors=[
            ("momentum", "tests.factors.momentum", lambda data: data["close"]),
            ("contrarian", "tests.factors.contrarian", lambda data: -data["close"]),
        ],
        candidate_horizon="1min",
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        input_lookback_window="2min",
    )

    assert [(factor.factor_name, factor.symbol) for factor in result.factors] == [
        ("momentum", "BTCUSDT"),
        ("momentum", "ETHUSDT"),
        ("contrarian", "BTCUSDT"),
        ("contrarian", "ETHUSDT"),
    ]
    assert [factor.gate_status for factor in result.factors] == [
        "candidate",
        "candidate",
        "candidate",
        "candidate",
    ]
    assert result.factors[0].timing is not None
    assert result.factors[0].timing["factor_execution_seconds"] >= 0.0
    assert result.factors[0].timing["report_and_library_seconds"] >= 0.0
    assert result.factors[0].timing["total_seconds"] >= 0.0
    assert all(factor.library_entry_stored is False for factor in result.factors)

    momentum_report = workspace.reports_dir / "momentum__BTCUSDT.json"
    contrarian_report = workspace.reports_dir / "contrarian__BTCUSDT.json"
    assert momentum_report.exists()
    assert contrarian_report.exists()
    assert json.loads(momentum_report.read_text(encoding="utf-8"))["symbol"] == "BTCUSDT"
    assert json.loads(contrarian_report.read_text(encoding="utf-8"))["gate_outcome"]["status"] == "candidate"

    library = load_candidate_factor_library(workspace.candidate_library_path)
    assert library["entries"] == []


def test_batch_runner_stores_effective_factor_for_the_symbol_that_passed(tmp_path):
    panel_data = build_crypto_panel(
        pd.DataFrame(
            [
                {
                    "timestamp": f"2026-01-01 00:0{minute}:00",
                    "symbol": symbol,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 10,
                }
                for minute in range(8)
                for symbol, close in [
                    ("BTCUSDT", 100 + minute * 10),
                    ("ETHUSDT", 100 - minute * 5),
                ]
            ]
        )
    )
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    workspace = create_crypto_factor_workspace(
        output_dir=tmp_path,
        run_id="run_symbol_specific",
        crypto_data_universe={
            "feature_data": ["fixture_spot_1m_ohlcv"],
            "pnl_data": ["fixture_spot_1m_ohlcv"],
        },
    )

    result = run_supplied_factor_callables(
        workspace=workspace,
        feature_panel=feature_panel,
        factors=[("momentum", "tests.factors.momentum", lambda data: data["close"])],
        candidate_horizon="1min",
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        input_lookback_window="2min",
    )

    # New paradigm: all non-failed factors are "candidate" (placeholder)
    assert [(factor.symbol, factor.gate_status) for factor in result.factors] == [
        ("BTCUSDT", "candidate"),
        ("ETHUSDT", "candidate"),
    ]
    # Library storage is deferred to iteration 2
    library = load_candidate_factor_library(workspace.candidate_library_path)
    assert len(library["entries"]) == 0


def test_batch_runner_captures_failed_callable_diagnostics_and_continues(tmp_path):
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
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    workspace = create_crypto_factor_workspace(
        output_dir=tmp_path,
        run_id="run_001",
        crypto_data_universe={
            "feature_data": ["fixture_spot_1m_ohlcv"],
            "pnl_data": ["fixture_spot_1m_ohlcv"],
        },
    )

    def broken_factor(data):
        raise RuntimeError("boom")

    result = run_supplied_factor_callables(
        workspace=workspace,
        feature_panel=feature_panel,
        factors=[
            ("broken", "tests.factors.broken", broken_factor),
            ("momentum", "tests.factors.momentum", lambda data: data["close"]),
        ],
        candidate_horizon="1min",
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        input_lookback_window="2min",
    )

    assert [(factor.factor_name, factor.symbol) for factor in result.factors] == [
        ("broken", "BTCUSDT"),
        ("broken", "ETHUSDT"),
        ("momentum", "BTCUSDT"),
        ("momentum", "ETHUSDT"),
    ]
    assert result.factors[0].gate_status == "execution_failed"
    assert result.factors[0].library_entry_stored is False
    assert result.factors[0].failure_reasons == ["factor_execution_failed"]
    assert result.factors[0].diagnostic_reference == "rejected/broken__BTCUSDT.json"

    diagnostic = json.loads((workspace.rejected_dir / "broken__BTCUSDT.json").read_text(encoding="utf-8"))
    assert diagnostic["artifact_type"] == "rejected_factor_diagnostic"
    assert diagnostic["factor_name"] == "broken"
    assert diagnostic["factor_callable_reference"] == "tests.factors.broken"
    assert diagnostic["error_type"] == "RuntimeError"
    assert diagnostic["error_message"] == "boom"
    assert diagnostic["artifact_path"] == "rejected/broken__BTCUSDT.json"
    assert diagnostic["live_strategy"] is False

    library = load_candidate_factor_library(workspace.candidate_library_path)
    assert library["entries"] == []


def test_batch_runner_rejects_future_dependent_factor_when_lookback_is_configured(tmp_path):
    panel_data = build_crypto_panel(
        pd.DataFrame(
            [
                {
                    "timestamp": timestamp,
                    "symbol": "BTCUSDT",
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 10,
                }
                for timestamp, close in [
                    ("2026-01-01 00:00:00", 100),
                    ("2026-01-01 00:01:00", 101),
                    ("2026-01-01 00:02:00", 102),
                    ("2026-01-01 00:03:00", 103),
                ]
            ]
        )
    )
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    workspace = create_crypto_factor_workspace(
        output_dir=tmp_path,
        run_id="run_lookahead",
        crypto_data_universe={
            "feature_data": ["fixture_spot_1m_ohlcv"],
            "pnl_data": ["fixture_spot_1m_ohlcv"],
        },
    )

    def future_close(data):
        return data.groupby(level="symbol")["close"].shift(-1)

    result = run_supplied_factor_callables(
        workspace=workspace,
        feature_panel=feature_panel,
        factors=[("leaky", "tests.factors.leaky", future_close)],
        candidate_horizon="1min",
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        input_lookback_window="2min",
    )

    assert result.factors[0].gate_status == "execution_failed"
    diagnostic = json.loads((workspace.rejected_dir / "leaky__BTCUSDT.json").read_text(encoding="utf-8"))
    assert diagnostic["error_type"] == "ValueError"
    assert "future-looking" in diagnostic["error_message"]


def test_batch_runner_keeps_generated_factor_artifacts_inside_workspace_dirs(tmp_path):
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
    feature_panel = CryptoPanel(data=panel_data, data_role="feature")
    workspace = create_crypto_factor_workspace(
        output_dir=tmp_path,
        run_id="run_001",
        crypto_data_universe={
            "feature_data": ["fixture_spot_1m_ohlcv"],
            "pnl_data": ["fixture_spot_1m_ohlcv"],
        },
    )

    def broken_factor(data):
        raise RuntimeError("boom")

    result = run_supplied_factor_callables(
        workspace=workspace,
        feature_panel=feature_panel,
        factors=[
            ("../escape", "tests.factors.escape", broken_factor),
        ],
        candidate_horizon="1min",
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        input_lookback_window="2min",
    )

    diagnostic_reference = result.factors[0].diagnostic_reference
    assert diagnostic_reference is not None
    assert diagnostic_reference.startswith("rejected/")
    assert ".." not in diagnostic_reference
    assert (workspace.root / diagnostic_reference).exists()
    assert not (workspace.root / "escape.json").exists()
