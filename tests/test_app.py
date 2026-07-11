"""Tests for App lifecycle with mock subsystems."""

from __future__ import annotations

import os
import queue
import time
from unittest.mock import MagicMock, patch

import pytest

from writerdeck.core.config import Config, _deep_merge


def _make_config(overrides: dict | None = None) -> Config:
    base = {
        "display_model": "epd7in5_V2",
        "font_family": "Hack",
        "font_size": 14,
        "daily_goal_words": 500,
        "partial_refresh_max_streak": 20,
        "render_interval_ms": 100,
        "idle_full_refresh_seconds": 10,
        "display_sleep_minutes": 0,
        "keyboard_device": "auto",
        "keyboard_input": "stdin",
        "mode_order": ["distraction_free", "dashboard", "typewriter"],
        "documents_dir": "/tmp/writer-deck-test-docs",
        "autosave_interval_seconds": 9999,
        "battery_warning_percent": 15,
        "battery_shutdown_percent": 3,
        "enable_battery_monitor": False,
        "pisugar_socket": "/tmp/pisugar-test.sock",
        "log_dir": "/tmp/writer-deck-test-logs",
        "show_title_bar": True,
        "default_format": "txt",
        "sleep_tiers": {
            "display_off_minutes": 0,
            "cpu_powersave_minutes": 0,
            "system_suspend_minutes": 0,
        },
    }
    if overrides:
        base = _deep_merge(base, overrides)
    return Config(base)


class TestAppInit:
    """Test that App can be constructed with mocked subsystems."""

    @patch("writerdeck.core.app.get_config")
    @patch("writerdeck.core.app.detect_platform")
    @patch("writerdeck.core.app.create_driver")
    def test_app_creates(self, mock_driver, mock_platform, mock_config):
        from writerdeck.utils.platform import HardwareProfile

        mock_config.return_value = _make_config()
        mock_platform.return_value = HardwareProfile(
            name="desktop", is_pi=False, is_pi_zero=False,
            partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
        )
        mock_driver.return_value = MagicMock()

        from writerdeck.core.app import App
        app = App()
        assert app._doc is not None
        assert len(app._modes) == 3

    @patch("writerdeck.core.app.get_config")
    @patch("writerdeck.core.app.detect_platform")
    @patch("writerdeck.core.app.create_driver")
    def test_emergency_save_never_raises(self, mock_driver, mock_platform, mock_config):
        from writerdeck.utils.platform import HardwareProfile

        mock_config.return_value = _make_config()
        mock_platform.return_value = HardwareProfile(
            name="desktop", is_pi=False, is_pi_zero=False,
            partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
        )
        driver = MagicMock()
        driver.sleep.side_effect = RuntimeError("driver broken")
        mock_driver.return_value = driver

        from writerdeck.core.app import App
        app = App()
        # Should not raise even if driver.sleep() raises
        app.emergency_save()


