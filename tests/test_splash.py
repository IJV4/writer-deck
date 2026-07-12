"""Tests for splash screen rendering."""

from writerdeck.display.splash import render_paused, render_splash
from writerdeck.display.driver import WIDTH, HEIGHT


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
