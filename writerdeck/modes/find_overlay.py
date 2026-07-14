"""Find/Replace overlay — search and replace text in the document."""

from __future__ import annotations

from typing import Any

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.modes.overlay import Overlay


class FindOverlay(Overlay):
    def __init__(self) -> None:
        self._search: str = ""
        self._replace: str = ""
        self._in_replace_field: bool = False

    def handle_input(self, action: KeyAction, char: str) -> Any | None:
        if action == KeyAction.ESCAPE:
            return {}  # cancelled

        if action == KeyAction.CHAR:
            if self._in_replace_field:
                self._replace += char
            else:
                self._search += char
            return None

        if action == KeyAction.BACKSPACE:
            if self._in_replace_field:
                self._replace = self._replace[:-1]
            else:
                self._search = self._search[:-1]
            return None

        if action == KeyAction.ENTER:
            if not self._search:
                return None
            if self._in_replace_field:
                return {"find": self._search, "replace": self._replace}
            return {"find": self._search}

        # Tab switches between search and replace fields.
        # SWITCH_MODE_NEXT is Ctrl+Tab (works on the stdin backend); KeyAction.TAB
        # is a plain unmodified Tab (evdev/pygame emit this, not SWITCH_MODE_NEXT).
        if action in (KeyAction.TAB, KeyAction.SWITCH_MODE_NEXT):
            self._in_replace_field = not self._in_replace_field
            return None

        return None

    def render(self, base_frame: RenderFrame) -> RenderFrame:
        # Build overlay at bottom of the text area
        lines = list(base_frame.text_lines)

        # Add prompt lines at the bottom
        search_indicator = ">" if not self._in_replace_field else " "
        replace_indicator = ">" if self._in_replace_field else " "

        prompt_lines = [
            "",
            f"{search_indicator} Find: {self._search}_",
            f"{replace_indicator} Replace: {self._replace}_",
            "  [Enter] Find  [Tab] Switch  [Esc] Close",
        ]

        # Replace last few lines with prompt
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
