"""Tests for Power battery history and drain estimation."""

import time
from unittest import mock

from writerdeck.utils.power import SHUTDOWN_DEBOUNCE_SAMPLES, Power


class TestDrainRate:
    def test_no_history(self):
        p = Power(enabled=False)
        assert p.drain_rate_pct_per_hour is None

    def test_insufficient_history(self):
        p = Power(enabled=False)
        p._history.append((time.monotonic(), 80))
        assert p.drain_rate_pct_per_hour is None

    def test_drain_rate_calculation(self):
        p = Power(enabled=False)
        now = time.monotonic()
        # Simulate 1 hour of drain from 100% to 90%
        p._history.append((now - 3600, 100))
        p._history.append((now, 90))
        rate = p.drain_rate_pct_per_hour
        assert rate is not None
        assert abs(rate - 10.0) < 0.1

    def test_estimated_remaining(self):
        p = Power(enabled=False)
        p.battery_level = 50
        now = time.monotonic()
        p._history.append((now - 3600, 100))
        p._history.append((now, 90))
        remaining = p.estimated_remaining_hours
        assert remaining is not None
        assert abs(remaining - 5.0) < 0.1  # 50% / 10%/hr = 5 hours

    def test_charging_no_drain(self):
        p = Power(enabled=False)
        now = time.monotonic()
        p._history.append((now - 3600, 80))
        p._history.append((now, 90))  # Charging, level went up
        assert p.drain_rate_pct_per_hour is None
        assert p.estimated_remaining_hours is None

    def test_battery_bar(self):
        p = Power(enabled=False)
        p.battery_level = 60
        bar = p.battery_bar(5)
        assert "60%" in bar
        assert "\u25a0" in bar

    def test_battery_bar_charging(self):
        p = Power(enabled=False)
        p.battery_level = 80
        p.is_charging = True
        bar = p.battery_bar(5)
        assert "80%+" in bar

    def test_available_false_by_default(self):
        p = Power(enabled=False)
        assert p.available is False

    def test_available_true_after_update(self):
        p = Power(enabled=False)
        p._available = True
        assert p.available is True


def _run_monitor_with_readings(p, readings):
    """Drive Power._monitor_loop over a scripted list of (level, charging) samples.

    Each entry of ``readings`` is applied as one loop iteration by stubbing
    ``_update``. The loop is stopped after the last reading (or immediately once
    the shutdown path fires and returns).
    """
    samples = iter(readings)

    def fake_update():
        try:
            level, charging = next(samples)
        except StopIteration:
            # No more scripted samples: stop the loop and present a healthy,
            # non-critical reading so the trailing iteration can't spuriously
            # extend the low-battery streak.
            p._running = False
            p._available = True
            p.battery_level = 100
            p.is_charging = False
            return
        p._available = True
        p.battery_level = level
        p.is_charging = charging

    p._running = True
    p._check_interval = 0
    with (
        mock.patch.object(p, "_update", side_effect=fake_update),
        mock.patch("writerdeck.utils.power.subprocess.run") as mock_run,
        mock.patch("writerdeck.utils.power.time.sleep"),
    ):
        mock_run.return_value.returncode = 0
        p._monitor_loop()
    return mock_run


class TestCriticalShutdownDebounce:
    """BUG-7 \u2014 require N consecutive sub-threshold samples before poweroff."""

    def test_single_low_reading_does_not_shutdown(self):
        p = Power(shutdown_pct=3)
        callback = mock.Mock()
        p._shutdown_callback = callback
        # One critical reading, then healthy readings.
        mock_run = _run_monitor_with_readings(p, [(2, False), (50, False), (50, False)])
        callback.assert_not_called()
        mock_run.assert_not_called()

    def test_n_consecutive_low_readings_trigger_shutdown(self):
        p = Power(shutdown_pct=3)
        callback = mock.Mock()
        p._shutdown_callback = callback
        readings = [(2, False)] * SHUTDOWN_DEBOUNCE_SAMPLES
        mock_run = _run_monitor_with_readings(p, readings)
        callback.assert_called_once()
        mock_run.assert_called_once()
        assert mock_run.call_args.args[0] == ["sudo", "systemctl", "poweroff"]

    def test_healthy_reading_resets_streak(self):
        p = Power(shutdown_pct=3)
        callback = mock.Mock()
        p._shutdown_callback = callback
        # Two low, one healthy (reset), then two more low: never N in a row.
        readings = [(2, False), (2, False), (50, False), (2, False), (2, False)]
        mock_run = _run_monitor_with_readings(p, readings)
        callback.assert_not_called()
        mock_run.assert_not_called()

    def test_charging_reading_resets_streak(self):
        p = Power(shutdown_pct=3)
        callback = mock.Mock()
        p._shutdown_callback = callback
        # A sub-threshold-but-charging reading must not count toward shutdown.
        readings = [(2, False), (2, True), (2, False), (2, False)]
        mock_run = _run_monitor_with_readings(p, readings)
        callback.assert_not_called()
        mock_run.assert_not_called()


class TestQuerySocketClosed:
    """BUG-9 \u2014 _query must close the socket even on the error path."""

    def test_socket_closed_on_error(self):
        # A fully mocked socket whose connect() raises; the `with` block must
        # still close it (via __exit__) rather than leaking it.
        sock = mock.MagicMock()
        sock.connect.side_effect = OSError("boom")
        sock.__enter__.return_value = sock

        p = Power(enabled=False)
        with mock.patch("writerdeck.utils.power.socket.socket", return_value=sock):
            result = p._query("get battery")

        assert result is None
        # `with socket.socket(...) as sock:` closes the socket on exit even when
        # the body raises — real sockets close via __exit__ -> close().
        sock.__exit__.assert_called_once()


