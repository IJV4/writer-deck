"""Tests for RefreshManager."""

import time
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
