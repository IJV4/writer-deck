"""Battery / power management via PiSugar daemon."""

from __future__ import annotations

import logging
import socket
import subprocess
import threading
import time
from collections import deque

logger = logging.getLogger(__name__)

# Number of consecutive sub-threshold battery samples required before we shut
# down. Guards against a single glitchy PiSugar reading triggering poweroff and
# losing the session (readings are noisy under load).
SHUTDOWN_DEBOUNCE_SAMPLES = 3


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

        # Consecutive sub-threshold (critical, not charging) samples seen. Reset
        # to 0 on any healthy or charging reading; shutdown only fires once this
        # reaches SHUTDOWN_DEBOUNCE_SAMPLES.
        self._low_battery_streak = 0

        # Battery history for drain rate estimation
        self._history: deque[tuple[float, int]] = deque(maxlen=60)

    def start(self, shutdown_callback: callable | None = None) -> None:
        if not self._enabled:
            return
        self._shutdown_callback = shutdown_callback
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def check_now(self) -> None:
        """Synchronously refresh battery/charging state once.

        Used for a fresh reading before the async monitor thread has started
        (e.g. the startup low-battery gate) — waiting for the thread's first
        poll would race against callers that need a trustworthy value right
        away. Reuses the same query logic the monitor loop runs on its
        interval, so a caller sees identical fields (battery_level,
        is_charging, is_low, available).
        """
        self._update()

    def stop(self) -> None:
        self._running = False
        # Join the monitor thread for graceful shutdown. Use a short timeout so a
        # thread blocked in a socket op / long check_interval sleep can't hang
        # shutdown — the thread is a daemon, so a timed-out join is still safe.
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)

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
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(2)
                sock.connect(self._socket_path)
                sock.sendall((command + "\n").encode())
                return sock.recv(256).decode().strip()
        except Exception:
            return None

    def _update(self) -> None:
        # Battery level. A failed query (dead socket / no daemon) must mark the
        # data stale so a frozen critical+not-charging reading can't count toward
        # the shutdown debounce — otherwise a dead socket could trigger poweroff
        # entirely from last-known values. We only consider this cycle a success
        # once we've parsed a fresh battery level.
        fresh = False
        resp = self._query("get battery")
        if resp and ":" in resp:
            try:
                self.battery_level = int(float(resp.split(":")[1].strip()))
                fresh = True
            except (ValueError, IndexError):
                pass

        # Availability reflects whether *this* cycle got a fresh reading. A
        # recovered socket restores availability; a failed one clears it.
        self._available = fresh

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

            critical = (
                self._available
                and self.battery_level <= self._shutdown_pct
                and not self.is_charging
            )
            if critical:
                self._low_battery_streak += 1
            else:
                # Any healthy or charging reading clears the debounce so a single
                # glitchy sample never counts toward shutdown.
                self._low_battery_streak = 0

            if self._low_battery_streak >= SHUTDOWN_DEBOUNCE_SAMPLES:
                logger.critical(
                    "Battery critically low (%d%%) for %d consecutive samples — "
                    "initiating shutdown",
                    self.battery_level,
                    self._low_battery_streak,
                )
                # FAULT-5: the emergency callback (app._emergency_shutdown →
                # emergency_save → driver.sleep()) MUST run to completion — deep-
                # sleeping the panel while the battery still holds — BEFORE we
                # cut power. This call is synchronous, so poweroff is only issued
                # once it returns. Do not rely on poweroff's own service-stop to
                # win the race against high-voltage panel damage.
                if self._shutdown_callback:
                    try:
                        # NOTE: this runs on the monitor thread (not the main
                        # app/render thread). The callback deep-sleeps the panel
                        # via the display driver, so it touches the SPI bus
                        # concurrently with any in-flight render; thread-safety
                        # relies on the driver's internal SPI lock serialising
                        # those hardware ops.
                        self._shutdown_callback()
                        logger.info(
                            "Emergency callback complete (panel slept) — issuing poweroff"
                        )
                    except Exception:
                        # A failure to sleep the panel must NOT prevent poweroff:
                        # protecting the battery is the higher priority, and the
                        # systemd service-stop is a secondary chance to sleep it.
                        logger.exception(
                            "Emergency callback raised — powering off anyway"
                        )
                else:
                    logger.info("No emergency callback — issuing poweroff")
                try:
                    result = subprocess.run(
                        ["sudo", "systemctl", "poweroff"],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode != 0:
                        logger.error(
                            "poweroff exited %d: %s",
                            result.returncode,
                            result.stderr.strip(),
                        )
                except Exception:
                    logger.exception("Failed to issue poweroff")
                return

            time.sleep(self._check_interval)