class TestEmergencyShutdownOrdering:
    """FAULT-5 — the panel deep-sleep (callback) completes BEFORE poweroff."""

    def test_callback_runs_to_completion_before_poweroff(self):
        # The emergency callback (which deep-sleeps the panel) must finish before
        # the poweroff command is issued — don't rely on winning the power race.
        p = Power(shutdown_pct=3)
        order: list[str] = []

        def callback():
            order.append("callback")

        p._shutdown_callback = callback

        readings = [(2, False)] * SHUTDOWN_DEBOUNCE_SAMPLES

        samples = iter(readings)

        def fake_update():
            try:
                level, charging = next(samples)
            except StopIteration:
                p._running = False
                p._available = True
                p.battery_level = 100
                p.is_charging = False
                return
            p._available = True
            p.battery_level = level
            p.is_charging = charging

        def fake_run(cmd, **kwargs):
            order.append(f"poweroff:{' '.join(cmd)}")
            return mock.Mock(returncode=0, stderr="")

        p._running = True
        p._check_interval = 0
        with (
            mock.patch.object(p, "_update", side_effect=fake_update),
            mock.patch("writerdeck.utils.power.subprocess.run", side_effect=fake_run),
            mock.patch("writerdeck.utils.power.time.sleep"),
        ):
            p._monitor_loop()

        # Callback (panel sleep) recorded strictly before the poweroff call.
        assert order == ["callback", "poweroff:sudo systemctl poweroff"]

    def test_poweroff_issued_even_without_callback(self):
        # No callback wired — poweroff still fires once debounce is met.
        p = Power(shutdown_pct=3)
        p._shutdown_callback = None
        mock_run = _run_monitor_with_readings(
            p, [(2, False)] * SHUTDOWN_DEBOUNCE_SAMPLES
        )
        mock_run.assert_called_once()
        assert mock_run.call_args.args[0] == ["sudo", "systemctl", "poweroff"]

    def test_callback_exception_does_not_block_poweroff(self):
        # FAULT-5 hardware-safety guarantee: even if the emergency callback raises,
        # poweroff MUST still be issued (protecting the battery is the priority),
        # and the exception must NOT escape the monitor loop.
        p = Power(shutdown_pct=3)

        def callback():
            raise RuntimeError("panel sleep failed")

        p._shutdown_callback = callback
        mock_run = _run_monitor_with_readings(
            p, [(2, False)] * SHUTDOWN_DEBOUNCE_SAMPLES
        )
        mock_run.assert_called_once()
        assert mock_run.call_args.args[0] == ["sudo", "systemctl", "poweroff"]


class TestStaleSocketData:
    """D-power/1 — a dead socket must not trigger poweroff from frozen data."""

    def test_failed_query_marks_unavailable(self):
        # A failed battery query (None) must clear availability rather than
        # leaving a stale True from a previous healthy cycle.
        p = Power(enabled=False)
        p._available = True
        with mock.patch.object(p, "_query", return_value=None):
            p._update()
        assert p.available is False

    def test_recovered_query_restores_availability(self):
        p = Power(enabled=False)
        p._available = False

        def fake_query(cmd):
            if cmd == "get battery":
                return "battery: 42"
            return "battery_charging: false"

        with mock.patch.object(p, "_query", side_effect=fake_query):
            p._update()
        assert p.available is True
        assert p.battery_level == 42

    def test_stale_critical_data_does_not_trigger_shutdown(self):
        # Prime a genuine critical (2%, not charging) reading, then simulate a
        # dead socket for several cycles (query returns None). The stale critical
        # values must NOT count toward the debounce streak, so no shutdown fires.
        p = Power(shutdown_pct=3)
        callback = mock.Mock()
        p._shutdown_callback = callback

        # Prime last-known critical state as if a real reading had landed.
        p.battery_level = 2
        p.is_charging = False

        queries = iter([None] * (SHUTDOWN_DEBOUNCE_SAMPLES * 4))

        def fake_update():
            try:
                next(queries)
            except StopIteration:
                p._running = False
                return
            # Simulate a failed query cycle: real _update would clear _available
            # while leaving battery_level/is_charging frozen at their critical
            # last-known values.
            p._available = False
            # battery_level / is_charging deliberately left frozen at 2 / False.

        p._running = True
        p._check_interval = 0
        with (
            mock.patch.object(p, "_update", side_effect=fake_update),
            mock.patch("writerdeck.utils.power.subprocess.run") as mock_run,
            mock.patch("writerdeck.utils.power.time.sleep"),
        ):
            mock_run.return_value.returncode = 0
            p._monitor_loop()

        callback.assert_not_called()
        mock_run.assert_not_called()
        assert p._low_battery_streak == 0


class TestStopJoinsThread:
    """D-power/2 — stop() joins the monitor thread for graceful shutdown."""

    def test_stop_joins_thread(self):
        p = Power(enabled=True)
        p._shutdown_callback = None
        # Real thread, but _update does nothing and interval is instant-ish.
        with (
            mock.patch.object(p, "_update"),
            mock.patch("writerdeck.utils.power.time.sleep"),
        ):
            p.start()
            thread = p._thread
            assert thread is not None
            p.stop()
        assert p._running is False
        # After stop() returns, the monitor thread must have finished.
        assert thread is not None
        assert not thread.is_alive()

    def test_stop_without_start_is_noop(self):
        p = Power(enabled=False)
        # Never started: _thread is None; stop() must not raise.
        p.stop()
        assert p._running is False
