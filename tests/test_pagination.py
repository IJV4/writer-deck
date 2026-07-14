"""Tests for notebook-style pagination: page auto-advance, manual navigation, page stats."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.display.driver import HEIGHT
from writerdeck.input.keymapper import KeyAction, KeyMapper
from writerdeck.modes.dashboard import DashboardMode
from writerdeck.modes.distraction_free import DistractionFreeMode
from writerdeck.modes.typewriter import TypewriterMode

# Each mode uses font_size=14 → line_height=18.
# DistractionFreeMode: margin_top=8, margin_bottom=24 → visible = (480-32)//18 = 24
# DashboardMode: margin_top=8, margin_bottom=8 → visible = (480-16)//18 = 25
# These counts are what the tests are calibrated against.
_DF_VISIBLE = (HEIGHT - 8 - 24) // (14 + 4)   # 24
_DB_VISIBLE = (HEIGHT - 8 - 8) // (14 + 4)    # 25


def _doc_with_n_lines(n: int) -> Document:
    """Return a document with n empty lines (n-1 newlines)."""
    text = "\n" * (n - 1)
    return Document(text)


def _session() -> Session:
    return Session()


# ── Keymapper bindings ────────────────────────────────────────────────────────

class TestPageNavKeybindings:
    def test_ctrl_up_maps_to_page_prev(self):
        km = KeyMapper()
        km.process_event(29, 1)  # Ctrl press
        action, _ = km.process_event(103, 1)  # Up arrow
        assert action == KeyAction.PAGE_PREV

    def test_ctrl_down_maps_to_page_next(self):
        km = KeyMapper()
        km.process_event(29, 1)  # Ctrl press
        action, _ = km.process_event(108, 1)  # Down arrow
        assert action == KeyAction.PAGE_NEXT

    def test_ctrl_up_repeat_maps_to_page_prev(self):
        km = KeyMapper()
        km.process_event(29, 1)
        action, _ = km.process_event(103, 2)  # repeat
        assert action == KeyAction.PAGE_PREV

    def test_shift_up_still_select_up(self):
        """Shift+Up must remain SELECT_UP (text selection; not broken by pagination)."""
        km = KeyMapper()
        km.process_event(42, 1)  # Shift press
        action, _ = km.process_event(103, 1)  # Up arrow
        assert action == KeyAction.SELECT_UP

    def test_shift_down_still_select_down(self):
        km = KeyMapper()
        km.process_event(42, 1)
        action, _ = km.process_event(108, 1)
        assert action == KeyAction.SELECT_DOWN


# ── Auto-advance (cursor overflow) ───────────────────────────────────────────

class TestAutoPageAdvance:
    def test_cursor_on_page_0_renders_page_1_of_1(self):
        doc = _doc_with_n_lines(3)
        mode = DistractionFreeMode()
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "1/1"

    def test_cursor_past_first_page_advances_to_page_2(self):
        # Put cursor on the first line of page 2 (line index = _DF_VISIBLE)
        doc = _doc_with_n_lines(_DF_VISIBLE + 1)
        doc.cursor_line = _DF_VISIBLE
        doc.cursor_col = 0
        mode = DistractionFreeMode()
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "2/2"
        assert frame.cursor_line == 0   # cursor at top of new page
        assert frame.show_cursor is True

    def test_visible_slice_is_capped_at_visible_lines(self):
        doc = _doc_with_n_lines(_DF_VISIBLE + 5)
        doc.cursor_line = _DF_VISIBLE
        mode = DistractionFreeMode()
        frame = mode.render(doc, _session())
        assert len(frame.text_lines) <= _DF_VISIBLE

    def test_page_1_shows_first_page_content(self):
        """Cursor on page 0: only page 0 lines are visible."""
        doc = _doc_with_n_lines(_DF_VISIBLE + 1)
        doc.cursor_line = 0
        mode = DistractionFreeMode()
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "1/2"
        assert len(frame.text_lines) == _DF_VISIBLE


# ── Manual page navigation ────────────────────────────────────────────────────

class TestManualPageNav:
    def test_page_prev_shows_earlier_content(self):
        doc = _doc_with_n_lines(_DF_VISIBLE + 1)
        doc.cursor_line = _DF_VISIBLE
        mode = DistractionFreeMode()
        mode.render(doc, _session())  # renders page 2

        mode.handle_input(KeyAction.PAGE_PREV, "", doc)
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "1/2"

    def test_page_next_moves_forward(self):
        doc = _doc_with_n_lines(_DF_VISIBLE + 1)
        doc.cursor_line = 0  # cursor on page 1
        mode = DistractionFreeMode()
        mode.render(doc, _session())  # page 1

        mode.handle_input(KeyAction.PAGE_NEXT, "", doc)
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "2/2"

    def test_page_prev_at_first_page_stays(self):
        doc = _doc_with_n_lines(5)
        mode = DistractionFreeMode()
        mode.render(doc, _session())

        mode.handle_input(KeyAction.PAGE_PREV, "", doc)
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "1/1"

    def test_page_next_at_last_page_stays(self):
        doc = _doc_with_n_lines(_DF_VISIBLE + 1)
        doc.cursor_line = _DF_VISIBLE
        mode = DistractionFreeMode()
        mode.render(doc, _session())  # page 2

        mode.handle_input(KeyAction.PAGE_NEXT, "", doc)
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "2/2"

    def test_cursor_hidden_when_browsing_other_page(self):
        doc = _doc_with_n_lines(_DF_VISIBLE + 1)
        doc.cursor_line = _DF_VISIBLE  # cursor on page 2
        mode = DistractionFreeMode()
        mode.render(doc, _session())

        mode.handle_input(KeyAction.PAGE_PREV, "", doc)
        frame = mode.render(doc, _session())
        assert frame.show_cursor is False

    def test_editing_snaps_back_to_cursor_page(self):
        doc = _doc_with_n_lines(_DF_VISIBLE + 1)
        doc.cursor_line = _DF_VISIBLE  # cursor on page 2
        mode = DistractionFreeMode()
        mode.render(doc, _session())  # page 2

        mode.handle_input(KeyAction.PAGE_PREV, "", doc)  # browse to page 1
        mode.render(doc, _session())  # viewing page 1

        mode.handle_input(KeyAction.CHAR, "x", doc)  # type → snap back
        frame = mode.render(doc, _session())
        assert frame.show_cursor is True
        assert "2/" in frame.stats["Page"]  # back on page 2


# ── Dashboard mode pagination ─────────────────────────────────────────────────

class TestDashboardPagination:
    def test_page_stat_present(self):
        doc = _doc_with_n_lines(3)
        mode = DashboardMode()
        frame = mode.render(doc, _session())
        assert "Page" in frame.stats

    def test_dashboard_auto_advance(self):
        doc = _doc_with_n_lines(_DB_VISIBLE + 1)
        doc.cursor_line = _DB_VISIBLE
        mode = DashboardMode()
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "2/2"

    def test_dashboard_ctrl_up(self):
        doc = _doc_with_n_lines(_DB_VISIBLE + 1)
        doc.cursor_line = _DB_VISIBLE
        mode = DashboardMode()
        mode.render(doc, _session())
        mode.handle_input(KeyAction.PAGE_PREV, "", doc)
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "1/2"


# ── Physical PageUp/PageDown drive pagination in paged modes ──────────────────

class TestPagedKeyPageNav:
    """PageUp/PageDown must move the paged viewport and only refresh on change."""

    def test_page_down_advances_page_distraction_free(self):
        doc = _doc_with_n_lines(_DF_VISIBLE + 1)
        doc.cursor_line = 0  # cursor on page 1
        mode = DistractionFreeMode()
        mode.render(doc, _session())  # page 1, primes _visible_lines/_wrapped_len

        changed = mode.handle_input(KeyAction.PAGE_DOWN, "", doc)
        assert changed is True  # view moved → refresh warranted
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "2/2"
        assert frame.show_cursor is False  # browsing a non-cursor page

    def test_page_down_noop_at_last_page_returns_false(self):
        doc = _doc_with_n_lines(_DF_VISIBLE + 1)
        doc.cursor_line = _DF_VISIBLE  # cursor auto-advances to page 2
        mode = DistractionFreeMode()
        mode.render(doc, _session())  # page 2

        changed = mode.handle_input(KeyAction.PAGE_DOWN, "", doc)
        assert changed is False  # already at last page → no wasted refresh
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "2/2"

    def test_page_up_returns_to_earlier_page(self):
        doc = _doc_with_n_lines(_DF_VISIBLE + 1)
        doc.cursor_line = _DF_VISIBLE  # cursor on page 2
        mode = DistractionFreeMode()
        mode.render(doc, _session())  # page 2

        changed = mode.handle_input(KeyAction.PAGE_UP, "", doc)
        assert changed is True
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "1/2"

    def test_page_up_noop_at_first_page_returns_false(self):
        doc = _doc_with_n_lines(_DF_VISIBLE + 1)
        doc.cursor_line = 0  # cursor on page 1
        mode = DistractionFreeMode()
        mode.render(doc, _session())  # page 1

        changed = mode.handle_input(KeyAction.PAGE_UP, "", doc)
        assert changed is False
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "1/2"

    def test_page_down_advances_page_dashboard(self):
        doc = _doc_with_n_lines(_DB_VISIBLE + 1)
        doc.cursor_line = 0
        mode = DashboardMode()
        mode.render(doc, _session())

        changed = mode.handle_input(KeyAction.PAGE_DOWN, "", doc)
        assert changed is True
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "2/2"

    def test_page_down_single_page_is_noop(self):
        doc = _doc_with_n_lines(3)  # fits in one page
        mode = DistractionFreeMode()
        mode.render(doc, _session())

        changed = mode.handle_input(KeyAction.PAGE_DOWN, "", doc)
        assert changed is False
        frame = mode.render(doc, _session())
        assert frame.stats["Page"] == "1/1"


# ── Typewriter mode page stat ─────────────────────────────────────────────────

class TestTypewriterPageStat:
    def test_page_stat_present(self):
        doc = Document("hello world")
        mode = TypewriterMode()
        frame = mode.render(doc, _session())
        assert "Page" in frame.stats

    def test_page_stat_format(self):
        doc = Document("hello world")
        mode = TypewriterMode()
        frame = mode.render(doc, _session())
        page_stat = frame.stats["Page"]
        assert "/" in page_stat
        parts = page_stat.split("/")
        assert len(parts) == 2
        assert parts[0].isdigit()
        assert parts[1].isdigit()
