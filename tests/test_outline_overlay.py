"""Tests for OutlineOverlay — heading navigation."""

from __future__ import annotations

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.modes.outline_overlay import OutlineOverlay


def _base_frame() -> RenderFrame:
    return RenderFrame(text_lines=["a", "b"], cursor_line=0, cursor_col=0)


class TestOutlineOverlayExtraction:
    def test_extracts_headings_with_line_indices(self):
        doc_lines = ["intro", "# Chapter One", "body", "## Section A", "more body"]
        overlay = OutlineOverlay(doc_lines)
        text = "\n".join(overlay.render(_base_frame()).text_lines)
        assert "Chapter One" in text
        assert "Section A" in text
        assert "#" not in text.replace("--- Outline", "")  # markers stripped

    def test_no_headings_shows_placeholder(self):
        overlay = OutlineOverlay(["plain", "text", "only"])
        text = "\n".join(overlay.render(_base_frame()).text_lines)
        assert "(no headings)" in text


class TestOutlineOverlayNavigation:
    def test_arrow_down_moves_selection(self):
        overlay = OutlineOverlay(["# One", "# Two", "# Three"])
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        frame = overlay.render(_base_frame())
        selected_line = next(l for l in frame.text_lines if l.startswith(">"))
        assert "Two" in selected_line

    def test_arrow_up_at_top_stays_at_top(self):
        overlay = OutlineOverlay(["# One", "# Two"])
        overlay.handle_input(KeyAction.ARROW_UP, "")
        frame = overlay.render(_base_frame())
        selected_line = next(l for l in frame.text_lines if l.startswith(">"))
        assert "One" in selected_line

    def test_arrow_down_at_bottom_stays_at_bottom(self):
        overlay = OutlineOverlay(["# One", "# Two"])
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        frame = overlay.render(_base_frame())
        selected_line = next(l for l in frame.text_lines if l.startswith(">"))
        assert "Two" in selected_line

    def test_enter_returns_jump_to_line_of_selected_heading(self):
        overlay = OutlineOverlay(["intro", "# One", "body", "# Two"])
        overlay.handle_input(KeyAction.ARROW_DOWN, "")  # select "Two" (doc line 3)
        result = overlay.handle_input(KeyAction.ENTER, "")
        assert result == {"jump_to_line": 3}

    def test_enter_with_no_headings_cancels(self):
        overlay = OutlineOverlay(["plain text"])
        result = overlay.handle_input(KeyAction.ENTER, "")
        assert result == {}

    def test_escape_cancels(self):
        overlay = OutlineOverlay(["# One"])
        result = overlay.handle_input(KeyAction.ESCAPE, "")
        assert result == {}
