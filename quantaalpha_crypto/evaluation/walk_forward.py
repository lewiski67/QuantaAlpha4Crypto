from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def _label_exit_timestamps(
    sample_index: pd.MultiIndex,
    horizon: pd.Timedelta,
    execution_lag_bars: int,
) -> pd.Series:
    """Exit timestamp of each sample's Forward Return label window.

    Mirrors ``_forward_returns`` alignment: entry is the bar
    ``execution_lag_bars`` ahead (positional, per symbol) and exit is
    ``entry + horizon``. Samples near a symbol's tail whose entry runs off the
    end get ``NaT``. Returned in ``sample_index`` order.
    """
    pieces = []
    frame = pd.DataFrame(index=sample_index).sort_index()
    for _symbol, symbol_rows in frame.groupby(level="symbol", sort=False):
        timestamps = symbol_rows.index.get_level_values("timestamp")
        entry = pd.DatetimeIndex(pd.Series(timestamps).shift(-execution_lag_bars))
        pieces.append(pd.Series(entry + horizon, index=symbol_rows.index))
    exit_series = pd.concat(pieces) if pieces else pd.Series(dtype="datetime64[ns]")
    return exit_series.reindex(sample_index)


@dataclass(frozen=True)
class WalkForwardWindow:
    train_index: pd.MultiIndex
    test_index: pd.MultiIndex
    train_start: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def build_walk_forward_windows(
    sample_index: pd.MultiIndex,
    horizon: str | pd.Timedelta,
    train_window: str = "180D",
    test_window: str = "30D",
    step: str = "30D",
    execution_lag_bars: int = 1,
) -> list[WalkForwardWindow]:
    """Build rolling, two-segment (train/test) walk-forward windows.

    ``sample_index`` is the aligned evaluation index (``[timestamp, symbol]``).
    Each window carries the train and test sample subsets; the test segment holds
    the bars in ``[test_start, test_end)`` and the train segment the bars before
    ``test_start``, with **purge** applied: a training sample whose Forward Return
    label window reaches into the test period is dropped. The leak boundary is
    entry-aligned to match ``_forward_returns`` -- a sample enters at the next bar
    (``execution_lag_bars``) and exits ``horizon`` later, so it leaks iff
    ``entry + horizon >= test_start``. Purge by timestamp, not bar count, so
    irregular bar spacing (gaps) cannot mis-purge.
    """
    if len(sample_index) == 0:
        return []
    timestamps = sample_index.get_level_values("timestamp")
    start_at = pd.Timestamp(timestamps.min())
    end_at = pd.Timestamp(timestamps.max())
    horizon_delta = pd.Timedelta(horizon)
    train_delta = pd.Timedelta(train_window)
    test_delta = pd.Timedelta(test_window)
    step_delta = pd.Timedelta(step)
    if any(
        delta <= pd.Timedelta(0) for delta in (train_delta, test_delta, step_delta)
    ):
        raise ValueError("walk-forward windows and step must be positive")

    label_exit = _label_exit_timestamps(
        sample_index, horizon_delta, execution_lag_bars
    )

    windows: list[WalkForwardWindow] = []
    train_start = start_at
    while True:
        test_start = train_start + train_delta
        test_end = test_start + test_delta
        if test_end > end_at + pd.Timedelta("1ns"):
            break
        # Purge: keep a training row only if its label window exits before the
        # test period (a NaT exit -- no valid label -- never enters training).
        clean = (label_exit < test_start).to_numpy()
        train_mask = (timestamps < test_start) & clean
        test_mask = (timestamps >= test_start) & (timestamps < test_end)
        windows.append(
            WalkForwardWindow(
                train_index=sample_index[train_mask],
                test_index=sample_index[test_mask],
                train_start=train_start,
                test_start=test_start,
                test_end=test_end,
            )
        )
        train_start = train_start + step_delta

    return windows
