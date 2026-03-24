"""Tests for overlay render() methods — font picker, file picker, find overlay."""

from __future__ import annotations

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.modes.font_picker import FontPickerOverlay
from writerdeck.modes.file_picker import FilePickerOverlay
from writerdeck.modes.find_overlay import FindOverlay


def _base_frame() -> RenderFrame:
    return RenderFrame(
        text_lines=["Line 1", "Line 2", "Line 3", "Line 4", "Line 5"],
        cursor_line=0,
        cursor_col=0,
        show_cursor=True,
        stats={"Words": "10"},
        stats_position="footer",
        title="Test Doc",
    )


class TestFontPickerRender:
    def test_renders_font_list(self):
        overlay = FontPickerOverlay(["Hack", "DejaVu", "Courier"])
        frame = overlay.render(_base_frame())
        # Should contain font names
        text = "\n".join(frame.text_lines)
        assert "Hack" in text
        assert "DejaVu" in text
        assert "Courier" in text

    def test_selected_item_has_prefix(self):
        overlay = FontPickerOverlay(["Hack", "DejaVu"])
        frame = overlay.render(_base_frame())
        # First item should have ">" prefix
        found = any("> Hack" in line for line in frame.text_lines)
        assert found

    def test_navigation_moves_prefix(self):
        overlay = FontPickerOverlay(["Hack", "DejaVu"])
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        frame = overlay.render(_base_frame())
        found = any("> DejaVu" in line for line in frame.text_lines)
        assert found

    def test_cursor_hidden(self):
        overlay = FontPickerOverlay(["Hack"])
        frame = overlay.render(_base_frame())
        assert frame.show_cursor is False

    def test_force_full_refresh(self):
        overlay = FontPickerOverlay(["Hack"])
        frame = overlay.render(_base_frame())
        assert frame.force_full_refresh is True

    def test_empty_fonts_shows_placeholder(self):
        overlay = FontPickerOverlay([])
        frame = overlay.render(_base_frame())
        text = "\n".join(frame.text_lines)
        assert "no fonts" in text.lower()

    def test_boundary_navigation(self):
        overlay = FontPickerOverlay(["A", "B", "C"])
        # Navigate past start
        overlay.handle_input(KeyAction.ARROW_UP, "")
        assert overlay._selected == 0
        # Navigate to end
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        overlay.handle_input(KeyAction.ARROW_DOWN, "")  # past end
        assert overlay._selected == 2


class TestFilePickerRender:
    def test_renders_document_list(self):
        overlay = FilePickerOverlay(["doc-1", "doc-2"])
        frame = overlay.render(_base_frame())
        text = "\n".join(frame.text_lines)
        assert "doc-1" in text
        assert "doc-2" in text

    def test_selected_item_has_prefix(self):
        overlay = FilePickerOverlay(["doc-1", "doc-2"])
        frame = overlay.render(_base_frame())
        found = any("> doc-1" in line for line in frame.text_lines)
        assert found

    def test_cursor_hidden(self):
        overlay = FilePickerOverlay(["doc-1"])
        frame = overlay.render(_base_frame())
        assert frame.show_cursor is False

    def test_force_full_refresh(self):
        overlay = FilePickerOverlay(["doc-1"])
        frame = overlay.render(_base_frame())
        assert frame.force_full_refresh is True

    def test_empty_list_shows_placeholder(self):
        overlay = FilePickerOverlay([])
        frame = overlay.render(_base_frame())
        text = "\n".join(frame.text_lines)
        assert "no documents" in text.lower()

    def test_boundary_navigation(self):
        overlay = FilePickerOverlay(["a", "b"])
        overlay.handle_input(KeyAction.ARROW_UP, "")  # past start
        assert overlay._selected == 0
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        overlay.handle_input(KeyAction.ARROW_DOWN, "")  # past end
        assert overlay._selected == 1

    def test_unhandled_action_returns_none(self):
        overlay = FilePickerOverlay(["a"])
        result = overlay.handle_input(KeyAction.CHAR, "x")
        assert result is None


