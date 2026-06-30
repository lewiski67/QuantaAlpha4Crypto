from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def build_walk_forward_windows(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    train_window: str = "180D",
    validation_window: str = "30D",
    test_window: str = "30D",
    step: str = "30D",
) -> list[WalkForwardWindow]:
    """Build right-open, time-ordered walk-forward windows."""
    start_at = pd.Timestamp(start)
    end_at = pd.Timestamp(end)
    train_delta = pd.Timedelta(train_window)
    validation_delta = pd.Timedelta(validation_window)
    test_delta = pd.Timedelta(test_window)
    step_delta = pd.Timedelta(step)
    if any(
        delta <= pd.Timedelta(0)
        for delta in (train_delta, validation_delta, test_delta, step_delta)
    ):
        raise ValueError("walk-forward windows and step must be positive")

    windows: list[WalkForwardWindow] = []
    train_start = start_at
    while True:
        train_end = train_start + train_delta
        validation_end = train_end + validation_delta
        test_end = validation_end + test_delta
        if test_end > end_at:
            break
        windows.append(
            WalkForwardWindow(
                train_start=train_start,
                train_end=train_end,
                validation_start=train_end,
                validation_end=validation_end,
                test_start=validation_end,
                test_end=test_end,
            )
        )
        train_start = train_start + step_delta

    return windows


def _validate_window(window: WalkForwardWindow) -> None:
    if not (
        window.train_start < window.train_end
        <= window.validation_start
        < window.validation_end
        <= window.test_start
        < window.test_end
    ):
        raise ValueError("walk-forward windows must be time ordered")
