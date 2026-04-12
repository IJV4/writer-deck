"""Keyboard input — daemon thread reading evdev events into a queue."""

from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path
from typing import Callable

from writerdeck.input.keymapper import KeyAction, KeyMapper

logger = logging.getLogger(__name__)


class KeyboardReader:
    def __init__(
        self,
        device_path: str = "auto",
        action_queue: queue.SimpleQueue | None = None,
        on_any_key: Callable[[], None] | None = None,
    ) -> None:
        self._device_path = device_path
        self.queue: queue.SimpleQueue[tuple[KeyAction, str]] = (
            action_queue or queue.SimpleQueue()
        )
        self._on_any_key = on_any_key
        self._mapper = KeyMapper()
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _resolve_device(self) -> str | None:
        if self._device_path != "auto":
            return self._device_path
        # Try to find a keyboard device via stable by-id symlinks.
        # Sort for determinism; skip mouse/joystick entries.
        by_id = Path("/dev/input/by-id")
        if by_id.exists():
            candidates = sorted(by_id.iterdir())
            # First pass: prefer explicit event-kbd entries (most specific)
            for p in candidates:
                name = p.name.lower()
                if "mouse" in name or "joystick" in name:
                    continue
                if "event-kbd" in name or name.endswith("-kbd"):
                    return str(p.resolve())
            # Second pass: any keyboard-named entry that isn't a mouse device
            for p in candidates:
                name = p.name.lower()
                if "mouse" in name or "joystick" in name:
                    continue
                if "keyboard" in name or "kbd" in name:
                    return str(p.resolve())
        # Fallback: first event* device
        for p in sorted(Path("/dev/input").glob("event*")):
            return str(p)
        return None

    def _read_loop(self) -> None:
        try:
            import evdev  # type: ignore[import-untyped]
        except ImportError:
            logger.error("evdev not installed — keyboard input unavailable")
            return

        device_path = self._resolve_device()
        if not device_path:
            logger.error("No keyboard device found")
            return

        try:
            dev = evdev.InputDevice(device_path)
        except OSError as exc:
            logger.error("Cannot open %s: %s", device_path, exc)
            return

        logger.info("Reading keyboard from %s (%s)", device_path, dev.name)

        while self._running:
            try:
                for event in dev.read_loop():
                    if not self._running:
                        break
                    # EV_KEY = 1
                    if event.type != 1:
                        continue
                    action, char = self._mapper.process_event(event.code, event.value)
                    if action != KeyAction.UNKNOWN:
                        self.queue.put((action, char))
                    # Notify wake callback on any key press/repeat
                    if event.value != 0 and self._on_any_key:
                        self._on_any_key()
            except OSError:
                logger.warning("Keyboard device disconnected, retrying in 2s…")
                time.sleep(2)
                try:
                    dev = evdev.InputDevice(device_path)
                except Exception:
                    pass