class TestHandleAction:
    @patch("writerdeck.core.app.get_config")
    @patch("writerdeck.core.app.detect_platform")
    @patch("writerdeck.core.app.create_driver")
    def test_save_sets_status(self, mock_driver, mock_platform, mock_config, tmp_path):
        from writerdeck.utils.platform import HardwareProfile
        from writerdeck.input.keymapper import KeyAction

        mock_config.return_value = _make_config(
            {"documents_dir": str(tmp_path)}
        )
        mock_platform.return_value = HardwareProfile(
            name="desktop", is_pi=False, is_pi_zero=False,
            partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
        )
        mock_driver.return_value = MagicMock()

        from writerdeck.core.app import App
        app = App()
        # Pre-create the file on disk so SAVE doesn't prompt for a name
        (tmp_path / "test-doc.txt").write_text("test content")
        app._doc.load("test content", "test-doc")
        app._doc.dirty = True
        app._handle_action(KeyAction.SAVE, "")
        assert app._status.current == "Saved"

    @patch("writerdeck.core.app.get_config")
    @patch("writerdeck.core.app.detect_platform")
    @patch("writerdeck.core.app.create_driver")
    def test_mode_switch(self, mock_driver, mock_platform, mock_config, tmp_path):
        from writerdeck.utils.platform import HardwareProfile
        from writerdeck.input.keymapper import KeyAction

        mock_config.return_value = _make_config(
            {"documents_dir": str(tmp_path)}
        )
        mock_platform.return_value = HardwareProfile(
            name="desktop", is_pi=False, is_pi_zero=False,
            partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
        )
        mock_driver.return_value = MagicMock()

        from writerdeck.core.app import App
        app = App()
        assert app._mode.name == "distraction_free"
        app._handle_action(KeyAction.SWITCH_MODE_NEXT, "")
        assert app._mode.name == "dashboard"

    @patch("writerdeck.core.app.get_config")
    @patch("writerdeck.core.app.detect_platform")
    @patch("writerdeck.core.app.create_driver")
    def test_mode_switch_prev(self, mock_driver, mock_platform, mock_config, tmp_path):
        from writerdeck.utils.platform import HardwareProfile
        from writerdeck.input.keymapper import KeyAction

        mock_config.return_value = _make_config(
            {"documents_dir": str(tmp_path)}
        )
        mock_platform.return_value = HardwareProfile(
            name="desktop", is_pi=False, is_pi_zero=False,
            partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
        )
        mock_driver.return_value = MagicMock()

        from writerdeck.core.app import App
        app = App()
        assert app._mode.name == "distraction_free"
        app._handle_action(KeyAction.SWITCH_MODE_PREV, "")
        assert app._mode.name == "typewriter"

    @patch("writerdeck.core.app.get_config")
    @patch("writerdeck.core.app.detect_platform")
    @patch("writerdeck.core.app.create_driver")
    def test_new_doc_resets(self, mock_driver, mock_platform, mock_config, tmp_path):
        from writerdeck.utils.platform import HardwareProfile
        from writerdeck.input.keymapper import KeyAction

        mock_config.return_value = _make_config(
            {"documents_dir": str(tmp_path)}
        )
        mock_platform.return_value = HardwareProfile(
            name="desktop", is_pi=False, is_pi_zero=False,
            partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
        )
        mock_driver.return_value = MagicMock()

        from writerdeck.core.app import App
        app = App()
        app._doc.load("old content", "old-doc")
        app._doc.insert("x")
        app._handle_action(KeyAction.NEW_DOC, "")
        import re
        assert app._doc.text == ""
        assert re.match(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}", app._doc.name)

    @patch("writerdeck.core.app.get_config")
    @patch("writerdeck.core.app.detect_platform")
    @patch("writerdeck.core.app.create_driver")
    def test_escape_returns_false(self, mock_driver, mock_platform, mock_config, tmp_path):
        from writerdeck.utils.platform import HardwareProfile
        from writerdeck.input.keymapper import KeyAction

        mock_config.return_value = _make_config(
            {"documents_dir": str(tmp_path)}
        )
        mock_platform.return_value = HardwareProfile(
            name="desktop", is_pi=False, is_pi_zero=False,
            partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
        )
        mock_driver.return_value = MagicMock()

        from writerdeck.core.app import App
        app = App()
        result = app._handle_action(KeyAction.ESCAPE, "")
        assert result is False


