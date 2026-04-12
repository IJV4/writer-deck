"""Typewriter mode — active line fixed at ~40% from top, history scrolls up."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import BaseMode, RenderFrame
from writerdeck.utils.text_wrapper import wrap_lines
from writerdeck.display.driver import HEIGHT


_FOCUS_RATIO = 0.4  # active line sits 40% from top


class TypewriterMode(BaseMode):
    name = "typewriter"

    def __init__(self, font_family: str = "Hack", font_size: int = 14) -> None:
        super().__init__()
        self._font_family = font_family
        self._font_size = font_size
        self._text_width_px = 784

    def handle_input(self, action: KeyAction, char: str, doc: Document) -> bool:
        result = self._handle_visual_updown(action, char, doc)
        if result is not None:
            return result
        return self._apply_common_input(action, char, doc)

    def render(self, doc: Document, session: Session) -> RenderFrame:
        wrapped, cursor_line, cursor_col, row_map = wrap_lines(
            doc.lines, doc.cursor_line, doc.cursor_col,
            self._font_family, self._font_size, self._text_width_px,
        )
        self._wrapped_lines = wrapped
        self._row_map = row_map

        line_height = self._font_size + 4
        visible_lines = (HEIGHT - 32) // line_height
        focus_line = int(visible_lines * _FOCUS_RATIO)

        # Apply manual scroll offset if page up/down was used
        if self._scroll_offset > 0:
            start = max(0, self._scroll_offset)
            end = start + visible_lines
            if end > len(wrapped):
                end = len(wrapped)
                start = max(0, end - visible_lines)
            visible = wrapped[start:end]
            adj_cursor = cursor_line - start
            show_cursor = 0 <= adj_cursor < len(visible)
        else:
            # Scroll so cursor_line appears at the focus position
            start = max(0, cursor_line - focus_line)
            end = start + visible_lines
            if end > len(wrapped):
                end = len(wrapped)
                start = max(0, end - visible_lines)
            visible = wrapped[start:end]
            adj_cursor = cursor_line - start
            show_cursor = True

        # Force full refresh on newline (feels like a typewriter carriage return)
        force_full = (
            len(doc.lines) > 1
            and doc.cursor_col == 0
            and doc.cursor_line == len(doc.lines) - 1
        )

        stats = {"Words": str(doc.word_count)}

        selection = None
        if doc.selection is not None:
            selection = doc.selection.ordered()

        return RenderFrame(
            text_lines=visible,
            cursor_line=adj_cursor,
            cursor_col=cursor_col,
            show_cursor=show_cursor,
            stats=stats,
            stats_position="footer",
            force_full_refresh=force_full,
            margin_top=8,
            margin_bottom=24,
            margin_left=8,
            selection=selection,
        )
