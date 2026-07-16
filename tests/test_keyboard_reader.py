"""Tests for KeyboardReader evdev reconnect + auto-resolve (no live hardware)."""

from __future__ import annotations

import logging
import sys

from writerdeck.input.keyboard import KeyboardReader


class _FakeEvdev:
    """Minimal stand-in for the evdev module used by _reconnect."""

    def __init__(self, raises: bool = False) -> None:
        self._raises = raises
        self.opened: list[str] = []

    def InputDevice(self, path):  # noqa: N802 — mirror evdev's API
        self.opened.append(path)
        if self._raises:
            raise OSError("device still gone")
        return f"dev:{path}"


class TestReconnect:
    def test_reconnect_resets_mapper(self):
        reader = KeyboardReader(device_path="/dev/input/event0")
        # Simulate a modifier held at the moment of disconnect.
        reader._mapper.process_event(29, 1)  # Ctrl press
        assert reader._mapper._ctrl_held is True

        fake = _FakeEvdev()
        new_dev = reader._reconnect(fake, "old-dev")

        assert reader._mapper._ctrl_held is False
        assert new_dev == "dev:/dev/input/event0"

    def test_reconnect_reset_even_when_reopen_fails(self):
        reader = KeyboardReader(device_path="/dev/input/event0")
        reader._mapper.process_event(42, 1)  # Shift press
        assert reader._mapper._shift_held is True

        fake = _FakeEvdev(raises=True)
        new_dev = reader._reconnect(fake, "old-dev")

        # Mapper is still reset, and the old handle is returned on failure.
        assert reader._mapper._shift_held is False
        assert new_dev == "old-dev"

    def test_reconnect_reresolves_new_node(self, monkeypatch):
        """A replug onto a different eventN must be picked up (HIGH bug)."""
        reader = KeyboardReader(device_path="auto")
        # _resolve_device_retrying now reports the new node the keyboard
        # re-enumerated onto after the replug.
        monkeypatch.setattr(
            reader, "_resolve_device_retrying", lambda: "/dev/input/event7"
        )

        fake = _FakeEvdev()
        new_dev = reader._reconnect(fake, "old-dev")

        assert fake.opened == ["/dev/input/event7"]
        assert new_dev == "dev:/dev/input/event7"

    def test_reconnect_returns_old_dev_when_reresolve_fails(self, monkeypatch):
        reader = KeyboardReader(device_path="auto")
        monkeypatch.setattr(reader, "_resolve_device_retrying", lambda: None)

        fake = _FakeEvdev()
        new_dev = reader._reconnect(fake, "old-dev")

        # Nothing re-resolved → keep the old handle, don't try to open None.
        assert fake.opened == []
        assert new_dev == "old-dev"