class TestOverlayDispatch:
    def _make_app(self, tmp_path):
        """Helper to construct an App with full mocking."""
        from writerdeck.utils.platform import HardwareProfile
        from writerdeck.core.app import App

        with patch("writerdeck.core.app.get_config") as mc, \
             patch("writerdeck.core.app.detect_platform") as mp, \
             patch("writerdeck.core.app.create_driver") as md:
            mc.return_value = _make_config({"documents_dir": str(tmp_path)})
            mp.return_value = HardwareProfile(
                name="desktop", is_pi=False, is_pi_zero=False,
                partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
            )
            md.return_value = MagicMock()
            return App()

    def test_open_doc_overlay_activates(self, tmp_path):
        from writerdeck.input.keymapper import KeyAction

        app = self._make_app(tmp_path)
        app._handle_action(KeyAction.OPEN_DOC, "")
        assert app._overlay is not None

    def test_find_overlay_activates(self, tmp_path):
        from writerdeck.input.keymapper import KeyAction

        app = self._make_app(tmp_path)
        app._handle_action(KeyAction.FIND, "")
        assert app._overlay is not None

    def test_font_menu_overlay_activates(self, tmp_path):
        from writerdeck.input.keymapper import KeyAction

        app = self._make_app(tmp_path)
        app._handle_action(KeyAction.FONT_MENU, "")
        assert app._overlay is not None

    def test_overlay_routes_input(self, tmp_path):
        from writerdeck.input.keymapper import KeyAction

        app = self._make_app(tmp_path)
        # Activate find overlay
        app._handle_action(KeyAction.FIND, "")
        assert app._overlay is not None
        # Type a character — should go to overlay, not document
        original_text = app._doc.text
        app._handle_action(KeyAction.CHAR, "x")
        assert app._doc.text == original_text  # doc unchanged

    def test_overlay_escape_closes(self, tmp_path):
        from writerdeck.input.keymapper import KeyAction

        app = self._make_app(tmp_path)
        app._handle_action(KeyAction.FIND, "")
        assert app._overlay is not None
        # Escape closes overlay
        app._handle_action(KeyAction.ESCAPE, "")
        assert app._overlay is None

    def test_handle_overlay_result_open_doc(self, tmp_path):
        from writerdeck.input.keymapper import KeyAction

        app = self._make_app(tmp_path)
        # Create a doc file first
        doc_path = tmp_path / "my-doc.txt"
        doc_path.write_text("Hello from file")
        app._handle_overlay_result({"open_doc": "my-doc"})
        assert app._doc.name == "my-doc"

    def test_handle_overlay_result_font(self, tmp_path):
        app = self._make_app(tmp_path)
        original_font = app._config.font_family
        app._handle_overlay_result({"font": "Courier"})
        assert app._config._data["font_family"] == "Courier"

    def test_handle_overlay_result_find(self, tmp_path):
        app = self._make_app(tmp_path)
        app._doc.load("hello world hello", "test")
        app._doc.cursor_line = 0
        app._doc.cursor_col = 0
        app._handle_overlay_result({"find": "world"})
        assert app._doc.cursor_col == 6
        assert app._status.current == "Found at line 1"

    def test_handle_overlay_result_find_not_found(self, tmp_path):
        app = self._make_app(tmp_path)
        app._doc.load("hello", "test")
        app._handle_overlay_result({"find": "xyz"})
        assert app._status.current == "Not found"

    def test_handle_overlay_result_replace(self, tmp_path):
        app = self._make_app(tmp_path)
        app._doc.load("hello world", "test")
        app._doc.cursor_line = 0
        app._doc.cursor_col = 6
        app._handle_overlay_result({"find": "world", "replace": "earth"})
        assert app._doc.text == "hello earth"
        assert app._status.current == "Replaced"

    def test_handle_overlay_result_replace_locates_match(self, tmp_path):
        # BUG-1: cursor at (0,0) should still find and replace a later match.
        app = self._make_app(tmp_path)
        app._doc.load("the cat sat", "test")
        app._doc.cursor_line = 0
        app._doc.cursor_col = 0
        app._handle_overlay_result({"find": "cat", "replace": "dog"})
        assert app._doc.text == "the dog sat"
        assert app._status.current == "Replaced"
        # Cursor moved past the inserted text.
        assert (app._doc.cursor_line, app._doc.cursor_col) == (0, 4 + len("dog"))
        # Exactly one undo entry restores the original text.
        assert app._doc.undo() is True
        assert app._doc.text == "the cat sat"
        assert app._doc.undo() is False

    def test_handle_overlay_result_replace_no_match(self, tmp_path):
        # BUG-1: a no-match replace changes nothing and shows "Not found".
        app = self._make_app(tmp_path)
        app._doc.load("the cat sat", "test")
        app._doc.cursor_line = 0
        app._doc.cursor_col = 0
        app._handle_overlay_result({"find": "zzz", "replace": "dog"})
        assert app._doc.text == "the cat sat"
        assert app._status.current == "Not found"
        assert app._doc.undo() is False  # undo stack untouched

    def test_handle_overlay_result_none(self, tmp_path):
        app = self._make_app(tmp_path)
        # Should not raise
        app._handle_overlay_result(None)

    def test_handle_overlay_result_font_calls_on_exit(self, tmp_path):
        # BUG-10: font change must exit the outgoing mode and preserve index.
        from unittest.mock import MagicMock

        app = self._make_app(tmp_path)
        app._mode_idx = 1
        app._mode = app._modes[1]
        outgoing = app._mode
        outgoing.on_exit = MagicMock(wraps=outgoing.on_exit)
        app._handle_overlay_result({"font": "Courier"})
        outgoing.on_exit.assert_called_once()
        # Index preserved and a fresh mode instance is active at that index.
        assert app._mode_idx == 1
        assert app._mode is app._modes[1]
        assert app._mode is not outgoing

    def test_handle_overlay_result_font_preserves_scroll(self, tmp_path):
        # BUG-10: in-mode scroll state survives a font change.
        app = self._make_app(tmp_path)
        app._mode._scroll_offset = 7
        app._handle_overlay_result({"font": "Courier"})
        assert app._mode._scroll_offset == 7


