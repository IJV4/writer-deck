"""Tests for App lifecycle with mock subsystems."""

from __future__ import annotations

import os
import queue
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

    def test_handle_overlay_result_none(self, tmp_path):
        app = self._make_app(tmp_path)
        # Should not raise
        app._handle_overlay_result(None)


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
