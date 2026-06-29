from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from quantaalpha_crypto.evaluation.metrics import _forward_returns
from quantaalpha_crypto.evaluation.panel import CryptoPanel


FactorCallable = Callable[[pd.DataFrame], pd.Series]


@dataclass(frozen=True)
class FactorEvaluation:
    horizon: pd.Timedelta
    scores: pd.Series
    forward_returns: pd.Series
    ic: float
    rank_ic: float


def evaluate_directional_factor(
    feature_panel: CryptoPanel,
    factor: FactorCallable,
    horizon: str | pd.Timedelta,
    input_lookback_window: str | pd.Timedelta | None = None,
    input_audit_sample_count: int = 16,
) -> FactorEvaluation:
    """Evaluate one Directional Factor against one Forward Return horizon."""
    if feature_panel.data_role != "feature":
        raise ValueError("Directional Factor evaluation requires Feature Data")
    horizon_delta = pd.Timedelta(horizon)
    scores = _normalize_scores(factor(feature_panel.data))
    if input_lookback_window is not None:
        _audit_factor_inputs(
            data=feature_panel.data,
            factor=factor,
            scores=scores,
            input_lookback_window=pd.Timedelta(input_lookback_window),
            sample_count=input_audit_sample_count,
        )
    forward_returns = _forward_returns(
        feature_panel.data,
        horizon_delta,
        price_column=_default_close_column(feature_panel.data),
    )
    aligned = pd.concat(
        [scores.rename("score"), forward_returns.rename("forward_return")],
        axis=1,
        join="inner",
    ).dropna()

    return FactorEvaluation(
        horizon=horizon_delta,
        scores=aligned["score"],
        forward_returns=aligned["forward_return"],
        ic=_corr(aligned["score"], aligned["forward_return"]),
        rank_ic=_corr(aligned["score"].rank(), aligned["forward_return"].rank()),
    )


def _normalize_scores(scores: pd.Series) -> pd.Series:
    if not isinstance(scores.index, pd.MultiIndex) or scores.index.names != [
        "timestamp",
        "symbol",
    ]:
        raise ValueError("factor scores must be indexed by timestamp and symbol")
    return pd.to_numeric(scores, errors="raise").astype("float64").sort_index()


def _audit_factor_inputs(
    data: pd.DataFrame,
    factor: FactorCallable,
    scores: pd.Series,
    input_lookback_window: pd.Timedelta,
    sample_count: int,
) -> None:
    if input_lookback_window <= pd.Timedelta(0):
        raise ValueError("input_lookback_window must be positive")
    if sample_count <= 0:
        raise ValueError("input_audit_sample_count must be positive")

    audited_scores = scores.dropna()
    if audited_scores.empty:
        return

    timestamps = audited_scores.index.get_level_values("timestamp")
    data_timestamps = data.index.get_level_values("timestamp")
    for timestamp in _sample_timestamps(timestamps, sample_count):
        window_start = timestamp - input_lookback_window
        window_data = data[
            (data_timestamps >= window_start)
            & (data_timestamps <= timestamp)
        ]
        window_scores = _normalize_scores(factor(window_data))
        expected = audited_scores.xs(timestamp, level="timestamp", drop_level=False)
        observed = window_scores.reindex(expected.index)
        if observed.isna().any() or not _scores_close_enough(observed, expected):
            raise ValueError(
                "factor scores depend on future-looking data or data outside input_lookback_window"
            )


def _sample_timestamps(timestamps: pd.Index, sample_count: int) -> list[pd.Timestamp]:
    unique = pd.Index(timestamps).drop_duplicates().sort_values()
    if len(unique) <= sample_count:
        return [pd.Timestamp(timestamp) for timestamp in unique]

    positions = {
        round(position * (len(unique) - 1) / (sample_count - 1))
        for position in range(sample_count)
    }
    return [pd.Timestamp(unique[position]) for position in sorted(positions)]


def _scores_close_enough(observed: pd.Series, expected: pd.Series) -> bool:
    tolerance = 1e-12 + 1e-10 * expected.abs()
    return bool(((observed - expected).abs() <= tolerance).all())


def _default_close_column(data: pd.DataFrame) -> str:
    for column in ("close", "futures_close", "spot_close"):
        if column in data:
            return column
    raise ValueError("factor evaluation requires close, futures_close, or spot_close")


def _corr(left: pd.Series, right: pd.Series) -> float:
    if len(left) < 2:
        return float("nan")
    if left.nunique(dropna=True) < 2 or right.nunique(dropna=True) < 2:
        return float("nan")
    return float(left.corr(right))
