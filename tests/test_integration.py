"""Integration tests — end-to-end flows with mocked hardware."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.input.keymapper import KeyAction, KeyMapper
from writerdeck.modes.dashboard import DashboardMode
from writerdeck.modes.distraction_free import DistractionFreeMode
from writerdeck.modes.file_picker import FilePickerOverlay
from writerdeck.modes.find_overlay import FindOverlay
from writerdeck.modes.font_picker import FontPickerOverlay
from writerdeck.modes.typewriter import TypewriterMode


class TestTypingAndUndo:
    def test_type_undo_redo(self):
        doc = Document()
        mode = DistractionFreeMode()
        session = Session()

        # Type "Hello"
        for ch in "Hello":
            mode.handle_input(KeyAction.CHAR, ch, doc)
        assert doc.text == "Hello"

        # Force different undo group
        doc._last_undo_time = 0

        # Type " World"
        for ch in " World":
            mode.handle_input(KeyAction.CHAR, ch, doc)
        assert doc.text == "Hello World"

        # Undo
        mode.handle_input(KeyAction.UNDO, "", doc)
        assert doc.text == "Hello"

        # Redo
        mode.handle_input(KeyAction.REDO, "", doc)
        assert doc.text == "Hello World"

    def test_word_delete(self):
        doc = Document("hello world")
        doc.cursor_line = 0
        doc.cursor_col = 11
        mode = DistractionFreeMode()

        mode.handle_input(KeyAction.DELETE_WORD_BACK, "", doc)
        assert doc.text == "hello "


class TestModeRendering:
    def test_distraction_free_renders(self):
        doc = Document("Hello world")
        session = Session()
        mode = DistractionFreeMode()
        frame = mode.render(doc, session)
        assert len(frame.text_lines) > 0
        assert frame.stats is not None
        assert "Words" in frame.stats

    def test_dashboard_renders(self):
        doc = Document("Hello world")
        session = Session()
        mode = DashboardMode()
        frame = mode.render(doc, session)
        assert frame.stats_position == "sidebar"
        assert "Session" in frame.stats

    def test_typewriter_renders(self):
        doc = Document("Hello world\n" * 50)
        session = Session()
        mode = TypewriterMode()
        frame = mode.render(doc, session)
        assert len(frame.text_lines) > 0


class TestSelection:
    def test_select_and_delete(self):
        doc = Document("Hello World")
        doc.cursor_line = 0
        doc.cursor_col = 5
        mode = DistractionFreeMode()

        # Select " World"
        for _ in range(6):
            mode.handle_input(KeyAction.SELECT_RIGHT, "", doc)
        assert doc.selection is not None

        # Delete selection
        mode.handle_input(KeyAction.BACKSPACE, "", doc)
        assert doc.text == "Hello"

    def test_type_replaces_selection(self):
        doc = Document("Hello")
        doc.cursor_line = 0
        doc.cursor_col = 0
        mode = DistractionFreeMode()

        mode.handle_input(KeyAction.SELECT_ALL, "", doc)
        mode.handle_input(KeyAction.CHAR, "X", doc)
        assert doc.text == "X"


class TestFontPicker:
    def test_navigate_and_select(self):
        overlay = FontPickerOverlay(["Hack", "DejaVuSansMono", "Courier"])
        assert overlay._selected == 0

        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        assert overlay._selected == 1

        result = overlay.handle_input(KeyAction.ENTER, "")
        assert result == {"font": "DejaVuSansMono"}

    def test_escape_cancels(self):
        overlay = FontPickerOverlay(["Hack"])
        result = overlay.handle_input(KeyAction.ESCAPE, "")
        assert result == {}


def _make_file_picker(docs: list[str]) -> FilePickerOverlay:
    entries = [(name, False) for name in docs]
    return FilePickerOverlay(
        list_entries=lambda subfolder="", sort_by_modified=False: entries,
        create_folder=lambda path: None,
        rename=lambda old, new: None,
        delete=lambda name: None,
    )


class TestFilePicker:
    def test_navigate_and_open(self):
        overlay = _make_file_picker(["doc-1", "doc-2", "doc-3"])
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        result = overlay.handle_input(KeyAction.ENTER, "")
        assert result == {"open_doc": "doc-3"}

    def test_empty_list(self):
        overlay = _make_file_picker([])
        result = overlay.handle_input(KeyAction.ENTER, "")
        assert result == {}  # empty list closes picker


class TestFindOverlay:
    def test_type_and_search(self):
        overlay = FindOverlay()

        for ch in "hello":
            overlay.handle_input(KeyAction.CHAR, ch)
        result = overlay.handle_input(KeyAction.ENTER, "")
        assert result == {"find": "hello"}

    def test_backspace(self):
        overlay = FindOverlay()
        overlay.handle_input(KeyAction.CHAR, "a")
        overlay.handle_input(KeyAction.CHAR, "b")
        overlay.handle_input(KeyAction.BACKSPACE, "")
        result = overlay.handle_input(KeyAction.ENTER, "")
        assert result == {"find": "a"}

    def test_tab_switches_to_replace(self):
        overlay = FindOverlay()
        for ch in "old":
            overlay.handle_input(KeyAction.CHAR, ch)
        # Tab to replace field
        overlay.handle_input(KeyAction.SWITCH_MODE_NEXT, "")
        for ch in "new":
            overlay.handle_input(KeyAction.CHAR, ch)
        result = overlay.handle_input(KeyAction.ENTER, "")
        assert result == {"find": "old", "replace": "new"}

    def test_escape(self):
        overlay = FindOverlay()
        result = overlay.handle_input(KeyAction.ESCAPE, "")
        assert result == {}


class TestKeymapper:
    def test_ctrl_z_undo(self):
        mapper = KeyMapper()
        # Press Ctrl
        mapper.process_event(29, 1)
        action, char = mapper.process_event(44, 1)  # Z
        assert action == KeyAction.UNDO

    def test_ctrl_shift_z_redo(self):
        mapper = KeyMapper()
        mapper.process_event(29, 1)   # Ctrl
        mapper.process_event(42, 1)   # Shift
        action, char = mapper.process_event(44, 1)  # Z
        assert action == KeyAction.REDO

    def test_shift_arrow_select(self):
        mapper = KeyMapper()
        mapper.process_event(42, 1)  # Shift
        action, char = mapper.process_event(106, 1)  # Right
        assert action == KeyAction.SELECT_RIGHT

    def test_ctrl_left_word(self):
        mapper = KeyMapper()
        mapper.process_event(29, 1)  # Ctrl
        action, char = mapper.process_event(105, 1)  # Left
        assert action == KeyAction.WORD_LEFT

    def test_page_up(self):
        mapper = KeyMapper()
        action, char = mapper.process_event(104, 1)
        assert action == KeyAction.PAGE_UP

    def test_escape(self):
        mapper = KeyMapper()
        action, char = mapper.process_event(1, 1)
        assert action == KeyAction.ESCAPE

    def test_ctrl_f_find(self):
        mapper = KeyMapper()
        mapper.process_event(29, 1)  # Ctrl
        action, char = mapper.process_event(33, 1)  # F
        assert action == KeyAction.FIND

    def test_ctrl_e_export(self):
        mapper = KeyMapper()
        mapper.process_event(29, 1)  # Ctrl
        action, char = mapper.process_event(18, 1)  # E
        assert action == KeyAction.EXPORT_USB
