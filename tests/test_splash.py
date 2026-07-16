"""Tests for splash screen rendering."""

from writerdeck.display.driver import HEIGHT, WIDTH
from writerdeck.display.splash import render_low_battery, render_paused, render_splash


class TestSplash:
    def test_render_splash_dimensions(self):
        img = render_splash()
        assert img.size == (WIDTH, HEIGHT)

    def test_render_splash_mode(self):
        img = render_splash()
        assert img.mode == "1"  # 1-bit


class TestPaused:
    """LONG-3 — the mostly-white screensaver frame."""

    def test_render_paused_dimensions(self):
        img = render_paused()
        assert img.size == (WIDTH, HEIGHT)

    def test_render_paused_mode(self):
        img = render_paused()
        assert img.mode == "1"

    def test_render_paused_is_fully_blank(self):
        # No message is drawn — the panel goes fully white, no ink at all.
        img = render_paused()
        black = sum(1 for px in img.getdata() if px == 0)
        assert black == 0


class TestLowBattery:
    """Startup low-battery gate message — distinct from render_paused()
    because a blank screen here would look like a fault, not a deliberate
    refusal to start."""

    def test_render_low_battery_dimensions(self):
        img = render_low_battery(7)
        assert img.size == (WIDTH, HEIGHT)

    def test_render_low_battery_mode(self):
        img = render_low_battery(7)
        assert img.mode == "1"

    def test_render_low_battery_draws_a_message(self):
        # Unlike render_paused(), this must carry visible text.
        img = render_low_battery(7)
        black = sum(1 for px in img.getdata() if px == 0)
        assert black > 0
