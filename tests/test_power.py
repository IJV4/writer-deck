"""Tests for Power battery history and drain estimation."""

import time

from writerdeck.utils.power import Power


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
