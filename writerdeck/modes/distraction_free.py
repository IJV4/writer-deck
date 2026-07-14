"""Distraction-Free mode — full canvas text with a tiny word count footer."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.display.driver import HEIGHT
from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import BaseMode, RenderFrame
from writerdeck.utils.headings import line_kinds_for_rows
from writerdeck.utils.text_wrapper import map_selection, wrap_lines


class DistractionFreeMode(BaseMode):
    name = "distraction_free"

    def __init__(self, text_width_px: int = 784, font_family: str = "Hack", font_size: int = 14) -> None:
        super().__init__()
        self._text_width_px = text_width_px
        self._font_family = font_family
        self._font_size = font_size

    def handle_input(self, action: KeyAction, char: str, doc: Document) -> bool:
        return self._handle_paged_input(action, char, doc)

    def render(self, doc: Document, session: Session) -> RenderFrame:
        wrapped, cursor_line, cursor_col, row_map = wrap_lines(
            doc._lines, doc.cursor_line, doc.cursor_col,
            self._font_family, self._font_size, self._text_width_px,
        )
        self._wrapped_lines = wrapped
        self._row_map = row_map
        self._wrapped_len = len(wrapped)
        line_kinds = line_kinds_for_rows(doc._lines, row_map)

        avail_height_px = HEIGHT - 8 - 24
        page, total, visible, visible_kinds, start, adj_cursor, show_cursor = (
            self._paginate_by_height(
                wrapped, line_kinds, cursor_line, avail_height_px, self._font_size,
            )
        )

        stats = {"Words": str(doc.word_count), "Page": f"{page + 1}/{total}"}

        selection = (
            map_selection(doc.selection.ordered(), row_map, start)
            if doc.selection is not None else None
        )

        return RenderFrame(
            text_lines=visible,
            line_kinds=visible_kinds,
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

