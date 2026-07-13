"""Reading mode — read-only, paginated, larger-font document viewer."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.display.driver import HEIGHT
from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import BaseMode, RenderFrame
from writerdeck.utils.headings import line_kinds_for_rows
from writerdeck.utils.text_wrapper import wrap_lines


class ReadingMode(BaseMode):
    name = "reading"

    def __init__(
        self,
        font_family: str = "Hack",
        font_size: int = 14,
        font_size_delta: int = 4,
    ) -> None:
        super().__init__()
        self._font_family = font_family
        self._font_size = font_size + font_size_delta
        self._text_width_px = 784
        # Start from page 0; on_enter() will reset _page_manual to False for cursor-following
        self._page_manual = True

    def handle_input(self, action: KeyAction, char: str, doc: Document) -> bool:
        # Read-only: page/scroll navigation only, all editing actions ignored.
        if action in (KeyAction.PAGE_NEXT, KeyAction.ARROW_DOWN, KeyAction.ARROW_RIGHT):
            self._current_page += 1
            self._page_manual = True
            return True
        if action in (KeyAction.PAGE_PREV, KeyAction.ARROW_UP, KeyAction.ARROW_LEFT):
            self._current_page = max(0, self._current_page - 1)
            self._page_manual = True
            return True
        return False

    def render(self, doc: Document, session: Session) -> RenderFrame:
        wrapped, cursor_line, cursor_col, row_map = wrap_lines(
            doc._lines, doc.cursor_line, doc.cursor_col,
            self._font_family, self._font_size, self._text_width_px,
        )
        self._wrapped_lines = wrapped
        self._row_map = row_map
        self._wrapped_len = len(wrapped)
        line_kinds = line_kinds_for_rows(doc._lines, row_map)

        avail_height_px = HEIGHT - 8 - 8  # no footer stats bar in reading mode
        page, total, visible, visible_kinds, start, adj_cursor, show_cursor = (
            self._paginate_by_height(
                wrapped, line_kinds, cursor_line, avail_height_px, self._font_size,
            )
        )

        return RenderFrame(
            text_lines=visible,
            line_kinds=visible_kinds,
            cursor_line=-1,
            cursor_col=0,
            show_cursor=False,
            stats=None,
            force_full_refresh=True,
            margin_top=8,
            margin_bottom=8,
            margin_left=8,
            margin_right=8,
        )
