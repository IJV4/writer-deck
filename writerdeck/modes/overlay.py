"""Overlay ABC — base class for modal UI overlays."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame


class Overlay(ABC):
    @abstractmethod
    def handle_input(self, action: KeyAction, char: str) -> Any | None:
        """Handle input. Return non-None to signal completion with a result."""
        ...

    @abstractmethod
    def render(self, base_frame: RenderFrame) -> RenderFrame:
        """Render the overlay on top of the base frame."""
        ...
