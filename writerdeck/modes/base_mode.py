"""Base mode contract and RenderFrame dataclass."""

from __future__ import annotations

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

    def on_enter(self) -> None:
        self._scroll_offset = 0

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
            self._scroll_offset += 20
            editing_action = False
        else:
            return False

        if editing_action:
            self._scroll_offset = 0
        return True
