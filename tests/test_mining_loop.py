"""Tests for the iteration 0.3 single-factor verdict (`mining/loop.py`)."""

import math

import pandas as pd

from quantaalpha_crypto import CryptoPanel, build_crypto_panel
from quantaalpha_crypto.mining.loop import (
    SingleFactorVerdict,
    _verdict_label,
    format_verdict,
    judge_single_factor,
)


def _uptrend_panel(n: int = 150, symbol: str = "BTCUSDT") -> CryptoPanel:
    timestamps = pd.date_range("2026-01-01", periods=n, freq="1min")
    prices = [100.0 * (1.002 ** i) for i in range(n)]
    raw = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": symbol,
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": 10,
        }
    )
    return CryptoPanel(data=build_crypto_panel(raw), data_role="feature")


def test_verdict_label_thresholds():
    assert _verdict_label(float("nan"), 2.0) == "insufficient-data"
    assert _verdict_label(0.5, 2.0) == "indistinguishable-from-noise"
    assert _verdict_label(3.0, 2.0) == "signal"
    assert _verdict_label(-3.0, 2.0) == "signal"


def test_judge_single_factor_runs_end_to_end():
    # The skeleton's job: data -> factor -> full-sample IC + NW t-stat -> verdict.
    panel = _uptrend_panel()
    verdict = judge_single_factor(panel, lambda data: data["close"], horizon="3min")

    assert isinstance(verdict, SingleFactorVerdict)
    assert verdict.horizon == pd.Timedelta("3min")
    assert verdict.verdict in {
        "signal",
        "indistinguishable-from-noise",
        "insufficient-data",
    }
    # NW t-stat is either a real number or NaN (never an exception leaking out).
    assert math.isnan(verdict.nw_tstat) or math.isfinite(verdict.nw_tstat)


def test_judge_single_factor_respects_threshold():
    # An impossibly high bar forces the noise verdict regardless of the estimate.
    panel = _uptrend_panel()
    verdict = judge_single_factor(
        panel, lambda data: data["close"], horizon="3min", t_threshold=1e9
    )
    assert verdict.verdict in {"indistinguishable-from-noise", "insufficient-data"}


def test_format_verdict_contains_metrics():
    verdict = SingleFactorVerdict(
        horizon=pd.Timedelta("3min"),
        ic=0.1234,
        rank_ic=-0.0567,
        nw_tstat=2.5,
        verdict="signal",
    )
    text = format_verdict(verdict)
    assert "IC=+0.1234" in text
    assert "NW_t=+2.50" in text
    assert "signal" in text
