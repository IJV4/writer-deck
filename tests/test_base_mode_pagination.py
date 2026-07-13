"""Tests for BaseMode._paginate_by_height — variable-height page packing."""

from __future__ import annotations

from writerdeck.modes.distraction_free import DistractionFreeMode


def _mode() -> DistractionFreeMode:
    return DistractionFreeMode()


class TestPaginateByHeight:
    def test_all_body_rows_single_page_when_they_fit(self):
        mode = _mode()
        wrapped = ["a", "b", "c"]
        kinds = ["body", "body", "body"]
        page, total, visible, visible_kinds, start, adj_cursor, show = (
            mode._paginate_by_height(wrapped, kinds, 0, 200, 14)
        )
        assert total == 1
        assert visible == wrapped
        assert visible_kinds == kinds
        assert start == 0
        assert adj_cursor == 0
        assert show is True

    def test_splits_into_multiple_pages_when_overflowing(self):
        mode = _mode()
        # Body row height = 14 + 4 = 18px. avail=40px -> 2 rows/page.
        wrapped = ["a", "b", "c", "d", "e"]
        kinds = ["body"] * 5
        page, total, visible, visible_kinds, start, adj_cursor, show = (
            mode._paginate_by_height(wrapped, kinds, 0, 40, 14)
        )
        assert total == 3  # 2 + 2 + 1
        assert visible == ["a", "b"]
        assert start == 0

    def test_heading_row_is_taller_and_consumes_more_budget(self):
        mode = _mode()
        # h1 row height = 14+6+4 = 24px (no gap: it's the first row on its page).
        # Remaining budget on a 40px page after the h1 row: 16px < one 18px body row.
        # So "body one" and "body two" pack onto page 1 (18+18=36px <= 40px).
        wrapped = ["# Title", "body one", "body two"]
        kinds = ["h1", "body", "body"]
        page, total, visible, visible_kinds, start, adj_cursor, show = (
            mode._paginate_by_height(wrapped, kinds, 0, 40, 14)
        )
        assert visible == ["# Title"]
        assert total == 2

    def test_gap_precedes_heading_not_first_on_its_page(self):
        mode = _mode()
        # Page 1: "body" (18px) + gap(18px) + h1(24px) = 60px > 50px avail,
        # so the heading pushes to page 2 where it IS first-on-page (no gap).
        wrapped = ["body", "# Title"]
        kinds = ["body", "h1"]
        page, total, visible, visible_kinds, start, adj_cursor, show = (
            mode._paginate_by_height(wrapped, kinds, 0, 50, 14)
        )
        assert total == 2
        assert visible == ["body"]

    def test_cursor_page_is_selected_when_not_manual(self):
        mode = _mode()
        wrapped = ["a", "b", "c", "d"]
        kinds = ["body"] * 4
        # Page size 2 rows (36px avail / 18px each). Cursor on row 3 -> page 1.
        page, total, visible, visible_kinds, start, adj_cursor, show = (
            mode._paginate_by_height(wrapped, kinds, 3, 36, 14)
        )
        assert page == 1
        assert start == 2
        assert adj_cursor == 1
        assert show is True

    def test_manual_page_stays_put_until_out_of_range(self):
        mode = _mode()
        wrapped = ["a", "b", "c", "d"]
        kinds = ["body"] * 4
        mode._current_page = 1
        mode._page_manual = True
        page, total, visible, visible_kinds, start, adj_cursor, show = (
            mode._paginate_by_height(wrapped, kinds, 0, 36, 14)
        )
        assert page == 1
        assert visible == ["c", "d"]

    def test_empty_wrapped_list(self):
        mode = _mode()
        page, total, visible, visible_kinds, start, adj_cursor, show = (
            mode._paginate_by_height([], [], 0, 200, 14)
        )
        assert total == 1
        assert visible == []
        assert visible_kinds == []
        assert start == 0
