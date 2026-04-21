"""Distraction-Free mode — full canvas text with a tiny word count footer."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import BaseMode, RenderFrame
from writerdeck.utils.text_wrapper import map_selection, wrap_lines


class DistractionFreeMode(BaseMode):
    name = "distraction_free"

    def __init__(self, text_width_px: int = 784, font_family: str = "Hack", font_size: int = 14) -> None:
        super().__init__()
        self._text_width_px = text_width_px
        self._font_family = font_family
        self._font_size = font_size

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

        # Apply scroll offset for page up/down
        visible = wrapped
        show_cursor = True
        adj_cursor = cursor_line
        if self._scroll_offset > 0:
            visible = wrapped[self._scroll_offset:]
            adj_cursor = cursor_line - self._scroll_offset
            if adj_cursor < 0 or adj_cursor >= len(visible):
                show_cursor = False

        stats = {"Words": str(doc.word_count)}

        selection = (
            map_selection(doc.selection.ordered(), row_map, self._scroll_offset)
            if doc.selection is not None else None
        )

        return RenderFrame(
            text_lines=visible,
            cursor_line=adj_cursor,
            cursor_col=cursor_col,
            show_cursor=show_cursor,
            stats=stats,
            stats_position="footer",
            margin_top=8,
            margin_bottom=24,
            margin_left=8,
            selection=selection,
        )

