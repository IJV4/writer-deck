"""Refresh manager — decides between partial and full refresh."""

from __future__ import annotations

import time


class RefreshManager:
    def __init__(self, max_streak: int = 20, idle_full_seconds: int = 10) -> None:
        self._max_streak = max_streak
        self._idle_full_seconds = idle_full_seconds
        self._partial_streak = 0
        self._last_refresh_time = time.monotonic()
        self._force_full = True  # first frame is always full

    def request_full(self) -> None:
        self._force_full = True

    def should_full_refresh(self) -> bool:
        if self._force_full:
            return True
        if self._partial_streak >= self._max_streak:
            return True
        if time.monotonic() - self._last_refresh_time >= self._idle_full_seconds:
            return True
        return False

    def should_full_refresh_no_streak(self) -> bool:
        """Like should_full_refresh() but ignores the streak counter.

        Used during active typing so that streak-based full refreshes don't
        cause 1-second interruptions mid-burst.  Force and idle-timer triggers
        still fire normally; ghosting is cleaned up when the user pauses.
        """
        if self._force_full:
            return True
        if time.monotonic() - self._last_refresh_time >= self._idle_full_seconds:
            return True
        return False

    def record_refresh(self, was_full: bool) -> None:
        if was_full:
            self._partial_streak = 0
            self._force_full = False
        else:
            self._partial_streak += 1
        self._last_refresh_time = time.monotonic()
