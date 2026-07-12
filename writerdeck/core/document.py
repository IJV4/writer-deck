"""Text buffer and cursor model for a single document."""

from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass


@dataclass
class Selection:
    start_line: int
    start_col: int
    end_line: int
    end_col: int

    def ordered(self) -> tuple[int, int, int, int]:
        """Return (start_line, start_col, end_line, end_col) in document order."""
        if (self.start_line, self.start_col) <= (self.end_line, self.end_col):
            return self.start_line, self.start_col, self.end_line, self.end_col
        return self.end_line, self.end_col, self.start_line, self.start_col


@dataclass
class _Snapshot:
    lines: list[str]
    cursor_line: int
    cursor_col: int


class Document:
    def __init__(self, text: str = "", name: str = "Untitled") -> None:
        self._lines: list[str] = text.split("\n") if text else [""]
        self.name = name
        self.cursor_line: int = len(self._lines) - 1
        self.cursor_col: int = len(self._lines[-1])
        self.dirty: bool = False
        self.selection: Selection | None = None

        # Undo/redo
        self._undo_stack: deque[_Snapshot] = deque(maxlen=100)
        self._redo_stack: deque[_Snapshot] = deque(maxlen=100)
        self._last_undo_time: float = 0.0
        self._last_undo_action: str = ""

        # Word count cache
        self._cached_word_count: int = 0
        self._word_count_dirty: bool = True

    # -- Text access -------------------------------------------------------

    @property
    def text(self) -> str:
        return "\n".join(self._lines)

    @property
    def lines(self) -> list[str]:
        return list(self._lines)

    @property
    def current_line(self) -> str:
        return self._lines[self.cursor_line]

    @property
    def line_count(self) -> int:
        return len(self._lines)

    @property
    def word_count(self) -> int:
        if self._word_count_dirty:
            self._cached_word_count = len(re.findall(r"\S+", self.text))
            self._word_count_dirty = False
        return self._cached_word_count

    def _invalidate_word_count(self) -> None:
        self._word_count_dirty = True

    @property
    def char_count(self) -> int:
        return len(self.text)

    # -- Undo/Redo ---------------------------------------------------------

    def _push_undo(self, action: str = "") -> None:
        """Push current state onto undo stack. Coalesces if <1s and same action."""
        now = time.monotonic()
        if (
            action
            and action == self._last_undo_action
            and now - self._last_undo_time < 1.0
            and self._undo_stack
        ):
            return  # Coalesce
        snap = _Snapshot(
            lines=list(self._lines),
            cursor_line=self.cursor_line,
            cursor_col=self.cursor_col,
        )
        self._undo_stack.append(snap)
        self._redo_stack.clear()
        self._last_undo_time = now
        self._last_undo_action = action

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._invalidate_word_count()
        # Save current state for redo
        self._redo_stack.append(_Snapshot(
            lines=list(self._lines),
            cursor_line=self.cursor_line,
            cursor_col=self.cursor_col,
        ))
        snap = self._undo_stack.pop()
        self._lines = snap.lines
        self.cursor_line = snap.cursor_line
        self.cursor_col = snap.cursor_col
        self.selection = None
        self.dirty = True
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._invalidate_word_count()
        # Save current state for undo (no coalesce)
        self._undo_stack.append(_Snapshot(
            lines=list(self._lines),
            cursor_line=self.cursor_line,
            cursor_col=self.cursor_col,
        ))
        snap = self._redo_stack.pop()
        self._lines = snap.lines
        self.cursor_line = snap.cursor_line
        self.cursor_col = snap.cursor_col
        self.selection = None
        self.dirty = True
        return True

    # -- Selection ---------------------------------------------------------

    def _start_or_extend_selection(self, extend: bool) -> None:
        """If extend is True, start or extend selection from current cursor pos."""
        if extend:
            if self.selection is None:
                self.selection = Selection(
                    self.cursor_line, self.cursor_col,
                    self.cursor_line, self.cursor_col,
                )
        else:
            self.selection = None

    def _update_selection_end(self) -> None:
        """Update the selection endpoint to current cursor position."""
        if self.selection is not None:
            self.selection.end_line = self.cursor_line
            self.selection.end_col = self.cursor_col

    def select_all(self) -> None:
        self.selection = Selection(
            0, 0,
            len(self._lines) - 1, len(self._lines[-1]),
        )
        self.cursor_line = len(self._lines) - 1
        self.cursor_col = len(self._lines[-1])

    def clear_selection(self) -> None:
        self.selection = None

    def get_selected_text(self) -> str:
        if self.selection is None:
            return ""
        sl, sc, el, ec = self.selection.ordered()
        if sl == el:
            return self._lines[sl][sc:ec]
        parts = [self._lines[sl][sc:]]
        for i in range(sl + 1, el):
            parts.append(self._lines[i])
        parts.append(self._lines[el][:ec])
        return "\n".join(parts)

    def delete_selection(self) -> bool:
        if self.selection is None:
            return False
        self._invalidate_word_count()
        self._push_undo("delete_selection")
        sl, sc, el, ec = self.selection.ordered()
        if sl == el:
            line = self._lines[sl]
            self._lines[sl] = line[:sc] + line[ec:]
        else:
            before = self._lines[sl][:sc]
            after = self._lines[el][ec:]
            self._lines[sl] = before + after
            del self._lines[sl + 1 : el + 1]
        self.cursor_line = sl
        self.cursor_col = sc
        self.selection = None
        self.dirty = True
        return True

    # -- Mutations ---------------------------------------------------------

    def insert(self, char: str) -> None:
        if self.selection is not None:
            self.delete_selection()
        self._invalidate_word_count()
        self._push_undo("insert")
        if char == "\n":
            self._insert_newline()
        else:
            line = self._lines[self.cursor_line]
            self._lines[self.cursor_line] = (
                line[: self.cursor_col] + char + line[self.cursor_col :]
            )
            self.cursor_col += len(char)
        self.dirty = True

    def _insert_newline(self) -> None:
        line = self._lines[self.cursor_line]
        before = line[: self.cursor_col]
        after = line[self.cursor_col :]
        self._lines[self.cursor_line] = before
        self._lines.insert(self.cursor_line + 1, after)
        self.cursor_line += 1
        self.cursor_col = 0

    def delete_backward(self) -> None:
        if self.selection is not None:
            self.delete_selection()
            return
        self._invalidate_word_count()
        self._push_undo("delete_backward")
        if self.cursor_col > 0:
            line = self._lines[self.cursor_line]
            self._lines[self.cursor_line] = (
                line[: self.cursor_col - 1] + line[self.cursor_col :]
            )
            self.cursor_col -= 1
            self.dirty = True
        elif self.cursor_line > 0:
            prev_line = self._lines[self.cursor_line - 1]
            cur_line = self._lines.pop(self.cursor_line)
            self.cursor_line -= 1
            self.cursor_col = len(prev_line)
            self._lines[self.cursor_line] = prev_line + cur_line
            self.dirty = True

    def delete_forward(self) -> None:
        if self.selection is not None:
            self.delete_selection()
            return
        self._invalidate_word_count()
        self._push_undo("delete_forward")
        line = self._lines[self.cursor_line]
        if self.cursor_col < len(line):
            self._lines[self.cursor_line] = (
                line[: self.cursor_col] + line[self.cursor_col + 1 :]
            )
            self.dirty = True
        elif self.cursor_line < len(self._lines) - 1:
            next_line = self._lines.pop(self.cursor_line + 1)
            self._lines[self.cursor_line] = line + next_line
            self.dirty = True

    # -- Word-level operations ---------------------------------------------

    def move_word_left(self, extend: bool = False) -> None:
        self._start_or_extend_selection(extend)
        if self.cursor_col == 0 and self.cursor_line > 0:
            self.cursor_line -= 1
            self.cursor_col = len(self._lines[self.cursor_line])
        line = self._lines[self.cursor_line]
        col = self.cursor_col
        # Skip whitespace backwards
        while col > 0 and not line[col - 1].isalnum():
            col -= 1
        # Skip word chars backwards
        while col > 0 and line[col - 1].isalnum():
            col -= 1
        self.cursor_col = col
        self._update_selection_end()

    def move_word_right(self, extend: bool = False) -> None:
        self._start_or_extend_selection(extend)
        line = self._lines[self.cursor_line]
        col = self.cursor_col
        length = len(line)
        if col >= length and self.cursor_line < len(self._lines) - 1:
            self.cursor_line += 1
            self.cursor_col = 0
            self._update_selection_end()
            return
        # Skip word chars forward
        while col < length and line[col].isalnum():
            col += 1
        # Skip whitespace forward
        while col < length and not line[col].isalnum():
            col += 1
        self.cursor_col = col
        self._update_selection_end()

    def delete_word_backward(self) -> None:
        if self.selection is not None:
            self.delete_selection()
            return
        self._invalidate_word_count()
        self._push_undo("delete_word_backward")
        line = self._lines[self.cursor_line]
        col = self.cursor_col
        if col == 0 and self.cursor_line > 0:
            # Join with previous line
            self.delete_backward()
            return
        start = col
        # Skip whitespace backwards
        while start > 0 and not line[start - 1].isalnum():
            start -= 1
        # Skip word chars backwards
        while start > 0 and line[start - 1].isalnum():
            start -= 1
        self._lines[self.cursor_line] = line[:start] + line[col:]
        self.cursor_col = start
        self.dirty = True

    # -- Find/Replace ------------------------------------------------------

    def find_next(
        self, query: str, from_line: int, from_col: int
    ) -> tuple[int, int] | None:
        """Find next occurrence of query starting from (from_line, from_col)."""
        if not query:
            return None
        for i in range(len(self._lines)):
            line_idx = (from_line + i) % len(self._lines)
            line = self._lines[line_idx]
            start_col = from_col if i == 0 else 0
            pos = line.find(query, start_col)
            if pos >= 0:
                return (line_idx, pos)
        return None

    def replace_at(self, line: int, col: int, old: str, new: str) -> bool:
        """Replace old with new at the given position.

        Returns True if the text at (line, col) matched ``old`` and was
        replaced. Only pushes an undo snapshot / sets ``dirty`` when it
        actually edits, so a no-op replace leaves the undo stack untouched.
        """
        text = self._lines[line]
        if text[col : col + len(old)] != old:
            return False
        self._invalidate_word_count()
        self._push_undo("replace")
        self._lines[line] = text[:col] + new + text[col + len(old) :]
        self.dirty = True
        return True

    # -- Cursor movement ---------------------------------------------------

    def move_left(self, extend: bool = False) -> None:
        self._start_or_extend_selection(extend)
        if self.cursor_col > 0:
            self.cursor_col -= 1
        elif self.cursor_line > 0:
            self.cursor_line -= 1
            self.cursor_col = len(self._lines[self.cursor_line])
        self._update_selection_end()

    def move_right(self, extend: bool = False) -> None:
        self._start_or_extend_selection(extend)
        line = self._lines[self.cursor_line]
        if self.cursor_col < len(line):
            self.cursor_col += 1
        elif self.cursor_line < len(self._lines) - 1:
            self.cursor_line += 1
            self.cursor_col = 0
        self._update_selection_end()

    def move_up(self, extend: bool = False) -> None:
        self._start_or_extend_selection(extend)
        if self.cursor_line > 0:
            self.cursor_line -= 1
            self.cursor_col = min(self.cursor_col, len(self._lines[self.cursor_line]))
        self._update_selection_end()

    def move_down(self, extend: bool = False) -> None:
        self._start_or_extend_selection(extend)
        if self.cursor_line < len(self._lines) - 1:
            self.cursor_line += 1
            self.cursor_col = min(self.cursor_col, len(self._lines[self.cursor_line]))
        self._update_selection_end()

    def move_home(self, extend: bool = False) -> None:
        self._start_or_extend_selection(extend)
        self.cursor_col = 0
        self._update_selection_end()

    def move_end(self, extend: bool = False) -> None:
        self._start_or_extend_selection(extend)
        self.cursor_col = len(self._lines[self.cursor_line])
        self._update_selection_end()

    # -- Bulk operations ---------------------------------------------------

    def load(self, text: str, name: str | None = None) -> None:
        self._lines = text.split("\n") if text else [""]
        if name is not None:
            self.name = name
        self.cursor_line = 0
        self.cursor_col = 0
        self.dirty = False
        self.selection = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._invalidate_word_count()

    def mark_saved(self) -> None:
        self.dirty = False
