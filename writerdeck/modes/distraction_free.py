"""Distraction-Free mode — full canvas text with a tiny word count footer."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import BaseMode, RenderFrame
from writerdeck.utils.text_wrapper import wrap_lines


class DistractionFreeMode(BaseMode):
    name = "distraction_free"

    def __init__(self, text_width_px: int = 784, font_family: str = "Hack", font_size: int = 14) -> None:
        super().__init__()
        self._text_width_px = text_width_px
        self._font_family = font_family
        self._font_size = font_size

    def handle_input(self, action: KeyAction, char: str, doc: Document) -> bool:
        return self._apply_common_input(action, char, doc)

    def render(self, doc: Document, session: Session) -> RenderFrame:
        wrapped, cursor_line, cursor_col = wrap_lines(
            doc.lines, doc.cursor_line, doc.cursor_col,
            self._font_family, self._font_size, self._text_width_px,
        )

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

        # Selection coordinates in wrapped space
        selection = _map_selection(doc, wrapped, cursor_line)

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


def _map_selection(doc: Document, wrapped: list[str], cursor_line: int) -> tuple[int, int, int, int] | None:
    """Map document selection to wrapped-line coordinates (stub — returns None for now)."""
    if doc.selection is None:
        return None
    # For simplicity, return the ordered selection coords directly
    # A full implementation would map through the wrap mapping
    return doc.selection.ordered()
