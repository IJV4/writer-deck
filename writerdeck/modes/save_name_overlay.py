"""Save name overlay — prompts for a filename on first save."""

from __future__ import annotations

from typing import Any

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.modes.overlay import Overlay


class SaveNameOverlay(Overlay):
    def __init__(self, default_name: str) -> None:
        self._name = default_name

    def handle_input(self, action: KeyAction, char: str) -> Any | None:
        if action == KeyAction.ESCAPE:
            return {}  # cancelled — don't save
        if action == KeyAction.ENTER:
            name = self._name.strip()
            if name:
                return {"save_as": name}
            return {}
        if action == KeyAction.BACKSPACE:
            self._name = self._name[:-1]
            return None
        if char and char.isprintable():
            self._name += char
            return None
        return None

    def render(self, base_frame: RenderFrame) -> RenderFrame:
        lines = list(base_frame.text_lines)
        prompt_lines = [
            "",
            f"> Save as: {self._name}_",
            "  [Enter] Save  [Esc] Cancel",
        ]
        visible_count = max(0, len(lines) - len(prompt_lines))
        display_lines = lines[:visible_count] + prompt_lines

        return RenderFrame(
            text_lines=display_lines,
            cursor_line=base_frame.cursor_line,
            cursor_col=base_frame.cursor_col,
            show_cursor=False,
            stats=base_frame.stats,
            stats_position=base_frame.stats_position,
            sidebar_width=base_frame.sidebar_width,
            force_full_refresh=True,
            margin_top=base_frame.margin_top,
            margin_bottom=base_frame.margin_bottom,
            margin_left=base_frame.margin_left,
            title=base_frame.title,
        )
