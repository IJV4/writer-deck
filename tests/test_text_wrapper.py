"""Tests for pixel-aware text wrapper."""

from writerdeck.utils.text_wrapper import wrap_lines, _wrap_single_line, _break_word, _subline_offsets
from writerdeck.display.fonts import get_font


def test_short_line_no_wrap():
    lines, cl, cc, row_map = wrap_lines(["Hello"], 0, 3, "Hack", 14, 800)
    assert lines == ["Hello"]
    assert cl == 0
    assert cc == 3


def test_empty_document():
    lines, cl, cc, row_map = wrap_lines([""], 0, 0, "Hack", 14, 800)
    assert lines == [""]
    assert cl == 0
    assert cc == 0


def test_multiline_preserves_structure():
    doc_lines = ["Line one", "Line two", "Line three"]
    lines, cl, cc, row_map = wrap_lines(doc_lines, 1, 4, "Hack", 14, 800)
    assert len(lines) == 3
    assert cl == 1
    assert cc == 4


def test_wrapping_occurs_on_narrow_width():
    long_line = "The quick brown fox jumps over the lazy dog"
    lines, cl, cc, row_map = wrap_lines([long_line], 0, 0, "Hack", 14, 50)
    assert len(lines) > 1


def test_cursor_tracks_through_wrap():
    long_line = "AAAA BBBB CCCC DDDD EEEE"
    lines, cl, cc, row_map = wrap_lines([long_line], 0, len(long_line), "Hack", 14, 60)
    assert cl == len(lines) - 1


# --- New edge case tests ---


def test_empty_lines_preserved():
    doc_lines = ["Hello", "", "World"]
    lines, cl, cc, row_map = wrap_lines(doc_lines, 2, 3, "Hack", 14, 800)
    assert lines == ["Hello", "", "World"]
    assert cl == 2
    assert cc == 3


def test_cursor_on_empty_line():
    doc_lines = ["Hello", "", "World"]
    lines, cl, cc, row_map = wrap_lines(doc_lines, 1, 0, "Hack", 14, 800)
    assert cl == 1
    assert cc == 0


def test_line_with_only_spaces():
    doc_lines = ["   "]
    lines, cl, cc, row_map = wrap_lines(doc_lines, 0, 2, "Hack", 14, 800)
    assert lines == ["   "]
    assert cc == 2


def test_multiple_lines_wrapping():
    doc_lines = ["short", "The quick brown fox jumps over the lazy dog"]
    lines, cl, cc, row_map = wrap_lines(doc_lines, 1, 0, "Hack", 14, 100)
    assert len(lines) > 2
    # Cursor on line 1 col 0 should be on the first sub-line of the second doc line
    assert cl >= 1


def test_cursor_at_wrap_boundary():
    # A line that wraps exactly at a word boundary
    font = get_font("Hack", 14)
    # Build a line that's just barely over the width
    word = "test "
    line = ""
    while font.getbbox(line + word)[2] < 200:
        line += word
    # cursor at end of the part that fits
    doc_lines = [line + "extra"]
    lines, cl, cc, row_map = wrap_lines(doc_lines, 0, len(line), "Hack", 14, 200)
    # cursor should be valid
    assert 0 <= cl < len(lines)
    assert cc >= 0


def test_wrap_single_line_short():
    font = get_font("Hack", 14)
    result = _wrap_single_line("Hi", font, 800)
    assert result == ["Hi"]


def test_wrap_single_line_empty():
    font = get_font("Hack", 14)
    result = _wrap_single_line("", font, 800)
    # Empty string has bbox width 0 which is <= 800
    assert result == [""]


def test_wrap_single_line_forces_break():
    font = get_font("Hack", 14)
    # A single very long word with narrow width
    result = _wrap_single_line("ABCDEFGHIJKLMNOPQRSTUVWXYZ", font, 30)
    assert len(result) > 1
    # All chars should be preserved
    assert "".join(result) == "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def test_break_word():
    font = get_font("Hack", 14)
    parts = _break_word("ABCDEFGHIJ", font, 40)
    assert len(parts) > 1
    assert "".join(parts) == "ABCDEFGHIJ"


def test_break_word_single_char_wider_than_max():
    font = get_font("Hack", 14)
    # Even with width=1, should still produce the character
    parts = _break_word("W", font, 1)
    assert len(parts) == 1
    assert parts[0] == "W"


def test_many_short_words():
    words = " ".join(["hi"] * 50)
    lines, cl, cc, row_map = wrap_lines([words], 0, 0, "Hack", 14, 200)
    assert len(lines) > 1
    # All text should be present
    assert "".join(lines).replace(" ", "") == "hi" * 50


def test_cursor_on_last_subline():
    # Put cursor at very end of a wrapping line
    long_line = "word " * 30
    total_len = len(long_line)
    lines, cl, cc, row_map = wrap_lines([long_line], 0, total_len, "Hack", 14, 200)
    assert cl == len(lines) - 1


# --- row_map and cursor offset tests ---


def test_row_map_single_line():
    lines, cl, cc, row_map = wrap_lines(["Hello world"], 0, 5, "Hack", 14, 800)
    assert len(row_map) == 1
    assert row_map[0] == (0, 0)


def test_row_map_multiline_no_wrap():
    doc_lines = ["foo", "bar", "baz"]
    lines, cl, cc, row_map = wrap_lines(doc_lines, 1, 2, "Hack", 14, 800)
    assert row_map == [(0, 0), (1, 0), (2, 0)]


def test_row_map_wrapped_line():
    # Force wrapping with narrow width
    long_line = "hello world foo bar"
    lines, cl, cc, row_map = wrap_lines([long_line], 0, 0, "Hack", 14, 60)
    assert len(lines) > 1
    # All row_map entries should reference doc line 0
    assert all(dl == 0 for dl, _ in row_map)
    # char_start of first row is always 0
    assert row_map[0][1] == 0
    # char_starts should be strictly increasing
    starts = [s for _, s in row_map]
    assert starts == sorted(starts)


def test_cursor_col_correct_after_wrap():
    # "hello world foo" wraps — cursor at start of "foo" should have col=0 in its sub-line
    font = get_font("Hack", 14)
    line = "hello world foo"
    sub_lines = _wrap_single_line(line, font, 70)
    if len(sub_lines) < 2:
        return  # not wrapped at this width, skip
    # Find where "foo" starts in the original
    foo_start = line.index("foo")
    lines, cl, cc, row_map = wrap_lines([line], 0, foo_start, "Hack", 14, 70)
    # cursor_col should be 0 (start of the "foo" sub-line)
    assert cc == 0


def test_subline_offsets_basic():
    offsets = _subline_offsets("hello world foo", ["hello world", "foo"])
    assert offsets == [0, 12]


def test_subline_offsets_repeated_word():
    offsets = _subline_offsets("foo foo foo", ["foo foo", "foo"])
    assert offsets[0] == 0
    assert offsets[1] == 8
