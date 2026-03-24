"""Tests for StatusBar."""

import time

from writerdeck.display.status_bar import StatusBar


class TestStatusBar:
    def test_show_message(self):
        bar = StatusBar()
        bar.show("Saved")
        assert bar.current == "Saved"

    def test_message_expires(self):
        bar = StatusBar()
        bar.show("Saved", duration=0.01)
        time.sleep(0.02)
        assert bar.current is None

    def test_no_message(self):
        bar = StatusBar()
        assert bar.current is None

    def test_message_replaced(self):
        bar = StatusBar()
        bar.show("First")
        bar.show("Second")
        assert bar.current == "Second"
