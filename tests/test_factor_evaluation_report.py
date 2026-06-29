import pandas as pd

from quantaalpha_crypto import (
    EvaluationGridResult,
    EvaluationGridTrial,
    FactorEvaluation,
    FactorGateResult,
    WalkForwardValidationResult,
    WalkForwardWindow,
    WalkForwardWindowResult,
    build_factor_evaluation_report,
)


def test_factor_evaluation_report_records_dependencies_trials_selected_params_and_oos_metrics():
    factor_evaluation = _factor_evaluation()
    walk_forward_result = _walk_forward_result()
    gate_result = _gate_result()

    report = build_factor_evaluation_report(
        factor_name="close_momentum",
        factor_evaluation=factor_evaluation,
        walk_forward_result=walk_forward_result,
        gate_result=gate_result,
        feature_data_dependencies=["binance_spot_1m_ohlcv"],
        pnl_data_dependencies=["binance_spot_1m_ohlcv"],
    )

    assert report.factor_name == "close_momentum"
    assert report.feature_data_dependencies == ["binance_spot_1m_ohlcv"]
    assert report.pnl_data_dependencies == ["binance_spot_1m_ohlcv"]
    assert report.walk_forward_windows[0]["window"] == {
        "train_start": "2026-01-01 00:00:00",
        "train_end": "2026-01-01 00:01:00",
        "validation_start": "2026-01-01 00:01:00",
        "validation_end": "2026-01-01 00:02:00",
        "test_start": "2026-01-01 00:02:00",
        "test_end": "2026-01-01 00:03:00",
    }
    assert report.walk_forward_windows[0]["train_trials"] == [
        {
            "action": "spot_long",
            "threshold_quantile": 0.2,
            "holding_horizon": "0 days 00:01:00",
            "leverage": 1.0,
            "selected": False,
            "net_return": -0.01,
            "sharpe": -1.0,
            "turnover": 2.0,
            "fee": 0.002,
            "fee_rate": 0.0,
            "cost_source": "fallback",
        },
        {
            "action": "spot_long",
            "threshold_quantile": 0.8,
            "holding_horizon": "0 days 00:01:00",
            "leverage": 1.0,
            "selected": True,
            "net_return": 0.03,
            "sharpe": 1.5,
            "turnover": 2.0,
            "fee": 0.002,
            "fee_rate": 0.0,
            "cost_source": "fallback",
        },
    ]
    assert report.walk_forward_windows[0]["selected_parameters"] == {
        "action": "spot_long",
        "threshold_quantile": 0.8,
        "holding_horizon": "0 days 00:01:00",
        "leverage": 1.0,
    }
    assert report.walk_forward_windows[0]["validation_metrics"] == {
        "net_return": 0.02,
        "sharpe": 1.0,
    }
    assert report.walk_forward_windows[0]["test_metrics"] == {
        "net_return": 0.01,
        "sharpe": 0.9,
    }


def test_factor_evaluation_report_records_cost_risk_ic_groups_gate_and_research_status():
    factor_evaluation = _factor_evaluation_with_train_and_test_rows()
    walk_forward_result = _walk_forward_result()
    gate_result = _gate_result()

    report = build_factor_evaluation_report(
        factor_name="close_momentum",
        factor_evaluation=factor_evaluation,
        walk_forward_result=walk_forward_result,
        gate_result=gate_result,
        feature_data_dependencies=["binance_spot_1m_ohlcv"],
        pnl_data_dependencies=["binance_spot_1m_ohlcv"],
    )

    assert report.cost_summary == {
        "cost_sources": ["fallback"],
        "uses_cost_fallback": True,
        "total_fee": 0.004,
        "total_turnover": 4.0,
        "total_funding_return": 0.0,
    }
    assert report.risk_summary == {"test_max_drawdown": 0.0}
    assert report.ic_stability == {
        "ic_same_sign_rate": 1.0,
        "mean_rank_ic": 1.0,
        "abs_mean_rank_ic": 1.0,
    }
    assert report.grouped_returns == [
        {"group": 1, "mean_forward_return": -0.01},
        {"group": 2, "mean_forward_return": 0.02},
    ]
    assert report.gate_outcome == {
        "status": "candidate",
        "failure_reasons": [],
        "strong_failure_reasons": ["low_strong_test_sharpe"],
        "test_sharpe": 0.9,
    }
    assert "cost_source_fallback" in report.limitations
    assert report.live_strategy is False
    assert "live strategy" not in report.summary.lower()


