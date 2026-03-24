"""Status bar — timed messages shown at the top of the display."""

from __future__ import annotations

import time


class StatusBar:
    def __init__(self) -> None:
        self._message: str | None = None
        self._expires_at: float = 0.0

    def show(self, message: str, duration: float = 3.0) -> None:
        """Show a status message for the given duration (seconds)."""
        self._message = message
        self._expires_at = time.monotonic() + duration

    @property
    def current(self) -> str | None:
        """Return the current message, or None if expired."""
        if self._message is None:
            return None
        if time.monotonic() > self._expires_at:
            self._message = None
            return None
        return self._message