class TestResolveRetrying:
    def test_explicit_path_returned_directly(self):
        reader = KeyboardReader(device_path="/dev/input/event3")
        assert reader._resolve_device_retrying() == "/dev/input/event3"

    def test_retries_then_succeeds(self, monkeypatch):
        """by-id symlink appears on a later attempt (slow USB enumeration)."""
        reader = KeyboardReader(device_path="auto")
        reader._running = True
        results = iter([None, None, "/dev/input/event2"])
        monkeypatch.setattr(reader, "_resolve_device", lambda: next(results))
        # Don't actually sleep in the test.
        monkeypatch.setattr(
            "writerdeck.input.keyboard.time.sleep", lambda _s: None
        )
        fallback_called = []
        monkeypatch.setattr(
            reader,
            "_resolve_device_fallback",
            lambda: fallback_called.append(True),
        )

        assert reader._resolve_device_retrying() == "/dev/input/event2"
        # Should not have needed the guessed fallback.
        assert fallback_called == []

    def test_loud_warning_on_fallback(self, monkeypatch, caplog):
        """When by-id never resolves, warn LOUDLY before guessing (MEDIUM bug)."""
        reader = KeyboardReader(device_path="auto")
        reader._running = True
        monkeypatch.setattr(reader, "_resolve_device", lambda: None)
        monkeypatch.setattr(
            reader, "_resolve_device_fallback", lambda: "/dev/input/event0"
        )
        monkeypatch.setattr(
            "writerdeck.input.keyboard.time.sleep", lambda _s: None
        )

        with caplog.at_level(logging.WARNING, logger="writerdeck.input.keyboard"):
            resolved = reader._resolve_device_retrying()

        assert resolved == "/dev/input/event0"
        assert any(
            record.levelno == logging.WARNING
            and "/dev/input/event0" in record.getMessage()
            for record in caplog.records
        ), "expected a loud warning naming the guessed device"

    def test_stops_retrying_when_not_running(self, monkeypatch):
        reader = KeyboardReader(device_path="auto")
        reader._running = False  # stop() called during startup window
        monkeypatch.setattr(reader, "_resolve_device", lambda: None)
        sleeps = []
        monkeypatch.setattr(
            "writerdeck.input.keyboard.time.sleep", lambda s: sleeps.append(s)
        )

        assert reader._resolve_device_retrying() is None
        # No sleeping / spinning once we've been told to stop.
        assert sleeps == []


class TestStop:
    def test_stop_joins_thread(self):
        reader = KeyboardReader(device_path="/dev/input/event0")

        class _FakeThread:
            def __init__(self) -> None:
                self.joined_with = None

            def is_alive(self) -> bool:
                return True

            def join(self, timeout=None):
                self.joined_with = timeout

        fake = _FakeThread()
        reader._thread = fake  # type: ignore[assignment]
        reader._running = True

        reader.stop()

        assert reader._running is False
        assert fake.joined_with == 2.0

    def test_stop_without_thread_is_safe(self):
        reader = KeyboardReader(device_path="/dev/input/event0")
        # Never started — no thread to join.
        reader.stop()
        assert reader._running is False


class _FakeEventPath:
    """Minimal stand-in for Path("/dev/input/eventN") — glob() results."""

    def __init__(self, name: str) -> None:
        self._str = f"/dev/input/{name}"

    def __str__(self) -> str:
        return self._str

    def __lt__(self, other: _FakeEventPath) -> bool:
        return str(self) < str(other)


class _FakeInputDir:
    def __init__(self, entries: list[_FakeEventPath]) -> None:
        self._entries = entries

    def glob(self, pattern: str):
        return iter(self._entries)


class _FakeCapsInputDevice:
    def __init__(self, caps: dict) -> None:
        self._caps = caps

    def capabilities(self):
        return self._caps


class _FakeEcodes:
    EV_KEY = 1
    KEY_A = 30


class _FakeEvdevModule:
    """Stand-in for the evdev module, keyed by device path string."""

    ecodes = _FakeEcodes()

    def __init__(self, caps_by_path: dict[str, dict]) -> None:
        self._caps_by_path = caps_by_path

    def InputDevice(self, path: str):  # noqa: N802 — mirror evdev's API
        return _FakeCapsInputDevice(self._caps_by_path.get(path, {}))


