"""Keyboard input — daemon thread reading evdev events into a queue."""

from __future__ import annotations

import logging
import queue
import select
import threading
import time
from collections.abc import Callable
from pathlib import Path

from writerdeck.input.keymapper import KeyAction, KeyMapper

logger = logging.getLogger(__name__)

# When device_path == "auto" and the stable by-id keyboard symlink isn't
# present yet (USB still enumerating at boot), retry the resolve a few times
# with a short sleep before falling back to a guessed event* node.
#
# Measured on real hardware (Pi Zero 2W, USB keyboard unplug/replug): udev
# doesn't recreate the by-id symlink until ~13s after the replug — the kernel
# removes and recreates ALL of the keyboard's /dev/input/eventN nodes during
# re-enumeration, so a short retry budget can expire while none of them exist
# yet, at which point the fallback guess has nothing real to find and can
# latch onto an unrelated, always-present node (e.g. the HDMI-CEC remote
# input) instead. 20 attempts * 1s gives a comfortable margin over that.
_AUTO_RESOLVE_ATTEMPTS = 20
_AUTO_RESOLVE_SLEEP = 1.0

# While running on a guessed fallback device (see _resolve_device_fallback),
# poll for a real keyboard resolving at this interval instead of blocking
# indefinitely on the guessed device's events. A guessed device is often a
# stable, always-present node (e.g. the Pi's HDMI-CEC input) that never
# itself disconnects — without this, once mis-guessed, the reader would
# never notice the real keyboard's by-id symlink appearing later and input
# would stay dead until a service restart.
_GUESS_UPGRADE_CHECK_INTERVAL = 3.0


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
        # True when the currently-open device came from _resolve_device_fallback
        # rather than a confident by-id match — lets _read_loop know to keep
        # checking for the real keyboard instead of trusting the guess forever.
        self._is_guessed_device = False

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        # Join so the reader thread is quiescent before driver teardown. It is a
        # daemon thread and may be blocked in a long evdev read, so bound the
        # wait — a timeout is acceptable (the interpreter won't hang on exit).
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def _resolve_device(self) -> str | None:
        """Resolve the configured device to a concrete node.

        Returns a confident by-id keyboard match when possible. Returns ``None``
        when ``device_path == "auto"`` and no keyboard symlink is found yet, so
        the caller can retry while USB is still enumerating; use
        :meth:`_resolve_device_fallback` for the last-resort guess.
        """
        if self._device_path != "auto":
            return self._device_path
        # Try to find a keyboard device via stable by-id symlinks.
        # Sort for determinism; skip mouse/joystick entries.
        by_id = Path("/dev/input/by-id")
        if by_id.exists():
            # Filter out non-keyboard devices once; iterate the result twice.
            candidates = [
                p for p in sorted(by_id.iterdir())
                if "mouse" not in p.name.lower() and "joystick" not in p.name.lower()
            ]
            # First pass: prefer explicit event-kbd entries (most specific)
            for p in candidates:
                name = p.name.lower()
                if "event-kbd" in name or name.endswith("-kbd"):
                    return str(p.resolve())
            # Second pass: any keyboard-named entry
            for p in candidates:
                name = p.name.lower()
                if "keyboard" in name or "kbd" in name:
                    return str(p.resolve())
        return None

    def _resolve_device_fallback(self) -> str | None:
        """Last-resort guess when no by-id keyboard symlink was found in time.

        Prefers a node that actually reports full alphanumeric keyboard
        capability (has KEY_A in its EV_KEY set) over blindly taking the
        alphabetically-first ``event*`` node — a real USB keyboard replug
        removes and recreates ALL of its own event nodes, so mid-reconnect the
        only node that happens to exist can be an unrelated, always-present
        device (e.g. the Pi's HDMI-CEC remote input, which only exposes a
        handful of IR remote keys, not a full keyboard). Falls back to the
        old first-node behavior if capability inspection isn't available
        (e.g. evdev missing) or nothing has full keyboard capability, so
        `auto` still degrades to *something* rather than nothing.

        Only meaningful for ``auto``; for an explicit path there is nothing to
        guess. Callers log loudly before using this, since it may still not
        be a keyboard.
        """
        candidates = sorted(Path("/dev/input").glob("event*"))
        if not candidates:
            return None

        try:
            import evdev  # type: ignore[import-untyped]

            for p in candidates:
                try:
                    caps = evdev.InputDevice(str(p)).capabilities().get(
                        evdev.ecodes.EV_KEY, []
                    )
                except OSError:
                    continue
                if evdev.ecodes.KEY_A in caps:
                    return str(p)
        except ImportError:
            pass

        return str(candidates[0])

    def _resolve_device_retrying(self) -> str | None:
        """Resolve the device, tolerating slow USB enumeration.

        For ``auto``, retry the by-id resolve a few times with a short sleep
        before falling back to a guessed ``event*`` node, logging a LOUD warning
        when it does fall back so a mis-guess is diagnosable. Sets
        ``self._is_guessed_device`` so ``_read_loop`` knows whether to keep
        checking for a better match once this device is open.
        """
        resolved = self._resolve_device()
        if resolved is not None or self._device_path != "auto":
            self._is_guessed_device = False
            return resolved

        # by-id keyboard symlink not present yet — USB may still be enumerating.
        for _ in range(_AUTO_RESOLVE_ATTEMPTS - 1):
            if not self._running:
                return None
            time.sleep(_AUTO_RESOLVE_SLEEP)
            resolved = self._resolve_device()
            if resolved is not None:
                self._is_guessed_device = False
                return resolved

        fallback = self._resolve_device_fallback()
        if fallback is not None:
            logger.warning(
                "No by-id keyboard symlink found after %d attempts; falling back "
                "to guessed device %s — this may NOT be a keyboard. Set "
                "keyboard_input device explicitly if input misbehaves.",
                _AUTO_RESOLVE_ATTEMPTS,
                fallback,
            )
        self._is_guessed_device = fallback is not None
        return fallback

    def _read_loop(self) -> None:
        try:
            import evdev  # type: ignore[import-untyped]
        except ImportError:
            logger.error("evdev not installed — keyboard input unavailable")
            return

        device_path = self._resolve_device_retrying()
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
                # A guessed fallback device is often a stable, always-present
                # node that never itself raises OSError (e.g. HDMI-CEC), so
                # blocking indefinitely on it would mean never noticing the
                # real keyboard resolving later. Poll with a short timeout
                # instead of the blocking dev.read_loop() so we get a
                # periodic checkpoint to attempt an upgrade.
                r, _, _ = select.select(
                    [dev.fd], [], [], _GUESS_UPGRADE_CHECK_INTERVAL
                )
                if not r:
                    if self._is_guessed_device:
                        dev = self._maybe_upgrade_from_guess(evdev, dev)
                    continue
                for event in dev.read():
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
                dev = self._reconnect(evdev, dev)

    def _maybe_upgrade_from_guess(self, evdev, dev):  # type: ignore[no-untyped-def]
        """While running on a guessed fallback device, check for the real
        by-id keyboard and switch over if it now resolves.

        Uses the strict, non-retrying resolve (no sleeping — this runs on
        every idle poll timeout) so it's cheap to call repeatedly. Returns the
        (possibly unchanged) device handle.
        """
        resolved = self._resolve_device()
        if resolved is None:
            return dev
        try:
            new_dev = evdev.InputDevice(resolved)
        except OSError:
            return dev
        logger.info("Upgraded from guessed device to confirmed keyboard %s", resolved)
        self._is_guessed_device = False
        self._mapper.reset()
        return new_dev

    def _reconnect(self, evdev, dev):  # type: ignore[no-untyped-def]
        """Reopen the device after a disconnect.

        Resets the KeyMapper so a modifier held during the unplug does not stay
        latched, then re-resolves the device node before reopening. Re-resolving
        matters because a keyboard that replugs may re-enumerate onto a
        different ``/dev/input/eventN`` — reopening the stale concrete path would
        leave input dead until a service restart. Returns the (possibly
        unchanged) device handle so the read loop can continue.
        """
        self._mapper.reset()
        device_path = self._resolve_device_retrying()
        if not device_path:
            return dev
        try:
            new_dev = evdev.InputDevice(device_path)
        except Exception:
            return dev
        logger.info("Reconnected keyboard on %s", device_path)
        return new_dev