class TestOnAnyKey:
    def _make_app(self, tmp_path):
        from writerdeck.utils.platform import HardwareProfile
        from writerdeck.core.app import App

        with patch("writerdeck.core.app.get_config") as mc, \
             patch("writerdeck.core.app.detect_platform") as mp, \
             patch("writerdeck.core.app.create_driver") as md:
            mc.return_value = _make_config({"documents_dir": str(tmp_path)})
            mp.return_value = HardwareProfile(
                name="desktop", is_pi=False, is_pi_zero=False,
                partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
            )
            md.return_value = MagicMock()
            return App()

    def test_wakes_from_display_sleep(self, tmp_path):
        app = self._make_app(tmp_path)
        app._display_sleeping = True
        app._on_any_key()
        assert app._display_sleeping is False
        # wake() must NOT be called from the keyboard background thread (EPD
        # SPI is not thread-safe); the flag signals the main thread to do it.
        app._driver.wake.assert_not_called()
        assert app._needs_display_wake is True

    def test_reverses_tier2(self, tmp_path):
        app = self._make_app(tmp_path)
        app._tier2_active = True
        with patch.object(app, "_exit_cpu_powersave") as mock_exit:
            app._on_any_key()
            mock_exit.assert_called_once()

    def test_reverses_tier3(self, tmp_path):
        app = self._make_app(tmp_path)
        app._tier3_active = True
        app._on_any_key()
        assert app._tier3_active is False

    def test_updates_last_keypress(self, tmp_path):
        import time
        app = self._make_app(tmp_path)
        before = time.monotonic()
        app._on_any_key()
        assert app._last_keypress >= before


class TestSleepTiers:
    def _make_app(self, tmp_path):
        from writerdeck.utils.platform import HardwareProfile
        from writerdeck.core.app import App

        with patch("writerdeck.core.app.get_config") as mc, \
             patch("writerdeck.core.app.detect_platform") as mp, \
             patch("writerdeck.core.app.create_driver") as md:
            mc.return_value = _make_config({"documents_dir": str(tmp_path)})
            mp.return_value = HardwareProfile(
                name="desktop", is_pi=False, is_pi_zero=False,
                partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
            )
            md.return_value = MagicMock()
            return App()

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=MagicMock)
    def test_enter_cpu_powersave(self, mock_open, mock_exists, tmp_path):
        app = self._make_app(tmp_path)
        app._enter_cpu_powersave()
        assert app._tier2_active is True

    @patch("os.path.exists", return_value=False)
    def test_enter_cpu_powersave_no_sysfs(self, mock_exists, tmp_path):
        app = self._make_app(tmp_path)
        app._enter_cpu_powersave()
        assert app._tier2_active is False  # path doesn't exist

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=MagicMock)
    def test_exit_cpu_powersave(self, mock_open, mock_exists, tmp_path):
        app = self._make_app(tmp_path)
        app._tier2_active = True
        app._exit_cpu_powersave()
        assert app._tier2_active is False

    @patch("os.system")
    def test_enter_system_suspend(self, mock_system, tmp_path):
        app = self._make_app(tmp_path)
        app._enter_system_suspend()
        assert app._tier3_active is True
        mock_system.assert_called_once_with("systemctl suspend")


