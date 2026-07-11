"""Tests for RefreshManager."""

import time
from unittest.mock import patch

from writerdeck.display.refresh_manager import RefreshManager


def test_first_refresh_is_full():
    rm = RefreshManager(max_streak=5)
    assert rm.should_full_refresh() is True


def test_partial_streak_triggers_full():
    rm = RefreshManager(max_streak=3, idle_full_seconds=999)
    rm.record_refresh(was_full=True)

    for _ in range(3):
        assert rm.should_full_refresh() is False
        rm.record_refresh(was_full=False)

    # After 3 partials, should require full
    assert rm.should_full_refresh() is True


def test_full_refresh_resets_streak():
    rm = RefreshManager(max_streak=3, idle_full_seconds=999)
    rm.record_refresh(was_full=True)

    rm.record_refresh(was_full=False)
    rm.record_refresh(was_full=False)
    rm.record_refresh(was_full=True)  # reset

    assert rm.should_full_refresh() is False


def test_request_full():
    rm = RefreshManager(max_streak=100, idle_full_seconds=999)
    rm.record_refresh(was_full=True)
    assert rm.should_full_refresh() is False

    rm.request_full()
    assert rm.should_full_refresh() is True


def test_idle_triggers_full():
    rm = RefreshManager(max_streak=100, idle_full_seconds=0)
    rm.record_refresh(was_full=True)
    # idle_full_seconds=0 means any elapsed time triggers full
    time.sleep(0.01)
    assert rm.should_full_refresh() is True


def test_five_partials_triggers_full():
    # Good Display spec: full refresh after every 5 partials.
    rm = RefreshManager(max_streak=5, idle_full_seconds=999, full_refresh_max_seconds=999)
    rm.record_refresh(was_full=True)

    for _ in range(5):
        assert rm.should_full_refresh() is False
        rm.record_refresh(was_full=False)

    assert rm.should_full_refresh() is True


def test_wall_clock_backstop_forces_full():
    # Neither streak nor idle triggers; only the wall-clock backstop should.
    with patch("writerdeck.display.refresh_manager.time.monotonic") as mono:
        mono.return_value = 1000.0
        rm = RefreshManager(
            max_streak=100, idle_full_seconds=999, full_refresh_max_seconds=300
        )
        rm.record_refresh(was_full=True)  # _last_full_time = 1000

        # Just before the backstop window elapses — still partial.
        mono.return_value = 1000.0 + 299
        rm.record_refresh(was_full=False)  # keep idle timer fresh
        assert rm.should_full_refresh() is False

        # Past the backstop window — force full.
        mono.return_value = 1000.0 + 301
        rm.record_refresh(was_full=False)
        assert rm.should_full_refresh() is True


def test_wall_clock_backstop_resets_after_full():
    with patch("writerdeck.display.refresh_manager.time.monotonic") as mono:
        mono.return_value = 0.0
        rm = RefreshManager(
            max_streak=100, idle_full_seconds=999, full_refresh_max_seconds=300
        )
        rm.record_refresh(was_full=True)

        # Cross the backstop → full → record it as full to reset _last_full_time.
        mono.return_value = 400.0
        assert rm.should_full_refresh() is True
        rm.record_refresh(was_full=True)  # resets _last_full_time to 400

        # Shortly after, no backstop trigger anymore.
        mono.return_value = 401.0
        rm.record_refresh(was_full=False)
        assert rm.should_full_refresh() is False


# ---------------------------------------------------------------------------
# PERF-4: idle-full timer measures against the last KEYPRESS, not the refresh
# ---------------------------------------------------------------------------


def test_keypress_after_short_pause_takes_partial_path():
    # Typing slower than idle_full_seconds, or pausing then resuming, must NOT
    # force a full refresh — the idle timer resets on each keypress.
    with patch("writerdeck.display.refresh_manager.time.monotonic") as mono:
        mono.return_value = 0.0
        rm = RefreshManager(
            max_streak=100, idle_full_seconds=10, full_refresh_max_seconds=999
        )
        rm.note_keypress()
        rm.record_refresh(was_full=True)  # first frame rendered

        # 8s pause (< 10s idle window) then a keypress resets the timer.
        mono.return_value = 8.0
        rm.note_keypress()
        # Even though 8s elapsed since the *refresh*, the keypress just fired,
        # so this stays on the partial path.
        assert rm.should_full_refresh() is False


def test_genuine_long_idle_still_forces_full():
    # No keypress for longer than idle_full_seconds → full refresh (the
    # intended idle clean is preserved).
    with patch("writerdeck.display.refresh_manager.time.monotonic") as mono:
        mono.return_value = 0.0
        rm = RefreshManager(
            max_streak=100, idle_full_seconds=10, full_refresh_max_seconds=999
        )
        rm.note_keypress()
        rm.record_refresh(was_full=True)

        # 15s with no keypress — genuine idle → force full.
        mono.return_value = 15.0
        assert rm.should_full_refresh() is True


def test_slow_typing_does_not_blink():
    # A refresh happening well after the last keypress does not itself reset the
    # idle timer — only note_keypress() does — so consecutive slow keystrokes
    # (each with a fresh keypress) never blink.
    with patch("writerdeck.display.refresh_manager.time.monotonic") as mono:
        mono.return_value = 100.0
        rm = RefreshManager(
            max_streak=100, idle_full_seconds=5, full_refresh_max_seconds=999
        )
        rm.note_keypress()
        rm.record_refresh(was_full=True)

        # Keystroke every 4s (< 5s window): each resets the timer → partial.
        for t in (104.0, 108.0, 112.0):
            mono.return_value = t
            rm.note_keypress()
            assert rm.should_full_refresh() is False
            rm.record_refresh(was_full=False)
