"""Distraction-Free mode — full canvas text with a tiny word count footer."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import BaseMode, RenderFrame
from writerdeck.display.driver import HEIGHT
from writerdeck.utils.text_wrapper import map_selection, wrap_lines


class DistractionFreeMode(BaseMode):
    name = "distraction_free"

    def __init__(self, text_width_px: int = 784, font_family: str = "Hack", font_size: int = 14) -> None:
        super().__init__()
        self._text_width_px = text_width_px
        self._font_family = font_family
        self._font_size = font_size

    def handle_input(self, action: KeyAction, char: str, doc: Document) -> bool:
        if action == KeyAction.PAGE_PREV:
            self._current_page = max(0, self._current_page - 1)
            self._page_manual = True
            return True
        if action == KeyAction.PAGE_NEXT:
            self._current_page += 1
            self._page_manual = True
            return True
        self._page_manual = False
        result = self._handle_visual_updown(action, char, doc)
        if result is not None:
            return result
        return self._apply_common_input(action, char, doc)

    def render(self, doc: Document, session: Session) -> RenderFrame:
        wrapped, cursor_line, cursor_col, row_map = wrap_lines(
            doc._lines, doc.cursor_line, doc.cursor_col,
            self._font_family, self._font_size, self._text_width_px,
        )
        self._wrapped_lines = wrapped
        self._row_map = row_map
        self._wrapped_len = len(wrapped)

        line_height = self._font_size + 4
        visible_lines = (HEIGHT - 8 - 24) // line_height
        page, total, visible, adj_cursor, show_cursor = self._paginate(wrapped, cursor_line, visible_lines)
        scroll = page * visible_lines

        stats = {"Words": str(doc.word_count), "Page": f"{page + 1}/{total}"}

        selection = (
            map_selection(doc.selection.ordered(), row_map, scroll)
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