class TestMaybeUpgradeFromGuess:
    """HIGH (found via real hardware): a guessed fallback device can be a
    stable node (e.g. HDMI-CEC) that never itself disconnects, so the
    OSError-driven reconnect path never re-fires once mis-guessed — input
    stays dead until a service restart unless something else keeps checking
    for the real keyboard.
    """

    def test_upgrades_when_real_device_resolves(self, monkeypatch):
        reader = KeyboardReader(device_path="auto")
        reader._is_guessed_device = True
        reader._mapper.process_event(29, 1)  # Ctrl held during the guess
        monkeypatch.setattr(reader, "_resolve_device", lambda: "/dev/input/event0")

        fake = _FakeEvdev()
        old_dev = "guessed-dev"
        new_dev = reader._maybe_upgrade_from_guess(fake, old_dev)

        assert new_dev == "dev:/dev/input/event0"
        assert reader._is_guessed_device is False
        assert reader._mapper._ctrl_held is False

    def test_no_upgrade_when_real_device_not_yet_resolved(self, monkeypatch):
        reader = KeyboardReader(device_path="auto")
        reader._is_guessed_device = True
        monkeypatch.setattr(reader, "_resolve_device", lambda: None)

        fake = _FakeEvdev()
        result = reader._maybe_upgrade_from_guess(fake, "guessed-dev")

        assert result == "guessed-dev"
        assert fake.opened == []
        assert reader._is_guessed_device is True

    def test_no_upgrade_when_open_fails(self, monkeypatch):
        reader = KeyboardReader(device_path="auto")
        reader._is_guessed_device = True
        monkeypatch.setattr(reader, "_resolve_device", lambda: "/dev/input/event0")

        fake = _FakeEvdev(raises=True)
        result = reader._maybe_upgrade_from_guess(fake, "guessed-dev")

        assert result == "guessed-dev"
        assert reader._is_guessed_device is True


class TestResolveFallback:
    """MEDIUM (found via real hardware): a replug can transiently leave only
    an unrelated, always-present node (e.g. HDMI-CEC) in /dev/input — the
    fallback guess must prefer a node with real keyboard capability over
    blindly taking the alphabetically-first event node.
    """

    def _patch_input_dir(self, monkeypatch, names: list[str]) -> list[_FakeEventPath]:
        entries = [_FakeEventPath(n) for n in names]
        fake_dir = _FakeInputDir(entries)
        monkeypatch.setattr(
            "writerdeck.input.keyboard.Path",
            lambda p: fake_dir if p == "/dev/input" else __import__("pathlib").Path(p),
        )
        return entries

    def test_prefers_keyboard_capable_node_over_first(self, monkeypatch):
        # event2 (HDMI-CEC-like: no KEY_A) sorts before event5 (real keyboard).
        self._patch_input_dir(monkeypatch, ["event2", "event5"])
        fake_evdev = _FakeEvdevModule(
            {
                "/dev/input/event2": {_FakeEcodes.EV_KEY: [1, 2, 3]},  # no KEY_A
                "/dev/input/event5": {_FakeEcodes.EV_KEY: [_FakeEcodes.KEY_A, 31]},
            }
        )
        monkeypatch.setitem(sys.modules, "evdev", fake_evdev)

        reader = KeyboardReader(device_path="auto")
        assert reader._resolve_device_fallback() == "/dev/input/event5"

    def test_falls_back_to_first_node_when_none_look_like_a_keyboard(
        self, monkeypatch
    ):
        self._patch_input_dir(monkeypatch, ["event2", "event5"])
        fake_evdev = _FakeEvdevModule(
            {
                "/dev/input/event2": {_FakeEcodes.EV_KEY: [1, 2]},
                "/dev/input/event5": {_FakeEcodes.EV_KEY: [3, 4]},
            }
        )
        monkeypatch.setitem(sys.modules, "evdev", fake_evdev)

        reader = KeyboardReader(device_path="auto")
        # No node has KEY_A — degrade to the old first-node guess rather than
        # finding nothing at all.
        assert reader._resolve_device_fallback() == "/dev/input/event2"

    def test_falls_back_to_first_node_when_evdev_unavailable(self, monkeypatch):
        self._patch_input_dir(monkeypatch, ["event2", "event5"])
        monkeypatch.setitem(sys.modules, "evdev", None)  # forces ImportError

        reader = KeyboardReader(device_path="auto")
        assert reader._resolve_device_fallback() == "/dev/input/event2"

    def test_returns_none_when_no_nodes_exist(self, monkeypatch):
        self._patch_input_dir(monkeypatch, [])
        reader = KeyboardReader(device_path="auto")
        assert reader._resolve_device_fallback() is None