class TestWatchdog:
    def _make_app(self, tmp_path):
        from writerdeck.utils.platform import HardwareProfile
        from writerdeck.core.app import App

        with patch("writerdeck.core.app.get_config") as mc, \
             patch("writerdeck.core.app.detect_platform") as mp, \
             patch("writerdeck.core.app.create_driver") as md:
            mc.return_value = _make_config({"documents_dir": str(tmp_path)})
            mp.return_value = HardwareProfile(
                name="desktop", is_pi=False, is_pi_zero=False,
                partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
            )
            md.return_value = MagicMock()
            return App()

    def test_no_socket_is_noop(self, tmp_path):
        app = self._make_app(tmp_path)
        with patch.dict(os.environ, {}, clear=True):
            # Should not raise
            app._notify_watchdog()

    @patch("socket.socket")
    def test_sends_watchdog_signal(self, mock_socket_cls, tmp_path):
        app = self._make_app(tmp_path)
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        with patch.dict(os.environ, {"NOTIFY_SOCKET": "/run/systemd/notify"}):
            app._notify_watchdog()
        mock_sock.sendto.assert_called_once_with(
            b"WATCHDOG=1", "/run/systemd/notify"
        )
        mock_sock.close.assert_called_once()

    @patch("socket.socket")
    def test_abstract_socket(self, mock_socket_cls, tmp_path):
        app = self._make_app(tmp_path)
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        with patch.dict(os.environ, {"NOTIFY_SOCKET": "@/run/systemd/notify"}):
            app._notify_watchdog()
        mock_sock.sendto.assert_called_once_with(
            b"WATCHDOG=1", "\0/run/systemd/notify"
        )


class TestExportUSB:
    def _make_app(self, tmp_path):
        from writerdeck.utils.platform import HardwareProfile
        from writerdeck.core.app import App

        with patch("writerdeck.core.app.get_config") as mc, \
             patch("writerdeck.core.app.detect_platform") as mp, \
             patch("writerdeck.core.app.create_driver") as md:
            mc.return_value = _make_config({"documents_dir": str(tmp_path)})
            mp.return_value = HardwareProfile(
                name="desktop", is_pi=False, is_pi_zero=False,
                partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
            )
            md.return_value = MagicMock()
            return App()

    @patch("writerdeck.core.app.export_documents", return_value=3)
    @patch("writerdeck.core.app.find_usb_mount", return_value="/mnt/usb")
    def test_export_success(self, mock_find, mock_export, tmp_path):
        from writerdeck.input.keymapper import KeyAction
        app = self._make_app(tmp_path)
        app._handle_action(KeyAction.EXPORT_USB, "")
        assert "3 files" in app._status.current

    @patch("writerdeck.core.app.find_usb_mount", return_value=None)
    def test_export_no_usb(self, mock_find, tmp_path):
        from writerdeck.input.keymapper import KeyAction
        app = self._make_app(tmp_path)
        app._handle_action(KeyAction.EXPORT_USB, "")
        assert "No USB" in app._status.current


