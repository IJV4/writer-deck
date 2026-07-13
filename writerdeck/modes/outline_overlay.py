"""Outline overlay — arrow-navigated list of document headings (Ctrl+H)."""

from __future__ import annotations

from typing import Any

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.modes.overlay import Overlay
from writerdeck.utils.headings import HEADING_PREFIX, classify_line


class OutlineOverlay(Overlay):
    def __init__(self, doc_lines: list[str]) -> None:
        self._headings: list[tuple[int, str, str]] = []  # (doc_line_idx, kind, text)
        for idx, line in enumerate(doc_lines):
            kind = classify_line(line)
            if kind == "body":
                continue
            prefix = HEADING_PREFIX[kind]
            stripped = line.lstrip()
            text = stripped[len(prefix):] if stripped.startswith(prefix) else stripped
            self._headings.append((idx, kind, text))
        self._selected = 0

    def handle_input(self, action: KeyAction, char: str) -> Any | None:
        if action == KeyAction.ESCAPE:
            return {}
        if not self._headings:
            if action == KeyAction.ENTER:
                return {}
            return None
        if action == KeyAction.ARROW_UP:
            self._selected = max(0, self._selected - 1)
            return None
        if action == KeyAction.ARROW_DOWN:
            self._selected = min(len(self._headings) - 1, self._selected + 1)
            return None
        if action == KeyAction.ENTER:
            doc_line_idx = self._headings[self._selected][0]
            return {"jump_to_line": doc_line_idx}
        return None

    def render(self, base_frame: RenderFrame) -> RenderFrame:
        lines = ["--- Outline (Up/Down, Enter, Esc) ---", ""]
        if not self._headings:
            lines.append("(no headings)")
        else:
            for i, (_, kind, text) in enumerate(self._headings):
                indent = "  " if kind == "h2" else ""
                prefix = "> " if i == self._selected else "  "
                lines.append(f"{prefix}{indent}{text}")

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
