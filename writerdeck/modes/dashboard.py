"""Dashboard mode — text area with a stats sidebar."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import BaseMode, RenderFrame
from writerdeck.utils.text_wrapper import wrap_lines

_SIDEBAR_WIDTH = 220
_TEXT_WIDTH_PX = 800 - _SIDEBAR_WIDTH - 16  # 564 usable


class DashboardMode(BaseMode):
    name = "dashboard"

    def __init__(self, font_family: str = "Hack", font_size: int = 14) -> None:
        super().__init__()
        self._font_family = font_family
        self._font_size = font_size

    def handle_input(self, action: KeyAction, char: str, doc: Document) -> bool:
        return self._apply_common_input(action, char, doc)

    def render(self, doc: Document, session: Session) -> RenderFrame:
        wrapped, cursor_line, cursor_col = wrap_lines(
            doc.lines, doc.cursor_line, doc.cursor_col,
            self._font_family, self._font_size, _TEXT_WIDTH_PX,
        )

        # Apply scroll offset
        visible = wrapped
        show_cursor = True
        adj_cursor = cursor_line
        if self._scroll_offset > 0:
            visible = wrapped[self._scroll_offset:]
            adj_cursor = cursor_line - self._scroll_offset
            if adj_cursor < 0 or adj_cursor >= len(visible):
                show_cursor = False

        stats = {
            "Words": str(doc.word_count),
            "Session": session.elapsed_display,
            "Written": str(session.words_written(doc.word_count)),
            "Goal": session.goal_bar(doc.word_count),
        }

        selection = None
        if doc.selection is not None:
            selection = doc.selection.ordered()

        return RenderFrame(
            text_lines=visible,
            cursor_line=adj_cursor,
            cursor_col=cursor_col,
            show_cursor=show_cursor,
            stats=stats,
            stats_position="sidebar",
            sidebar_width=_SIDEBAR_WIDTH,
            margin_top=8,
            margin_bottom=8,
            margin_left=8,
            margin_right=_SIDEBAR_WIDTH + 8,
            selection=selection,
        )
