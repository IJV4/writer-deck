"""Tests for Markdown line parser."""

from writerdeck.utils.markdown import parse_line, StyledSpan


class TestParseLine:
    def test_plain_text(self):
        result = parse_line("hello world", "Hack", 14)
        assert result.text == "hello world"
        assert result.font_size == 14
        assert result.bold is False
        assert result.indent == 0

    def test_h1(self):
        result = parse_line("# Title", "Hack", 14)
        assert result.text == "Title"
        assert result.font_size == 22  # 14 + 8
        assert result.bold is True

    def test_h2(self):
        result = parse_line("## Subtitle", "Hack", 14)
        assert result.text == "Subtitle"
        assert result.font_size == 18  # 14 + 4
        assert result.bold is True

    def test_h3(self):
        result = parse_line("### Section", "Hack", 14)
        assert result.text == "Section"
        assert result.font_size == 16  # 14 + 2
        assert result.bold is True

    def test_list_item(self):
        result = parse_line("- item one", "Hack", 14)
        assert result.text == "item one"
        assert result.indent == 16

    def test_bold_inline(self):
        result = parse_line("hello **world**", "Hack", 14)
        spans = result.spans
        assert len(spans) == 2
        assert spans[0].text == "hello "
        assert spans[0].bold is False
        assert spans[1].text == "world"
        assert spans[1].bold is True

    def test_italic_inline(self):
        result = parse_line("hello *world*", "Hack", 14)
        spans = result.spans
        assert len(spans) == 2
        assert spans[1].text == "world"
        assert spans[1].italic is True

    def test_no_markdown_prefix(self):
        # "#" without space is not a heading
        result = parse_line("#notheading", "Hack", 14)
        assert result.text == "#notheading"
        assert result.font_size == 14
