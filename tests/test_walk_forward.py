"""Tests for walk-forward window construction (`evaluation/walk_forward.py`).

Iteration 1.1: rolling, two-segment (train/test) walk-forward with purge applied
by timestamp. Purge removes training samples whose label window reaches into the
test period; the leak boundary is entry-aligned (``entry + horizon`` where
``entry`` is the next bar per the t+1 execution lag), matching ``_forward_returns``.
"""

import pandas as pd
import pytest

from quantaalpha_crypto.evaluation.walk_forward import (
    WalkForwardWindow,
    build_walk_forward_windows,
)


def _index(
    symbols: list[str], n: int, freq: str = "1D", start: str = "2024-01-01"
) -> pd.MultiIndex:
    tuples = []
    for symbol in symbols:
        for timestamp in pd.date_range(start, periods=n, freq=freq):
            tuples.append((timestamp, symbol))
    return pd.MultiIndex.from_tuples(tuples, names=["timestamp", "symbol"])


def test_tracer_basic_two_segment_split():
    # 10 daily bars, one symbol; train 3D / test 1D / step 1D.
    index = _index(["BTCUSDT"], n=10, freq="1D")
    windows = build_walk_forward_windows(
        index, horizon="1D", train_window="3D", test_window="1D", step="1D"
    )

    assert windows
    assert all(isinstance(w, WalkForwardWindow) for w in windows)

    first = windows[0]
    assert first.train_start == pd.Timestamp("2024-01-01")
    assert first.test_start == pd.Timestamp("2024-01-04")
    assert first.test_end == pd.Timestamp("2024-01-05")

    # Test segment holds exactly the bars in [test_start, test_end).
    test_ts = first.test_index.get_level_values("timestamp")
    assert list(test_ts) == [pd.Timestamp("2024-01-04")]

    # Training segment lies strictly before the test period.
    train_ts = first.train_index.get_level_values("timestamp")
    assert train_ts.max() < first.test_start


def test_purge_removes_training_rows_whose_label_reaches_into_test():
    # Daily bars; train 5D / test 2D; horizon 2D. First test_start = 2024-01-06.
    # Purge uses the entry-aligned leak boundary: a row at t enters at the NEXT
    # bar (t+1 bar, execution lag), exits at entry+horizon, and leaks iff
    # entry+horizon >= test_start.
    #   t=01-05: entry 01-06, exit 01-08 -> leaks -> purge
    #   t=01-04: entry 01-05, exit 01-07 -> leaks -> purge
    #   t=01-03: entry 01-04, exit 01-06 -> leaks (touches) -> purge
    #   t=01-02: entry 01-03, exit 01-05 -> clean -> keep
    #   t=01-01: entry 01-02, exit 01-04 -> clean -> keep
    index = _index(["BTCUSDT"], n=12, freq="1D")
    windows = build_walk_forward_windows(
        index, horizon="2D", train_window="5D", test_window="2D", step="2D"
    )

    first = windows[0]
    assert first.test_start == pd.Timestamp("2024-01-06")
    train_ts = list(first.train_index.get_level_values("timestamp"))
    assert train_ts == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")]


def test_purge_is_by_timestamp_across_a_gap_not_bar_count():
    # A gap between 01-04 and 01-20 exposes timestamp-vs-bar-count purge. The
    # bar at 01-04 enters at the NEXT available bar (01-20, across the gap) and
    # exits 01-22 -> its label window spans the gap into the test, so it leaks
    # and must be purged. 01-03 enters 01-04, exits 01-06 -> clean. A bar-count
    # purge ("drop the last N bars") would mis-purge here; timestamps get it right.
    stamps = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04",
              "2024-01-20", "2024-01-21", "2024-01-22"]
    index = pd.MultiIndex.from_tuples(
        [(pd.Timestamp(s), "BTCUSDT") for s in stamps], names=["timestamp", "symbol"]
    )
    windows = build_walk_forward_windows(
        index, horizon="2D", train_window="19D", test_window="2D", step="19D"
    )

    first = windows[0]
    assert first.test_start == pd.Timestamp("2024-01-20")
    train_ts = list(first.train_index.get_level_values("timestamp"))
    assert train_ts == [
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2024-01-03"),
    ]


def test_no_partial_trailing_window():
    # Windows stop before spilling past the data: no test segment exceeds the
    # last available timestamp.
    index = _index(["BTCUSDT"], n=10, freq="1D")
    windows = build_walk_forward_windows(
        index, horizon="1D", train_window="3D", test_window="1D", step="1D"
    )
    assert windows[-1].test_end <= pd.Timestamp("2024-01-10")


def test_empty_index_returns_no_windows():
    empty = pd.MultiIndex.from_arrays(
        [pd.DatetimeIndex([]), []], names=["timestamp", "symbol"]
    )
    assert build_walk_forward_windows(empty, horizon="1D") == []


@pytest.mark.parametrize("bad", ["0D", "-5D"])
def test_non_positive_windows_raise(bad):
    index = _index(["BTCUSDT"], n=10, freq="1D")
    with pytest.raises(ValueError):
        build_walk_forward_windows(index, horizon="1D", train_window=bad)
    with pytest.raises(ValueError):
        build_walk_forward_windows(index, horizon="1D", test_window=bad)
    with pytest.raises(ValueError):
        build_walk_forward_windows(index, horizon="1D", step=bad)
