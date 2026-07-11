"""Tests for PygameKeyboardReader focus-loss handling (no live window)."""

from __future__ import annotations

from types import SimpleNamespace

import pygame

from writerdeck.input.pygame_reader import PygameKeyboardReader


class TestFocusLoss:
    def test_window_focus_lost_resets_mapper(self, monkeypatch):
        reader = PygameKeyboardReader()
        # Modifier held at the moment focus is lost (e.g. Alt/Cmd-Tab).
        reader._mapper.process_event(29, 1)  # Ctrl press
        assert reader._mapper._ctrl_held is True

        event = SimpleNamespace(type=pygame.WINDOWFOCUSLOST)
        monkeypatch.setattr(pygame.event, "get", lambda: [event])
        reader.poll()

        assert reader._mapper._ctrl_held is False

    def test_activeevent_focus_out_resets_mapper(self, monkeypatch):
        reader = PygameKeyboardReader()
        reader._mapper.process_event(42, 1)  # Shift press
        assert reader._mapper._shift_held is True

        event = SimpleNamespace(type=pygame.ACTIVEEVENT, gain=0)
        monkeypatch.setattr(pygame.event, "get", lambda: [event])
        reader.poll()

        assert reader._mapper._shift_held is False
