"""File picker overlay — arrow-navigated list of documents."""

from __future__ import annotations

from typing import Any

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.modes.overlay import Overlay


class FilePickerOverlay(Overlay):
    def __init__(self, documents: list[str]) -> None:
        self._documents = documents if documents else ["(no documents)"]
        self._selected = 0

    def handle_input(self, action: KeyAction, char: str) -> Any | None:
        if action == KeyAction.ESCAPE:
            return {}  # cancelled
        if action == KeyAction.ARROW_UP:
            self._selected = max(0, self._selected - 1)
            return None
        if action == KeyAction.ARROW_DOWN:
            self._selected = min(len(self._documents) - 1, self._selected + 1)
            return None
        if action == KeyAction.ENTER:
            doc_name = self._documents[self._selected]
            if doc_name.startswith("("):
                return {}  # no actual doc
            return {"open_doc": doc_name}
        return None

    def render(self, base_frame: RenderFrame) -> RenderFrame:
        lines = ["--- Open Document (Up/Down, Enter, Esc) ---", ""]
        for i, doc in enumerate(self._documents):
            prefix = "> " if i == self._selected else "  "
            lines.append(f"{prefix}{doc}")
        lines.append("")
        lines.append("Press Enter to open, Escape to cancel")

        return RenderFrame(
            text_lines=lines,
            cursor_line=0,
            cursor_col=0,
            show_cursor=False,
            stats=None,
            force_full_refresh=True,
            margin_top=8,
            margin_bottom=8,
            margin_left=8,
        )