class TestFindOverlayRender:
    def test_renders_search_prompt(self):
        overlay = FindOverlay()
        frame = overlay.render(_base_frame())
        text = "\n".join(frame.text_lines)
        assert "Find:" in text

    def test_renders_replace_prompt(self):
        overlay = FindOverlay()
        frame = overlay.render(_base_frame())
        text = "\n".join(frame.text_lines)
        assert "Replace:" in text

    def test_typed_text_appears_in_prompt(self):
        overlay = FindOverlay()
        for ch in "hello":
            overlay.handle_input(KeyAction.CHAR, ch)
        frame = overlay.render(_base_frame())
        text = "\n".join(frame.text_lines)
        assert "hello" in text

    def test_replace_text_appears(self):
        overlay = FindOverlay()
        for ch in "old":
            overlay.handle_input(KeyAction.CHAR, ch)
        overlay.handle_input(KeyAction.SWITCH_MODE_NEXT, "")  # Tab
        for ch in "new":
            overlay.handle_input(KeyAction.CHAR, ch)
        frame = overlay.render(_base_frame())
        text = "\n".join(frame.text_lines)
        assert "old" in text
        assert "new" in text

    def test_cursor_hidden(self):
        overlay = FindOverlay()
        frame = overlay.render(_base_frame())
        assert frame.show_cursor is False

    def test_force_full_refresh(self):
        overlay = FindOverlay()
        frame = overlay.render(_base_frame())
        assert frame.force_full_refresh is True

    def test_preserves_base_frame_stats(self):
        base = _base_frame()
        overlay = FindOverlay()
        frame = overlay.render(base)
        assert frame.stats == base.stats

    def test_preserves_base_frame_title(self):
        base = _base_frame()
        overlay = FindOverlay()
        frame = overlay.render(base)
        assert frame.title == base.title

    def test_active_field_indicator(self):
        overlay = FindOverlay()
        frame = overlay.render(_base_frame())
        # ">" should be on Find line when search field active
        find_lines = [l for l in frame.text_lines if "Find:" in l]
        assert any(l.startswith(">") for l in find_lines)

    def test_tab_switches_indicator(self):
        overlay = FindOverlay()
        overlay.handle_input(KeyAction.SWITCH_MODE_NEXT, "")
        frame = overlay.render(_base_frame())
        replace_lines = [l for l in frame.text_lines if "Replace:" in l]
        assert any(l.startswith(">") for l in replace_lines)

    def test_enter_with_empty_search_returns_none(self):
        overlay = FindOverlay()
        result = overlay.handle_input(KeyAction.ENTER, "")
        assert result is None  # Can't search empty

    def test_backspace_in_replace_field(self):
        overlay = FindOverlay()
        overlay.handle_input(KeyAction.SWITCH_MODE_NEXT, "")
        overlay.handle_input(KeyAction.CHAR, "a")
        overlay.handle_input(KeyAction.CHAR, "b")
        overlay.handle_input(KeyAction.BACKSPACE, "")
        # Switch back to search to submit
        overlay.handle_input(KeyAction.SWITCH_MODE_NEXT, "")
        for ch in "q":
            overlay.handle_input(KeyAction.CHAR, ch)
        result = overlay.handle_input(KeyAction.ENTER, "")
        # Replace field should have "a" (not "ab")
        # But we need to submit from replace field for replace result
        overlay2 = FindOverlay()
        for ch in "search":
            overlay2.handle_input(KeyAction.CHAR, ch)
        overlay2.handle_input(KeyAction.SWITCH_MODE_NEXT, "")
        overlay2.handle_input(KeyAction.CHAR, "x")
        overlay2.handle_input(KeyAction.CHAR, "y")
        overlay2.handle_input(KeyAction.BACKSPACE, "")
        result = overlay2.handle_input(KeyAction.ENTER, "")
        assert result == {"find": "search", "replace": "x"}
