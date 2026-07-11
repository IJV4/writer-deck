"""Tests for main.py entry point — focused on the atexit cleanup hook (FAULT-3)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_atexit_registers_driver_close():
    """main() must register app._driver.close with atexit so the panel is
    deep-slept on any interpreter exit path (belt-and-suspenders)."""
    import main as main_module

    fake_app = MagicMock()
    fake_config = MagicMock()
    fake_config.get.return_value = "/tmp/writer-deck-test-logs"

    with patch.object(main_module, "load_config", return_value=fake_config), \
         patch.object(main_module, "_setup_logging"), \
         patch.object(main_module, "App", return_value=fake_app), \
         patch.object(main_module, "atexit") as mock_atexit, \
         patch.object(main_module.sys, "exit"):
        main_module.main()

    mock_atexit.register.assert_called_once_with(fake_app._driver.close)


def test_close_runs_on_unhandled_exception():
    """An unhandled exception in run() still triggers emergency_save, and the
    atexit hook (registered before run) covers the driver close."""
    import main as main_module

    fake_app = MagicMock()
    fake_app.run.side_effect = RuntimeError("boom")
    fake_config = MagicMock()
    fake_config.get.return_value = "/tmp/writer-deck-test-logs"

    with patch.object(main_module, "load_config", return_value=fake_config), \
         patch.object(main_module, "_setup_logging"), \
         patch.object(main_module, "App", return_value=fake_app), \
         patch.object(main_module, "atexit") as mock_atexit, \
         patch.object(main_module.sys, "exit"):
        main_module.main()

    mock_atexit.register.assert_called_once_with(fake_app._driver.close)
    fake_app.emergency_save.assert_called_once()