def test_factor_evaluation_report_handles_incomplete_walk_forward_windows():
    factor_evaluation = _factor_evaluation()
    gate_result = _gate_result()
    walk_forward_result = WalkForwardValidationResult(
        windows=[
            WalkForwardWindowResult(
                window=WalkForwardWindow(
                    train_start=pd.Timestamp("2026-01-01 00:00:00"),
                    train_end=pd.Timestamp("2026-01-01 00:01:00"),
                    validation_start=pd.Timestamp("2026-01-01 00:01:00"),
                    validation_end=pd.Timestamp("2026-01-01 00:02:00"),
                    test_start=pd.Timestamp("2026-01-01 00:02:00"),
                    test_end=pd.Timestamp("2026-01-01 00:03:00"),
                ),
                train_result=EvaluationGridResult(trials=[]),
                validation_result=EvaluationGridResult(trials=[]),
                test_result=EvaluationGridResult(trials=[]),
            )
        ]
    )

    report = build_factor_evaluation_report(
        factor_name="close_momentum",
        factor_evaluation=factor_evaluation,
        walk_forward_result=walk_forward_result,
        gate_result=gate_result,
        feature_data_dependencies=["binance_spot_1m_ohlcv"],
        pnl_data_dependencies=["binance_spot_1m_ohlcv"],
    )

    assert report.walk_forward_windows[0]["selected_parameters"] is None
    assert report.walk_forward_windows[0]["validation_metrics"] is None
    assert report.walk_forward_windows[0]["test_metrics"] is None


def _factor_evaluation() -> FactorEvaluation:
    index = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2026-01-01 00:00:00"), "BTCUSDT"),
            (pd.Timestamp("2026-01-01 00:00:00"), "ETHUSDT"),
        ],
        names=["timestamp", "symbol"],
    )
    return FactorEvaluation(
        horizon=pd.Timedelta("1min"),
        scores=pd.Series([1.0, 2.0], index=index),
        forward_returns=pd.Series([0.01, 0.02], index=index),
        ic=1.0,
        rank_ic=1.0,
    )


def _factor_evaluation_with_train_and_test_rows() -> FactorEvaluation:
    index = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2026-01-01 00:00:00"), "BTCUSDT"),
            (pd.Timestamp("2026-01-01 00:00:00"), "ETHUSDT"),
            (pd.Timestamp("2026-01-01 00:02:00"), "BTCUSDT"),
            (pd.Timestamp("2026-01-01 00:02:00"), "ETHUSDT"),
        ],
        names=["timestamp", "symbol"],
    )
    return FactorEvaluation(
        horizon=pd.Timedelta("1min"),
        scores=pd.Series([1.0, 2.0, 1.0, 2.0], index=index),
        forward_returns=pd.Series([-0.10, -0.20, 0.03, 0.04], index=index),
        ic=float("nan"),
        rank_ic=float("nan"),
    )


def _walk_forward_result() -> WalkForwardValidationResult:
    window = WalkForwardWindow(
        train_start=pd.Timestamp("2026-01-01 00:00:00"),
        train_end=pd.Timestamp("2026-01-01 00:01:00"),
        validation_start=pd.Timestamp("2026-01-01 00:01:00"),
        validation_end=pd.Timestamp("2026-01-01 00:02:00"),
        test_start=pd.Timestamp("2026-01-01 00:02:00"),
        test_end=pd.Timestamp("2026-01-01 00:03:00"),
    )
    return WalkForwardValidationResult(
        windows=[
            WalkForwardWindowResult(
                window=window,
                train_result=EvaluationGridResult(
                    trials=[
                        _trial(
                            threshold_quantile=0.2,
                            net_return=-0.01,
                            sharpe=-1.0,
                        ),
                        _trial(
                            threshold_quantile=0.8,
                            net_return=0.03,
                            sharpe=1.5,
                            selected=True,
                        ),
                    ],
                    selected_trial=_trial(
                        threshold_quantile=0.8,
                        net_return=0.03,
                        sharpe=1.5,
                        selected=True,
                    ),
                ),
                validation_result=EvaluationGridResult(
                    trials=[_trial(threshold_quantile=0.8, net_return=0.02, sharpe=1.0)]
                ),
                test_result=EvaluationGridResult(
                    trials=[
                        _trial(
                            threshold_quantile=0.8,
                            net_return=0.01,
                            sharpe=0.9,
                            grouped_returns=(
                                {"group": 1, "mean_forward_return": -0.01},
                                {"group": 2, "mean_forward_return": 0.02},
                            ),
                        )
                    ]
                ),
            )
        ],
        validation_net_return=0.02,
        test_net_return=0.01,
    )


def _trial(
    threshold_quantile: float,
    net_return: float,
    sharpe: float,
    selected: bool = False,
    grouped_returns: tuple[dict, ...] = (),
) -> EvaluationGridTrial:
    return EvaluationGridTrial(
        action="spot_long",
        threshold_quantile=threshold_quantile,
        holding_horizon=pd.Timedelta("1min"),
        leverage=1.0,
        turnover=2.0,
        fee=0.002,
        cost_source="fallback",
        uses_cost_fallback=True,
        net_return=net_return,
        sharpe=sharpe,
        grouped_returns=grouped_returns,
        selected=selected,
    )


def _gate_result() -> FactorGateResult:
    return FactorGateResult(
        status="candidate",
        failure_reasons=[],
        strong_failure_reasons=["low_strong_test_sharpe"],
        ic_same_sign_rate=1.0,
        mean_rank_ic=1.0,
        abs_mean_rank_ic=1.0,
        test_sharpe=0.9,
    )
