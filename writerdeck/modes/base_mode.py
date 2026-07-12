"""Base mode contract and RenderFrame dataclass."""

from __future__ import annotations

import bisect
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.input.keymapper import KeyAction


@dataclass
class RenderFrame:
    text_lines: list[str] = field(default_factory=list)
    cursor_line: int = 0
    cursor_col: int = 0
    show_cursor: bool = True
    stats: dict[str, str] | None = None
    stats_position: str = "footer"   # "footer" or "sidebar"
    sidebar_width: int = 220
    force_full_refresh: bool = False
    margin_top: int = 8
    margin_bottom: int = 24
    margin_left: int = 8
    margin_right: int = 8
    title: str = ""
    status_message: str | None = None
    selection: tuple[int, int, int, int] | None = None  # (sl, sc, el, ec) in wrapped coords


class BaseMode(ABC):
    name: str = "base"

    def __init__(self) -> None:
        self._scroll_offset: int = 0
        self._current_page: int = 0
        self._page_manual: bool = False
        # Set by render() so handle_input() can do visual-row Up/Down navigation.
        self._wrapped_lines: list[str] = []
        self._row_map: list[tuple[int, int]] = []  # [(doc_line_idx, char_start), ...]
        # Number of wrapped rows produced by the last render(); used to clamp
        # PAGE_DOWN so scrolling can't run off the end into a blank screen.
        self._wrapped_len: int = 0

    def on_enter(self) -> None:
        self._scroll_offset = 0
        self._current_page = 0
        self._page_manual = False

    def on_exit(self) -> None:
        pass

    @abstractmethod
    def handle_input(self, action: KeyAction, char: str, doc: Document) -> bool:
        """Process a key action. Return True if the document or view changed."""
        ...

    @abstractmethod
    def render(self, doc: Document, session: Session) -> RenderFrame:
        """Produce a RenderFrame for the current document state."""
        ...

    # -- Pagination --------------------------------------------------------

    def _paginate(
        self,
        wrapped: list[str],
        cursor_visual_row: int,
        visible_lines: int,
    ) -> tuple[int, int, list[str], int, bool]:
        """Compute page-based viewport.

        Returns (page, total_pages, visible_slice, adj_cursor_line, show_cursor).
        Tracks self._current_page and self._page_manual:
        - Editing actions reset _page_manual=False so the cursor is followed.
        - PAGE_PREV/PAGE_NEXT set _page_manual=True so the viewport stays put.
        """
        total = max(1, math.ceil(len(wrapped) / visible_lines))
        cursor_page = cursor_visual_row // visible_lines

        if self._page_manual and self._current_page != cursor_page:
            page = max(0, min(self._current_page, total - 1))
        else:
            page = cursor_page
            self._current_page = page
            self._page_manual = False

        visible = wrapped[page * visible_lines : (page + 1) * visible_lines]
        adj_cursor = cursor_visual_row - page * visible_lines
        show_cursor = 0 <= adj_cursor < len(visible)

        return page, total, visible, adj_cursor, show_cursor

    # -- Visual row navigation ---------------------------------------------

    def _find_visual_row(self, doc_line: int, doc_col: int) -> int:
        """Return the visual row index for the given document cursor position.

        When a doc line wraps to multiple visual rows, picks the row whose
        char_start is <= doc_col (the deepest match).
        """
        # _row_map is sorted by (doc_line, col_start). Find rightmost row
        # where (dl, start) <= (doc_line, doc_col).
        idx = bisect.bisect_right(self._row_map, (doc_line, doc_col))
        # bisect_right gives insertion point after all (doc_line, <= doc_col) entries.
        # Step back one to get the row whose start <= doc_col.
        return max(0, idx - 1)

    def _visual_move(self, doc: Document, delta: int, extend: bool) -> bool:
        """Move the cursor one visual row up (delta=-1) or down (delta=+1).

        Returns True if the action was handled (even if cursor didn't move
        because it's already at the first/last visual row).  Returns False
        only when no row_map is available yet (fallback to doc-level move).
        """
        if not self._row_map:
            return False

        vr = self._find_visual_row(doc.cursor_line, doc.cursor_col)
        # Column offset within the current visual row
        visual_col = doc.cursor_col - self._row_map[vr][1]

        target_vr = vr + delta
        if target_vr < 0 or target_vr >= len(self._row_map):
            # Already at the first or last visual row — consume the event so
            # _apply_common_input doesn't jump to the previous/next doc line.
            return True

        doc._start_or_extend_selection(extend)
        target_doc_line, target_start = self._row_map[target_vr]
        target_sub_len = len(self._wrapped_lines[target_vr])
        doc.cursor_line = target_doc_line
        doc.cursor_col = target_start + min(visual_col, target_sub_len)
        doc._update_selection_end()
        return True

    _UPDOWN_PARAMS: dict = {
        KeyAction.ARROW_UP:    (-1, False),
        KeyAction.ARROW_DOWN:  (+1, False),
        KeyAction.SELECT_UP:   (-1, True),
        KeyAction.SELECT_DOWN: (+1, True),
    }

    def _handle_visual_updown(
        self, action: KeyAction, char: str, doc: Document
    ) -> bool | None:
        """Intercept Up/Down/SelectUp/SelectDown for visual-row navigation.

        Returns True/False if the action was an Up/Down variant (handled or
        not).  Returns None if the action is something else (caller should
        continue to _apply_common_input).
        """
        if action not in self._UPDOWN_PARAMS:
            return None
        delta, extend = self._UPDOWN_PARAMS[action]
        result = self._visual_move(doc, delta, extend)
        if result:
            self._scroll_offset = 0
        return result

    # -- Standard key dispatch ---------------------------------------------

    def _apply_common_input(
        self, action: KeyAction, char: str, doc: Document
    ) -> bool:
        """Apply standard editing key actions. Returns True if handled."""
        # Any editing action resets scroll offset
        editing_action = True

        if action == KeyAction.CHAR:
            doc.insert(char)
        elif action == KeyAction.ENTER:
            doc.insert("\n")
        elif action == KeyAction.BACKSPACE:
            doc.delete_backward()
        elif action == KeyAction.DELETE:
            doc.delete_forward()
        elif action == KeyAction.ARROW_LEFT:
            doc.move_left()
        elif action == KeyAction.ARROW_RIGHT:
            doc.move_right()
        elif action == KeyAction.ARROW_UP:
            doc.move_up()
        elif action == KeyAction.ARROW_DOWN:
            doc.move_down()
        elif action == KeyAction.HOME:
            doc.move_home()
        elif action == KeyAction.END:
            doc.move_end()
        # Undo/Redo
        elif action == KeyAction.UNDO:
            doc.undo()
        elif action == KeyAction.REDO:
            doc.redo()
        # Word movement
        elif action == KeyAction.WORD_LEFT:
            doc.move_word_left()
        elif action == KeyAction.WORD_RIGHT:
            doc.move_word_right()
        elif action == KeyAction.DELETE_WORD_BACK:
            doc.delete_word_backward()
        # Selection
        elif action == KeyAction.SELECT_LEFT:
            doc.move_left(extend=True)
        elif action == KeyAction.SELECT_RIGHT:
            doc.move_right(extend=True)
        elif action == KeyAction.SELECT_UP:
            doc.move_up(extend=True)
        elif action == KeyAction.SELECT_DOWN:
            doc.move_down(extend=True)
        elif action == KeyAction.SELECT_WORD_LEFT:
            doc.move_word_left(extend=True)
        elif action == KeyAction.SELECT_WORD_RIGHT:
            doc.move_word_right(extend=True)
        elif action == KeyAction.SELECT_HOME:
            doc.move_home(extend=True)
        elif action == KeyAction.SELECT_END:
            doc.move_end(extend=True)
        elif action == KeyAction.SELECT_ALL:
            doc.select_all()
        # Page Up/Down
        elif action == KeyAction.PAGE_UP:
            self._scroll_offset = max(0, self._scroll_offset - 20)
            editing_action = False
        elif action == KeyAction.PAGE_DOWN:
            # Clamp against the last rendered wrapped length so scrolling can't
            # run past the end into a blank screen (BUG-3).
            max_offset = max(0, self._wrapped_len - 1)
            self._scroll_offset = min(self._scroll_offset + 20, max_offset)
            editing_action = False
        else:
            return False

        if editing_action:
            self._scroll_offset = 0
        return True
