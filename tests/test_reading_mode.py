"""Tests for ReadingMode — read-only paginated viewer."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.reading import ReadingMode


class TestReadingModeReadOnly:
    def test_char_input_is_rejected(self):
        doc = Document("hello")
        mode = ReadingMode()
        changed = mode.handle_input(KeyAction.CHAR, "x", doc)
        assert changed is False
        assert doc.text == "hello"

    def test_backspace_is_rejected(self):
        doc = Document("hello")
        mode = ReadingMode()
        changed = mode.handle_input(KeyAction.BACKSPACE, "", doc)
        assert changed is False
        assert doc.text == "hello"

    def test_enter_is_rejected(self):
        doc = Document("hello")
        mode = ReadingMode()
        changed = mode.handle_input(KeyAction.ENTER, "", doc)
        assert changed is False
        assert doc.text == "hello"


class TestReadingModePagination:
    def test_page_next_advances_and_forces_full_refresh(self):
        doc = Document("\n".join(f"line {i}" for i in range(200)))
        mode = ReadingMode()
        first = mode.render(doc, Session())
        assert first.force_full_refresh is True
        mode.handle_input(KeyAction.PAGE_NEXT, "", doc)
        second = mode.render(doc, Session())
        assert second.text_lines != first.text_lines

    def test_page_prev_does_not_go_below_zero(self):
        doc = Document("line one")
        mode = ReadingMode()
        mode.render(doc, Session())
        mode.handle_input(KeyAction.PAGE_PREV, "", doc)
        frame = mode.render(doc, Session())
        assert len(frame.text_lines) > 0

    def test_arrow_down_pages_forward(self):
        doc = Document("\n".join(f"line {i}" for i in range(200)))
        mode = ReadingMode()
        first = mode.render(doc, Session())
        mode.handle_input(KeyAction.ARROW_DOWN, "", doc)
        second = mode.render(doc, Session())
        assert second.text_lines != first.text_lines


class TestReadingModeLayout:
    def test_no_cursor_drawn(self):
        doc = Document("hello world")
        mode = ReadingMode()
        frame = mode.render(doc, Session())
        assert frame.show_cursor is False

    def test_no_footer_stats(self):
        doc = Document("hello")
        mode = ReadingMode()
        frame = mode.render(doc, Session())
        assert frame.stats is None

    def test_opens_on_page_containing_cursor(self):
        doc = Document("\n".join(f"line {i}" for i in range(200)))
        doc.cursor_line = 150
        doc.cursor_col = 0
        mode = ReadingMode()
        mode.on_enter()
        frame = mode.render(doc, Session())
        # The cursor's line should be among the words rendered on this page.
        assert any("line 150" in l for l in frame.text_lines)

    def test_line_kinds_present_for_headings(self):
        doc = Document("# Title\nbody text")
        mode = ReadingMode()
        frame = mode.render(doc, Session())
        assert frame.line_kinds is not None
        assert frame.line_kinds[0] == "h1"
