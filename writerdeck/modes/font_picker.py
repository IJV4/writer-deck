"""Font picker overlay — arrow-navigated list of available fonts."""

from __future__ import annotations

from typing import Any

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.modes.overlay import Overlay


class FontPickerOverlay(Overlay):
    def __init__(self, fonts: list[str]) -> None:
        self._fonts = fonts if fonts else ["(no fonts found)"]
        self._selected = 0

    def handle_input(self, action: KeyAction, char: str) -> Any | None:
        if action == KeyAction.ESCAPE:
            return {}  # cancelled
        if action == KeyAction.ARROW_UP:
            self._selected = max(0, self._selected - 1)
            return None
        if action == KeyAction.ARROW_DOWN:
            self._selected = min(len(self._fonts) - 1, self._selected + 1)
            return None
        if action == KeyAction.ENTER:
            return {"font": self._fonts[self._selected]}
        return None

    def render(self, base_frame: RenderFrame) -> RenderFrame:
        # Build overlay lines
        lines = ["--- Select Font (Up/Down, Enter, Esc) ---", ""]
        for i, font in enumerate(self._fonts):
            prefix = "> " if i == self._selected else "  "
            lines.append(f"{prefix}{font}")
        lines.append("")
        lines.append("Press Enter to select, Escape to cancel")

        return RenderFrame(
            text_lines=lines,
            cursor_line=0,
            cursor_col=0,
            show_cursor=False,
            stats=None,
            force_full_refresh=True,
            margin_top=8,
            margin_bottom=8,
            margin_left=8,
        )
