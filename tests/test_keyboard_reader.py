"""Tests for KeyboardReader evdev reconnect (no live hardware)."""

from __future__ import annotations

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
        reader = KeyboardReader()
        # Simulate a modifier held at the moment of disconnect.
        reader._mapper.process_event(29, 1)  # Ctrl press
        assert reader._mapper._ctrl_held is True

        fake = _FakeEvdev()
        new_dev = reader._reconnect(fake, "/dev/input/event0", "old-dev")

        assert reader._mapper._ctrl_held is False
        assert new_dev == "dev:/dev/input/event0"

    def test_reconnect_reset_even_when_reopen_fails(self):
        reader = KeyboardReader()
        reader._mapper.process_event(42, 1)  # Shift press
        assert reader._mapper._shift_held is True

        fake = _FakeEvdev(raises=True)
        new_dev = reader._reconnect(fake, "/dev/input/event0", "old-dev")

        # Mapper is still reset, and the old handle is returned on failure.
        assert reader._mapper._shift_held is False
        assert new_dev == "old-dev"