class TestIdleDisplaySleep:
    """LONG-1: aggressive panel idle-sleep after display_idle_sleep_seconds."""

    def _make_app(self, tmp_path, overrides=None):
        from writerdeck.utils.platform import HardwareProfile
        from writerdeck.core.app import App

        base_overrides = {
            "documents_dir": str(tmp_path),
            "display_idle_sleep_seconds": 20,
            # Keep other tiers off so only the aggressive trigger is exercised.
            "sleep_tiers": {
                "display_off_minutes": 5,
                "cpu_powersave_minutes": 0,
                "system_suspend_minutes": 0,
            },
        }
        if overrides:
            base_overrides.update(overrides)
        with patch("writerdeck.core.app.get_config") as mc, \
             patch("writerdeck.core.app.detect_platform") as mp, \
             patch("writerdeck.core.app.create_driver") as md:
            mc.return_value = _make_config(base_overrides)
            mp.return_value = HardwareProfile(
                name="desktop", is_pi=False, is_pi_zero=False,
                partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
            )
            md.return_value = MagicMock()
            return App()

    def _run_loop(self, app, ticks):
        """Run the real main loop for a fixed number of iterations, then stop."""
        state = {"n": 0}

        def fake_wait(timeout=None):
            state["n"] += 1
            if state["n"] >= ticks:
                app._running = False
            return True

        app._wakeup.wait = fake_wait  # type: ignore[assignment]
        # Avoid touching real subsystems / disk during run().
        app._keyboard.start = MagicMock()  # type: ignore[method-assign]
        app._keyboard.stop = MagicMock()  # type: ignore[method-assign]
        app._power.start = MagicMock()  # type: ignore[method-assign]
        app._power.stop = MagicMock()  # type: ignore[method-assign]
        app.run()

    def test_sleeps_after_idle_threshold(self, tmp_path):
        import time as _time
        app = self._make_app(tmp_path)
        # Pretend the last keystroke was well past the 20s aggressive threshold.
        app._last_keypress = _time.monotonic() - 25
        self._run_loop(app, ticks=1)
        # Panel deep-sleep was triggered on the MAIN thread.
        app._driver.sleep.assert_called()
        assert app._display_sleeping is True

    def test_does_not_sleep_before_threshold(self, tmp_path):
        import time as _time
        app = self._make_app(tmp_path)
        app._last_keypress = _time.monotonic() - 5  # under 20s
        self._run_loop(app, ticks=1)
        assert app._display_sleeping is False

    def test_key_thread_only_sets_flag_no_spi(self, tmp_path):
        # _on_any_key runs on the keyboard background thread: it must NOT make
        # any driver/SPI call, only set flags for the main thread.
        app = self._make_app(tmp_path)
        app._display_sleeping = True
        app._on_any_key()
        app._driver.wake.assert_not_called()
        app._driver.sleep.assert_not_called()
        assert app._needs_display_wake is True
        assert app._display_sleeping is False

    def test_key_wakes_and_full_refreshes(self, tmp_path):
        import time as _time
        from writerdeck.input.keymapper import KeyAction

        app = self._make_app(tmp_path)
        # Enter idle sleep on the first tick.
        app._last_keypress = _time.monotonic() - 25

        state = {"n": 0}

        def fake_wait(timeout=None):
            state["n"] += 1
            if state["n"] == 1:
                # After the first (sleeping) tick, simulate a keypress arriving:
                # on_any_key sets the wake flag, then a real action is queued so
                # the loop's render path runs wake() + full refresh.
                app._on_any_key()
                app._last_keypress = _time.monotonic()
                app._keyboard.queue.put((KeyAction.CHAR, "a"))
            if state["n"] >= 2:
                app._running = False
            return True

        app._wakeup.wait = fake_wait  # type: ignore[assignment]
        app._keyboard.start = MagicMock()  # type: ignore[method-assign]
        app._keyboard.stop = MagicMock()  # type: ignore[method-assign]
        app._power.start = MagicMock()  # type: ignore[method-assign]
        app._power.stop = MagicMock()  # type: ignore[method-assign]

        app.run()

        # Panel slept once (tick 1) then woke once (tick 2, main thread).
        app._driver.sleep.assert_called()
        app._driver.wake.assert_called_once()
        # A wake forces the first post-wake frame to be a full refresh.
        app._driver.display_full.assert_called()
        app._driver.display_partial.assert_not_called()


class TestStatsCadenceDecoupled:
    """PERF-1 part 2: volatile stats don't repaint on the per-keystroke path."""

    def _make_app(self, tmp_path, overrides=None):
        from writerdeck.core.app import App
        from writerdeck.utils.platform import HardwareProfile

        base_overrides = {"documents_dir": str(tmp_path)}
        if overrides:
            base_overrides.update(overrides)
        with patch("writerdeck.core.app.get_config") as mc, \
             patch("writerdeck.core.app.detect_platform") as mp, \
             patch("writerdeck.core.app.create_driver") as md:
            mc.return_value = _make_config(base_overrides)
            mp.return_value = HardwareProfile(
                name="desktop", is_pi=False, is_pi_zero=False,
                partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
            )
            md.return_value = MagicMock()
            return App()

    def test_full_refresh_snapshots_live_stats(self, tmp_path):
        app = self._make_app(tmp_path)
        app._doc.load("hello world foo", "d.txt")
        app._refresh.request_full()
        app._render_and_refresh(force_full=True)
        # The Words value painted on the full refresh is the live count.
        assert app._stats_snapshot is not None
        assert app._stats_snapshot["Words"] == str(app._doc.word_count)

    def test_partial_freezes_stats_to_snapshot(self, tmp_path):
        import time as _time
        app = self._make_app(tmp_path)
        # First: a full refresh captures the snapshot at the current word count.
        app._doc.load("one two", "d.txt")
        app._refresh.request_full()
        app._render_and_refresh(force_full=True)
        snapshot_words = app._stats_snapshot["Words"]

        # Now type more words and take the PARTIAL path — the rendered frame's
        # stats must be frozen to the snapshot so the footer bytes don't change.
        app._doc.load("one two three four five", "d.txt")
        app._refresh.record_refresh(was_full=True)  # clear force_full
        app._last_keypress = _time.monotonic()

        rendered = {}
        orig_render = app._mode.render

        def capture(doc, session):
            frame = orig_render(doc, session)
            rendered["frame"] = frame
            return frame

        app._mode.render = capture  # type: ignore[method-assign]
        app._render_and_refresh()
        # display_partial ran (not full), and the frame's stats were rewritten
        # to the frozen snapshot value, not the new live count.
        app._driver.display_partial.assert_called()
        assert rendered["frame"].stats["Words"] == snapshot_words


