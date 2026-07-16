"""Tests for overlay render() methods — font picker, file picker, find overlay."""

from __future__ import annotations

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.modes.file_picker import FilePickerOverlay
from writerdeck.modes.find_overlay import FindOverlay
from writerdeck.modes.font_picker import FontPickerOverlay


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
        overlay = FontPickerOverlay([("Hack", "Hack"), ("DejaVu", "DejaVu"), ("Courier", "Courier")])
        frame = overlay.render(_base_frame())
        # Should contain font names
        text = "\n".join(frame.text_lines)
        assert "Hack" in text
        assert "DejaVu" in text
        assert "Courier" in text

    def test_selected_item_has_prefix(self):
        # The ">" marker is drawn via line_prefixes (kept out of text_lines
        # so a per-row font override can't shift its alignment).
        overlay = FontPickerOverlay([("Hack", "Hack"), ("DejaVu", "DejaVu")])
        frame = overlay.render(_base_frame())
        hack_idx = frame.text_lines.index("Hack")
        assert frame.line_prefixes is not None
        assert frame.line_prefixes[hack_idx] == "> "

    def test_navigation_moves_prefix(self):
        overlay = FontPickerOverlay([("Hack", "Hack"), ("DejaVu", "DejaVu")])
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        frame = overlay.render(_base_frame())
        dejavu_idx = frame.text_lines.index("DejaVu")
        assert frame.line_prefixes is not None
        assert frame.line_prefixes[dejavu_idx] == "> "

    def test_cursor_hidden(self):
        overlay = FontPickerOverlay([("Hack", "Hack")])
        frame = overlay.render(_base_frame())
        assert frame.show_cursor is False

    def test_navigation_does_not_force_full_refresh(self):
        # app.py's open/close action handlers already force a full refresh
        # for the "page flip"; in-list navigation frames must not also force
        # one, or every arrow keypress blinks the whole panel.
        overlay = FontPickerOverlay([("Hack", "Hack")])
        frame = overlay.render(_base_frame())
        assert frame.force_full_refresh is False

    def test_empty_fonts_shows_placeholder(self):
        overlay = FontPickerOverlay([])
        frame = overlay.render(_base_frame())
        text = "\n".join(frame.text_lines)
        assert "no fonts" in text.lower()

    def test_boundary_navigation(self):
        overlay = FontPickerOverlay([("A", "A"), ("B", "B"), ("C", "C")])
        # Navigate past start
        overlay.handle_input(KeyAction.ARROW_UP, "")
        assert overlay._selected == 0
        # Navigate to end
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        overlay.handle_input(KeyAction.ARROW_DOWN, "")  # past end
        assert overlay._selected == 2

    def test_each_font_line_rendered_in_its_own_typeface(self):
        # Each entry's row is drawn using that font's own family, not the
        # frame's default, so its shape is visible directly in the list.
        overlay = FontPickerOverlay([("Hack", "Hack — Monospace"), ("DejaVuSerif", "DejaVuSerif — Serif")])
        frame = overlay.render(_base_frame())
        assert frame.line_fonts is not None
        assert len(frame.line_fonts) == len(frame.text_lines)
        font_line_idx = next(
            i for i, line in enumerate(frame.text_lines) if "DejaVuSerif" in line
        )
        assert frame.line_fonts[font_line_idx] == "DejaVuSerif"
        # Header/footer lines have no font override.
        assert frame.line_fonts[0] is None
        assert frame.line_fonts[-1] is None


def _make_file_picker(docs: list[str]) -> FilePickerOverlay:
    """Build a FilePickerOverlay with stub callbacks and a static doc list."""
    entries = [(name, False) for name in docs]
    return FilePickerOverlay(
        list_entries=lambda subfolder="", sort_by_modified=False: entries,
        create_folder=lambda path: None,
        rename=lambda old, new: None,
        delete=lambda name: None,
    )


class TestFilePickerRender:
    def test_renders_document_list(self):
        overlay = _make_file_picker(["doc-1", "doc-2"])
        frame = overlay.render(_base_frame())
        text = "\n".join(frame.text_lines)
        assert "doc-1" in text
        assert "doc-2" in text

    def test_selected_item_has_prefix(self):
        overlay = _make_file_picker(["doc-1", "doc-2"])
        frame = overlay.render(_base_frame())
        found = any("> doc-1" in line for line in frame.text_lines)
        assert found

    def test_cursor_hidden(self):
        overlay = _make_file_picker(["doc-1"])
        frame = overlay.render(_base_frame())
        assert frame.show_cursor is False

    def test_force_full_refresh(self):
        overlay = _make_file_picker(["doc-1"])
        frame = overlay.render(_base_frame())
        assert frame.force_full_refresh is True

    def test_empty_list_shows_placeholder(self):
        overlay = _make_file_picker([])
        frame = overlay.render(_base_frame())
        text = "\n".join(frame.text_lines)
        assert "empty" in text.lower()

    def test_boundary_navigation(self):
        overlay = _make_file_picker(["a", "b"])
        overlay.handle_input(KeyAction.ARROW_UP, "")  # past start
        assert overlay._selected == 0
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        overlay.handle_input(KeyAction.ARROW_DOWN, "")  # past end
        assert overlay._selected == 1

    def test_unhandled_action_returns_none(self):
        overlay = _make_file_picker(["a"])
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

    def test_plain_tab_switches_focus(self):
        """Plain Tab (evdev/pygame) switches Find/Replace focus, like Ctrl+Tab."""
        overlay = FindOverlay()
        assert overlay._in_replace_field is False
        overlay.handle_input(KeyAction.TAB, "")
        assert overlay._in_replace_field is True
        overlay.handle_input(KeyAction.TAB, "")
        assert overlay._in_replace_field is False

    def test_plain_tab_switches_indicator(self):
        overlay = FindOverlay()
        overlay.handle_input(KeyAction.TAB, "")
        frame = overlay.render(_base_frame())
        replace_lines = [l for l in frame.text_lines if "Replace:" in l]
        assert any(l.startswith(">") for l in replace_lines)

    def test_plain_tab_routes_typed_text_to_replace(self):
        overlay = FindOverlay()
        for ch in "old":
            overlay.handle_input(KeyAction.CHAR, ch)
        overlay.handle_input(KeyAction.TAB, "")  # switch to replace via plain Tab
        for ch in "new":
            overlay.handle_input(KeyAction.CHAR, ch)
        result = overlay.handle_input(KeyAction.ENTER, "")
        assert result == {"find": "old", "replace": "new"}

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
