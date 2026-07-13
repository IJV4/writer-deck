"""Tests for heading rendering wired into DistractionFreeMode."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.modes.distraction_free import DistractionFreeMode


class TestDistractionFreeHeadings:
    def test_heading_line_gets_h1_kind(self):
        doc = Document("# Chapter One\nSome body text.")
        mode = DistractionFreeMode()
        frame = mode.render(doc, Session())
        assert frame.line_kinds is not None
        assert frame.line_kinds[0] == "h1"
        assert frame.line_kinds[1] == "body"

    def test_h2_heading_line_gets_h2_kind(self):
        doc = Document("## Section A\nbody")
        mode = DistractionFreeMode()
        frame = mode.render(doc, Session())
        assert frame.line_kinds[0] == "h2"

    def test_plain_document_is_all_body(self):
        doc = Document("line one\nline two")
        mode = DistractionFreeMode()
        frame = mode.render(doc, Session())
        assert frame.line_kinds == ["body", "body"]

    def test_line_kinds_length_matches_text_lines(self):
        doc = Document("# Title\n" + "\n".join(f"line {i}" for i in range(20)))
        mode = DistractionFreeMode()
        frame = mode.render(doc, Session())
        assert len(frame.line_kinds) == len(frame.text_lines)