def _hw():
    from writerdeck.utils.platform import HardwareProfile
    return HardwareProfile(
        name="desktop", is_pi=False, is_pi_zero=False,
        partial_refresh_max_streak=50, render_interval_ms=100, font_size=16,
    )


def _make_app_with(tmp_path, overrides=None):
    from writerdeck.core.app import App
    base_overrides = {"documents_dir": str(tmp_path)}
    if overrides:
        base_overrides.update(overrides)
    with patch("writerdeck.core.app.get_config") as mc, \
         patch("writerdeck.core.app.detect_platform") as mp, \
         patch("writerdeck.core.app.create_driver") as md:
        mc.return_value = _make_config(base_overrides)
        mp.return_value = _hw()
        md.return_value = MagicMock()
        return App()


class TestRuntimeHeadlessFallback:
    """FAULT-7 — panel dies at runtime; app keeps input + autosave, retries panel."""

    def test_display_error_enters_headless_no_crash(self, tmp_path):
        from writerdeck.display.driver import DisplayError
        app = _make_app_with(tmp_path)
        app._driver.display_full.side_effect = DisplayError("dead panel")
        app._driver.display_partial.side_effect = DisplayError("dead panel")
        app._refresh.request_full()
        # Must NOT raise — degrades to headless instead.
        app._render_and_refresh(force_full=True)
        assert app._headless is True

    def test_headless_keeps_draining_input_and_autosaving(self, tmp_path):
        from writerdeck.display.driver import DisplayError
        from writerdeck.input.keymapper import KeyAction

        app = _make_app_with(tmp_path)
        app._driver.display_full.side_effect = DisplayError("dead")
        app._driver.display_partial.side_effect = DisplayError("dead")
        # Panel retry defaults to every 30s; within these few ticks it won't
        # fire, so the app stays headless throughout this run.

        state = {"n": 0}

        def fake_wait(timeout=None):
            state["n"] += 1
            if state["n"] == 1:
                # First tick: type a char → triggers a render → DisplayError →
                # headless. Queue more input for the following ticks.
                app._on_any_key()
                app._keyboard.queue.put((KeyAction.CHAR, "a"))
            elif state["n"] == 2:
                app._on_any_key()
                app._keyboard.queue.put((KeyAction.CHAR, "b"))
            if state["n"] >= 3:
                app._running = False
            return True

        app._wakeup.wait = fake_wait  # type: ignore[assignment]
        app._keyboard.start = MagicMock()  # type: ignore[method-assign]
        app._keyboard.stop = MagicMock()  # type: ignore[method-assign]
        app._power.start = MagicMock()  # type: ignore[method-assign]
        app._power.stop = MagicMock()  # type: ignore[method-assign]
        app._file_mgr.maybe_autosave = MagicMock()  # type: ignore[method-assign]

        app.run()  # must not raise

        assert app._headless is True
        # Both typed characters made it into the document (input never dropped).
        assert "a" in app._doc.text and "b" in app._doc.text
        # Autosave kept being attempted every tick even while headless.
        assert app._file_mgr.maybe_autosave.call_count >= 3

    def test_panel_retried_on_interval(self, tmp_path):
        app = _make_app_with(tmp_path)
        app._headless = True
        app._headless_retry_secs = 30.0
        # Last retry was long ago → this call should attempt init().
        app._last_headless_retry = time.monotonic() - 100
        app._driver.init.side_effect = RuntimeError("still dead")
        app._maybe_retry_panel()
        app._driver.init.assert_called_once()
        assert app._headless is True  # still dead → stays headless

    def test_retry_too_soon_is_skipped(self, tmp_path):
        app = _make_app_with(tmp_path)
        app._headless = True
        app._headless_retry_secs = 30.0
        app._last_headless_retry = time.monotonic()  # just retried
        app._maybe_retry_panel()
        app._driver.init.assert_not_called()

    def test_recovery_forces_full_refresh(self, tmp_path):
        app = _make_app_with(tmp_path)
        app._headless = True
        app._last_headless_retry = time.monotonic() - 100
        # init() succeeds this time → recovery path renders a full refresh.
        app._driver.init.side_effect = None
        app._maybe_retry_panel()
        assert app._headless is False
        # A forced full refresh was rendered on recovery.
        app._driver.display_full.assert_called()

    def test_recovery_failing_again_stays_headless(self, tmp_path):
        from writerdeck.display.driver import DisplayError
        app = _make_app_with(tmp_path)
        app._headless = True
        app._last_headless_retry = time.monotonic() - 100
        app._driver.init.side_effect = None  # init recovers
        app._driver.display_full.side_effect = DisplayError("dead again")
        app._maybe_retry_panel()
        # Recovery frame failed → fell straight back to headless.
        assert app._headless is True


