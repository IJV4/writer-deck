"""Tests for heading classification (document structure)."""

from __future__ import annotations

from writerdeck.utils.headings import (
    HEADING_FONT_DELTA,
    HEADING_PREFIX,
    classify_line,
    line_kinds_for_rows,
)


class TestClassifyLine:
    def test_h1_heading(self):
        assert classify_line("# Chapter One") == "h1"

    def test_h2_heading(self):
        assert classify_line("## Section A") == "h2"

    def test_body_line(self):
        assert classify_line("Just some prose.") == "body"

    def test_h3_is_not_a_heading(self):
        assert classify_line("### Not supported") == "body"

    def test_hash_without_space_is_not_a_heading(self):
        assert classify_line("#nospace") == "body"

    def test_leading_whitespace_is_tolerated(self):
        assert classify_line("   # Indented Heading") == "h1"

    def test_empty_line_is_body(self):
        assert classify_line("") == "body"

    def test_font_delta_and_prefix_tables(self):
        assert HEADING_FONT_DELTA == {"h1": 6, "h2": 3}
        assert HEADING_PREFIX == {"h1": "# ", "h2": "## "}


class TestLineKindsForRows:
    def test_maps_row_map_to_kinds(self):
        doc_lines = ["# Title", "body text", "## Sub"]
        row_map = [(0, 0), (1, 0), (2, 0)]
        assert line_kinds_for_rows(doc_lines, row_map) == ["h1", "body", "h2"]

    def test_multi_row_wrapped_heading_repeats_kind(self):
        # A long heading that wraps to two visual rows: both rows share doc_line_idx=0.
        doc_lines = ["# " + ("word " * 40).strip()]
        row_map = [(0, 0), (0, 120)]
        assert line_kinds_for_rows(doc_lines, row_map) == ["h1", "h1"]

    def test_empty_doc_lines_returns_empty(self):
        assert line_kinds_for_rows([], []) == []
