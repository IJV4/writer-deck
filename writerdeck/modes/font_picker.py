"""Font picker overlay — arrow-navigated list of available fonts."""

from __future__ import annotations

from typing import Any

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.modes.overlay import Overlay


class FontPickerOverlay(Overlay):
    def __init__(self, fonts: list[tuple[str, str]]) -> None:
        # Each entry is (family, display_label); family is what's stored in
        # config, display_label additionally shows the font's typology
        # (Serif/Sans/Monospace) so entries are distinguishable without
        # having to select each one to preview it.
        self._fonts = fonts if fonts else [("Hack", "(no fonts found)")]
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
            return {"font": self._fonts[self._selected][0]}
        return None

    def render(self, base_frame: RenderFrame) -> RenderFrame:
        # Build overlay lines. Each font's own line is rendered in that font
        # (via line_fonts) so its shape is visible directly. The "> "/"  "
        # marker is kept out of that font-overridden text and drawn via
        # line_prefixes instead — otherwise its width would vary per
        # typeface and the entries would end up left-aligned inconsistently.
        lines = ["--- Select Font (Up/Down, Enter, Esc) ---", ""]
        line_fonts: list[str | None] = [None, None]
        line_prefixes = ["", ""]
        for i, (family, label) in enumerate(self._fonts):
            lines.append(label)
            line_fonts.append(family)
            line_prefixes.append("> " if i == self._selected else "  ")
        lines.append("")
        line_fonts.append(None)
        line_prefixes.append("")
        lines.append("Press Enter to select, Escape to cancel")
        line_fonts.append(None)
        line_prefixes.append("")

        return RenderFrame(
            text_lines=lines,
            line_fonts=line_fonts,
            line_prefixes=line_prefixes,
            cursor_line=0,
            cursor_col=0,
            show_cursor=False,
            stats=None,
            # Opening/closing the picker already forces a full refresh in
            # app.py's action handlers; arrow-key navigation within the list
            # should use the normal partial-refresh path instead, so moving
            # the selection doesn't blink the whole panel every keypress.
            force_full_refresh=False,
            margin_top=8,
            margin_bottom=8,
            margin_left=8,
        )
