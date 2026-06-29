import json

import pandas as pd

from quantaalpha_crypto import (
    CryptoFactorSource,
    CryptoPanel,
    build_crypto_panel,
    create_crypto_factor_workspace,
    load_candidate_factor_library,
    run_crypto_factor_sources,
)


def test_crypto_factor_runner_executes_source_factors_through_evaluation_core(tmp_path):
    feature_panel, pnl_panel, workspace, evaluation_grid, walk_forward_settings = _fixture_run(tmp_path)

    result = run_crypto_factor_sources(
        workspace=workspace,
        feature_panel=feature_panel,
        pnl_panel=pnl_panel,
        factor_sources=[
            CryptoFactorSource(
                factor_name="momentum",
                factor_callable_reference="source.momentum",
                source_code="def factor(data):\n    return data['close']\n",
            )
        ],
        candidate_horizon="1min",
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
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

    library = load_candidate_factor_library(workspace.candidate_library_path)
    assert [entry["factor_callable_reference"] for entry in library["entries"]] == ["source.momentum"]
    assert [entry["symbol"] for entry in library["entries"]] == ["BTCUSDT"]


def test_crypto_factor_runner_converts_source_failures_to_rejected_diagnostics(tmp_path):
    feature_panel, pnl_panel, workspace, evaluation_grid, walk_forward_settings = _fixture_run(tmp_path)

    result = run_crypto_factor_sources(
        workspace=workspace,
        feature_panel=feature_panel,
        pnl_panel=pnl_panel,
        factor_sources=[
            CryptoFactorSource(
                factor_name="compile_bad",
                factor_callable_reference="source.compile_bad",
                source_code="def factor(data):\n    return data['close'\n",
            ),
            CryptoFactorSource(
                factor_name="import_bad",
                factor_callable_reference="source.import_bad",
                source_code="import qlib\n\ndef factor(data):\n    return data['close']\n",
            ),
            CryptoFactorSource(
                factor_name="runtime_bad",
                factor_callable_reference="source.runtime_bad",
                source_code="def factor(data):\n    raise RuntimeError('boom')\n",
            ),
            CryptoFactorSource(
                factor_name="index_bad",
                factor_callable_reference="source.index_bad",
                source_code="def factor(data):\n    return data['close'].reset_index(drop=True)\n",
            ),
            CryptoFactorSource(
                factor_name="type_bad",
                factor_callable_reference="source.type_bad",
                source_code="def factor(data):\n    return {'bad': 'not a series'}\n",
            ),
        ],
        candidate_horizon="1min",
        evaluation_grid=evaluation_grid,
        walk_forward_settings=walk_forward_settings,
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
    )

    assert [factor.gate_status for factor in result.factors] == ["execution_failed"] * 8
    assert [factor.library_entry_stored for factor in result.factors] == [False] * 8
    assert all(factor.diagnostic_reference is not None for factor in result.factors)

    diagnostics = [
        json.loads((workspace.root / factor.diagnostic_reference).read_text(encoding="utf-8"))
        for factor in result.factors
    ]
    assert [diagnostic["factor_name"] for diagnostic in diagnostics] == [
        "compile_bad",
        "import_bad",
        "runtime_bad",
        "runtime_bad",
        "index_bad",
        "index_bad",
        "type_bad",
        "type_bad",
    ]
    assert diagnostics[0]["error_type"] == "SyntaxError"
    assert diagnostics[1]["error_type"] in {"ImportError", "ModuleNotFoundError"}
    assert diagnostics[2]["error_type"] == "RuntimeError"
    assert diagnostics[3]["error_type"] == "RuntimeError"
    assert diagnostics[4]["error_type"] == "ValueError"
    assert diagnostics[5]["error_type"] == "ValueError"
    assert diagnostics[6]["error_type"] == "AttributeError"
    assert diagnostics[7]["error_type"] == "AttributeError"
    assert all(diagnostic["artifact_type"] == "rejected_factor_diagnostic" for diagnostic in diagnostics)


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
