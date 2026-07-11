"""Tests for wrapped-space selection mapping (BUG-2) and PAGE_DOWN clamp (BUG-3).

These exercise the shared helpers in BaseMode and their use by the three
writing modes.
"""

from __future__ import annotations

from writerdeck.core.document import Document, Selection
from writerdeck.core.session import Session
from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.dashboard import DashboardMode
from writerdeck.modes.distraction_free import DistractionFreeMode
from writerdeck.modes.typewriter import TypewriterMode
from writerdeck.utils.text_wrapper import wrap_lines

# A single document line long enough to wrap to 4 visual rows at width 784.
# Sub-line char-start offsets depend on font metrics (Hack rendering can vary
# slightly by platform/font build), so tests derive them from wrap_lines
# directly instead of hardcoding — see _row_starts().
_LONG_LINE = ("word " * 60).strip()


def _row_starts() -> list[int]:
    """Actual visual-row char-start offsets for _LONG_LINE at DistractionFreeMode's width."""
    _, _, _, row_map = wrap_lines([_LONG_LINE], 0, 0, "Hack", 14, 784)
    starts = [start for _, start in row_map]
    assert len(starts) >= 4, "test line must wrap to at least 4 visual rows"
    return starts


class TestSelectionWrappedMapping:
    """BUG-2 — selection endpoints are mapped to wrapped/scrolled coords."""

    def test_selection_on_wrapped_line_lands_on_visual_row(self):
        # Select a span entirely inside the second visual row.
        starts = _row_starts()
        col_start, col_end = starts[1] + 5, starts[1] + 15
        doc = Document(_LONG_LINE)
        doc.selection = None
        doc.cursor_line = 0
        doc.cursor_col = col_start
        doc.selection = Selection(0, col_start, 0, col_end)

        mode = DistractionFreeMode()
        frame = mode.render(doc, Session())

        assert frame.selection is not None
        sl, sc, el, ec = frame.selection
        # Visual row 1 (second wrapped row), columns relative to that row's start.
        assert sl == 1
        assert el == 1
        assert sc == col_start - starts[1]
        assert ec == col_end - starts[1]

    def test_selection_spanning_two_visual_rows(self):
        starts = _row_starts()
        col_start, col_end = starts[0] + 5, starts[2] + 10
        doc = Document(_LONG_LINE)
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.selection = Selection(0, col_start, 0, col_end)

        mode = DistractionFreeMode()
        frame = mode.render(doc, Session())

        assert frame.selection is not None
        sl, sc, el, ec = frame.selection
        # col_start is on row 0; col_end is on row 2 (start starts[2]).
        assert sl == 0
        assert sc == col_start
        assert el == 2
        assert ec == col_end - starts[2]

    def test_selection_subtracts_scroll_offset(self):
        # DistractionFreeMode/DashboardMode scroll via page-based pagination
        # (_paginate), not the legacy _scroll_offset field — build a document
        # long enough to span multiple pages, move to page 2 with PAGE_NEXT
        # (Ctrl+Down, which sets _page_manual so the viewport stays put), and
        # put the selection on a row within that second page.
        doc = Document("\n".join(f"line {i}" for i in range(200)))
        doc.cursor_line = 0
        doc.cursor_col = 0
        mode = DistractionFreeMode()

        first = mode.render(doc, Session())
        visible_lines = len(first.text_lines)
        assert visible_lines < 200, "doc must span more than one page"

        mode.handle_input(KeyAction.PAGE_NEXT, "", doc)
        target_line = visible_lines + 2  # 3rd row of the second page
        doc.selection = Selection(target_line, 0, target_line, 4)

        frame = mode.render(doc, Session())

        assert frame.selection is not None
        sl, sc, el, ec = frame.selection
        # Row lands within the visible page slice, not at its raw wrapped index.
        assert sl == 2
        assert el == 2
        assert sc == 0
        assert ec == 4

    def test_no_selection_returns_none(self):
        doc = Document(_LONG_LINE)
        mode = DistractionFreeMode()
        frame = mode.render(doc, Session())
        assert frame.selection is None

    def test_dashboard_maps_selection(self):
        # Dashboard uses a narrower text column; just assert it maps (row/col)
        # rather than passing raw document coords, and honors scroll offset.
        doc = Document(_LONG_LINE)
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.selection = Selection(0, 5, 0, 15)

        mode = DashboardMode()
        frame = mode.render(doc, Session())
        assert frame.selection is not None
        sl, sc, el, ec = frame.selection
        # Start is on the first visual row.
        assert sl == 0
        assert sc == 5

    def test_typewriter_maps_selection_through_start(self):
        # Many lines so typewriter scrolls the cursor to the focus position.
        doc = Document("\n".join(f"line{i}" for i in range(40)))
        doc.cursor_line = 39
        doc.cursor_col = 0
        doc.selection = Selection(39, 0, 39, 5)

        mode = TypewriterMode()
        frame = mode.render(doc, Session())
        assert frame.selection is not None
        sl, sc, el, ec = frame.selection
        # The selection row must map into the visible window (not raw doc row 39).
        assert 0 <= sl < len(frame.text_lines)
        assert sl == frame.cursor_line
        assert sc == 0
        assert ec == 5


class TestPageDownClamp:
    """BUG-3 — PAGE_DOWN cannot scroll into a permanently blank screen."""

    def test_page_down_does_not_blank_distraction_free(self):
        doc = Document("\n".join(f"line {i}" for i in range(10)))
        mode = DistractionFreeMode()
        session = Session()

        # Prime _wrapped_len.
        first = mode.render(doc, session)
        wrapped_len = len(first.text_lines)

        for _ in range(5):
            mode.handle_input(KeyAction.PAGE_DOWN, "", doc)
            frame = mode.render(doc, session)
            assert len(frame.text_lines) > 0  # never blank

        assert mode._scroll_offset <= max(0, wrapped_len - 1)

    def test_page_down_does_not_blank_dashboard(self):
        doc = Document("\n".join(f"line {i}" for i in range(10)))
        mode = DashboardMode()
        session = Session()
        mode.render(doc, session)

        for _ in range(5):
            mode.handle_input(KeyAction.PAGE_DOWN, "", doc)
            frame = mode.render(doc, session)
            assert len(frame.text_lines) > 0

    def test_page_up_after_clamp_restores_view(self):
        doc = Document("\n".join(f"line {i}" for i in range(10)))
        mode = DistractionFreeMode()
        session = Session()
        mode.render(doc, session)

        for _ in range(5):
            mode.handle_input(KeyAction.PAGE_DOWN, "", doc)
        mode.handle_input(KeyAction.PAGE_UP, "", doc)
        frame = mode.render(doc, session)
        assert len(frame.text_lines) > 0
