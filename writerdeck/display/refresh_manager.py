"""Refresh manager — decides between partial and full refresh."""

from __future__ import annotations

import time


class RefreshManager:
    def __init__(
        self,
        max_streak: int = 20,
        idle_full_seconds: int = 10,
        full_refresh_max_seconds: int = 300,
    ) -> None:
        self._max_streak = max_streak
        self._idle_full_seconds = idle_full_seconds
        self._full_refresh_max_seconds = full_refresh_max_seconds
        self._partial_streak = 0
        self._last_full_time = time.monotonic()
        # PERF-4: the idle-full timer measures time since the last *keypress*,
        # not the last refresh, so pausing to think then resuming doesn't force
        # a surprise full-refresh blink on the next keystroke. Seeded to now so
        # a fresh manager doesn't immediately report "idle".
        self._last_keypress_time = time.monotonic()
        self._force_full = True  # first frame is always full

    def note_keypress(self) -> None:
        """Record a keypress so the idle-full timer resets (PERF-4)."""
        self._last_keypress_time = time.monotonic()

    def request_full(self) -> None:
        self._force_full = True

    def should_full_refresh(self, ignore_streak: bool = False) -> bool:
        if self._force_full:
            return True
        if not ignore_streak and self._partial_streak >= self._max_streak:
            return True
        # Idle-full: measured against the last keypress (PERF-4). A brief
        # pause-then-type takes the partial path; genuine long idle still fulls.
        if time.monotonic() - self._last_keypress_time >= self._idle_full_seconds:
            return True
        # Wall-clock backstop: force a full refresh at least this often,
        # independent of streak/idle, to keep ghosting in check during long
        # steady-typing sessions that never idle and never hit the streak.
        return time.monotonic() - self._last_full_time >= self._full_refresh_max_seconds

    def record_refresh(self, was_full: bool) -> None:
        if was_full:
            self._partial_streak = 0
            self._force_full = False
            self._last_full_time = time.monotonic()
        else:
            self._partial_streak += 1
