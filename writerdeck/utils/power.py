"""Battery / power management via PiSugar daemon."""

from __future__ import annotations

import logging
import os
import socket
import threading
import time
from collections import deque

logger = logging.getLogger(__name__)


class Power:
    def __init__(
        self,
        socket_path: str = "/tmp/pisugar-server.sock",
        warning_pct: int = 15,
        shutdown_pct: int = 3,
        check_interval: int = 60,
        enabled: bool = True,
    ) -> None:
        self._socket_path = socket_path
        self._warning_pct = warning_pct
        self._shutdown_pct = shutdown_pct
        self._check_interval = check_interval
        self._enabled = enabled

        self.battery_level: int = 100
        self.is_charging: bool = False
        self.is_low: bool = False
        self._available = False
        self._shutdown_callback: callable | None = None

        self._thread: threading.Thread | None = None
        self._running = False

        # Battery history for drain rate estimation
        self._history: deque[tuple[float, int]] = deque(maxlen=60)

    def start(self, shutdown_callback: callable | None = None) -> None:
        if not self._enabled:
            return
        self._shutdown_callback = shutdown_callback
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    @property
    def available(self) -> bool:
        return self._available

    def battery_bar(self, width: int = 5) -> str:
        filled = int(self.battery_level / 100 * width)
        suffix = "+" if self.is_charging else ""
        return "[" + "\u25a0" * filled + "\u25a1" * (width - filled) + f"] {self.battery_level}%{suffix}"

    @property
    def drain_rate_pct_per_hour(self) -> float | None:
        """Compute battery drain rate in %/hour from history. None if insufficient data."""
        if len(self._history) < 2:
            return None
        oldest_time, oldest_level = self._history[0]
        newest_time, newest_level = self._history[-1]
        elapsed_hours = (newest_time - oldest_time) / 3600
        if elapsed_hours < 0.01:  # need at least ~36 seconds
            return None
        drain = oldest_level - newest_level
        if drain <= 0:
            return None  # charging or no drain
        return drain / elapsed_hours

    @property
    def estimated_remaining_hours(self) -> float | None:
        """Estimate remaining battery life in hours. None if cannot estimate."""
        rate = self.drain_rate_pct_per_hour
        if rate is None or rate <= 0:
            return None
        return self.battery_level / rate

    def _query(self, command: str) -> str | None:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(self._socket_path)
            sock.sendall((command + "\n").encode())
            data = sock.recv(256).decode().strip()
            sock.close()
            return data
        except Exception:
            return None

    def _update(self) -> None:
        # Battery level
        resp = self._query("get battery")
        if resp and ":" in resp:
            try:
                self.battery_level = int(float(resp.split(":")[1].strip()))
                self._available = True
            except (ValueError, IndexError):
                pass

        # Charging status
        resp = self._query("get battery_charging")
        if resp and ":" in resp:
            val = resp.split(":")[1].strip().lower()
            self.is_charging = val == "true"

        self.is_low = self.battery_level < self._warning_pct

        # Record history for drain estimation
        if self._available:
            self._history.append((time.monotonic(), self.battery_level))

    def _monitor_loop(self) -> None:
        while self._running:
            self._update()

            if self._available and self.battery_level <= self._shutdown_pct and not self.is_charging:
                logger.critical(
                    "Battery critically low (%d%%) — initiating shutdown",
                    self.battery_level,
                )
                if self._shutdown_callback:
                    self._shutdown_callback()
                os.system("sudo systemctl poweroff")
                return

            time.sleep(self._check_interval)
