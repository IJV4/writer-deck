"""Tests for splash screen rendering."""

from writerdeck.display.splash import render_splash
from writerdeck.display.driver import WIDTH, HEIGHT


class TestSplash:
    def test_render_splash_dimensions(self):
        img = render_splash()
        assert img.size == (WIDTH, HEIGHT)

    def test_render_splash_mode(self):
        img = render_splash()
        assert img.mode == "1"  # 1-bit