class TestScreensaver:
    """LONG-3 — blank to a white 'paused' frame before long-idle deep sleep."""

    def _run_loop(self, app, ticks):
        state = {"n": 0}

        def fake_wait(timeout=None):
            state["n"] += 1
            if state["n"] >= ticks:
                app._running = False
            return True

        app._wakeup.wait = fake_wait  # type: ignore[assignment]
        app._keyboard.start = MagicMock()  # type: ignore[method-assign]
        app._keyboard.stop = MagicMock()  # type: ignore[method-assign]
        app._power.start = MagicMock()  # type: ignore[method-assign]
        app._power.stop = MagicMock()  # type: ignore[method-assign]
        app.run()

    def test_paused_frame_shown_before_sleep(self, tmp_path):
        app = _make_app_with(
            tmp_path,
            {
                "display_idle_sleep_seconds": 20,
                "display_screensaver_seconds": 20,
                "sleep_tiers": {
                    "display_off_minutes": 5,
                    "cpu_powersave_minutes": 0,
                    "system_suspend_minutes": 0,
                },
            },
        )
        app._last_keypress = time.monotonic() - 25  # past the idle threshold
        self._run_loop(app, ticks=1)
        # The last displayed frame before sleep was the white/paused frame, and
        # then the panel deep-slept.
        app._driver.display_full.assert_called()
        app._driver.sleep.assert_called()
        assert app._screensaver_shown is True
        assert app._display_sleeping is True

    def test_screensaver_disabled_when_zero(self, tmp_path):
        app = _make_app_with(
            tmp_path,
            {
                "display_idle_sleep_seconds": 20,
                "display_screensaver_seconds": 0,  # disabled
                "sleep_tiers": {
                    "display_off_minutes": 5,
                    "cpu_powersave_minutes": 0,
                    "system_suspend_minutes": 0,
                },
            },
        )
        app._last_keypress = time.monotonic() - 25
        self._run_loop(app, ticks=1)
        assert app._screensaver_shown is False
        # Panel still sleeps, just without the paused frame.
        app._driver.sleep.assert_called()

    def test_key_rearms_screensaver(self, tmp_path):
        app = _make_app_with(tmp_path)
        app._screensaver_shown = True
        app._on_any_key()
        assert app._screensaver_shown is False

    def test_screensaver_display_error_goes_headless(self, tmp_path):
        from writerdeck.display.driver import DisplayError
        app = _make_app_with(tmp_path)
        app._driver.display_full.side_effect = DisplayError("dead")
        app._show_screensaver()
        assert app._headless is True
