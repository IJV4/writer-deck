"""Tests for pixel-aware text wrapper."""

import pytest

from writerdeck.display.fonts import get_font
from writerdeck.utils.text_wrapper import (
    _break_word,
    _char_width_cache,
    _subline_offsets,
    _text_width,
    _wrap_cache,
    _wrap_single_line,
    clear_wrap_cache,
    map_selection,
    wrap_lines,
)


@pytest.fixture(autouse=True)
def isolate_wrap_cache():
    """Clear the wrap cache before every test for isolation."""
    clear_wrap_cache()
    yield
    clear_wrap_cache()


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


def test_break_word_long_unbroken_run_is_fast_and_correct():
    """A pathologically long unbroken word (no spaces) must wrap correctly
    and quickly. _break_word previously grew a trial string one character at
    a time, re-measuring it from scratch each time — O(n) measurements per
    line, each itself O(current length), an O(n^2) pattern that measured
    tens of seconds for a ~650-char run on real (slow) hardware. The
    binary-search rewrite must still produce every character, in order, with
    no segment exceeding max_width_px, well within a fraction of a second on
    any hardware.
    """
    import time

    font = get_font("Hack", 14)
    word = "d" * 700
    t0 = time.monotonic()
    parts = _break_word(word, font, 784)
    elapsed = time.monotonic() - t0

    assert "".join(parts) == word
    assert len(parts) > 1
    for part in parts:
        assert _text_width(font, part) <= 784
    assert elapsed < 1.0, f"_break_word took {elapsed:.3f}s for a 700-char run"


def test_wrap_single_line_long_paragraph_is_fast_and_correct():
    """A long paragraph line (many words, none individually overlong) must
    wrap correctly and quickly. _wrap_single_line previously re-measured the
    whole growing 'current' sub-line on every word — O(n) measurements per
    line, each itself O(current length) — an O(n^2) pattern that measured
    several seconds for a ~900-char real paragraph line on a Pi Zero 2W.
    """
    import time

    font = get_font("Hack", 14)
    line = " ".join(["word"] * 180)  # ~900 chars, plenty of word boundaries
    t0 = time.monotonic()
    result = _wrap_single_line(line, font, 784)
    elapsed = time.monotonic() - t0

    assert "".join(result).replace(" ", "") == line.replace(" ", "")
    assert len(result) > 1
    for sub in result:
        assert _text_width(font, sub) <= 784
    assert elapsed < 1.0, f"_wrap_single_line took {elapsed:.3f}s for a ~900-char paragraph"


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


# --- leading-whitespace wrap tests ---


def test_indented_line_keeps_indent_when_wrapped():
    """A wrapped indented line must retain its leading indent on the first
    sub-line (line.split(' ') used to discard leading whitespace, dropping the
    indentation and shifting the first sub-line's char offset off zero)."""
    font = get_font("Hack", 14)
    indent = "    "  # 4 leading spaces
    body = "The quick brown fox jumps over the lazy dog again and again"
    line = indent + body
    # Ensure it actually wraps at this width.
    assert _text_width(font, line) > 200
    sub_lines = _wrap_single_line(line, font, 200)
    assert len(sub_lines) > 1
    # First sub-line keeps the indent.
    assert sub_lines[0].startswith(indent)
    # No character content is lost (ignoring inter-word space collapsing).
    assert "".join(sub_lines).replace(" ", "") == line.replace(" ", "")
    # And _subline_offsets sees the first sub-line starting at 0.
    offsets = _subline_offsets(line, sub_lines)
    assert offsets[0] == 0


def test_cursor_in_leading_whitespace_maps_non_negative():
    """A cursor positioned inside a wrapped line's leading whitespace must map
    to a non-negative column (previously new_cursor_col = cursor_col - start
    went negative because the first sub-line's offset was the indent width)."""
    indent = "    "  # 4 leading spaces
    body = "The quick brown fox jumps over the lazy dog again and again"
    line = indent + body
    # cursor at col 2 -> inside the leading whitespace
    lines, cl, cc, row_map = wrap_lines([line], 0, 2, "Hack", 14, 200)
    assert len(lines) > 1
    # Cursor stays on the first visual row, at its real column (2), non-negative.
    assert cl == 0
    assert cc == 2
    assert cc >= 0
    # First visual row retains the indent so col 2 addresses a space within it.
    assert lines[0].startswith(indent)
    # row_map's first row starts at doc offset 0.
    assert row_map[0] == (0, 0)


def test_cursor_at_indent_start_maps_zero():
    """Cursor at col 0 of an indented wrapped line maps to col 0 (guard)."""
    line = "    " + ("alpha beta gamma delta epsilon zeta eta theta iota " * 2)
    lines, cl, cc, row_map = wrap_lines([line], 0, 0, "Hack", 14, 200)
    assert cl == 0
    assert cc == 0


class TestMapSelection:
    def _make_row_map(self, doc_lines, font_family="Hack", font_size=14, width=800):
        _, _, _, row_map = wrap_lines(doc_lines, 0, 0, font_family, font_size, width)
        return row_map

    def test_no_wrap_identity(self):
        # Single short line, no wrap: doc coords == visual coords
        row_map = self._make_row_map(["hello"])
        result = map_selection((0, 0, 0, 5), row_map)
        assert result == (0, 0, 0, 5)

    def test_multiline_no_wrap(self):
        # Two short lines, no wrap: doc line 1 == visual line 1
        row_map = self._make_row_map(["hello", "world"])
        result = map_selection((0, 0, 1, 5), row_map)
        assert result == (0, 0, 1, 5)

    def test_wrapped_line_select_all(self):
        # Line 0 wraps into 2 visual rows; line 1 is visual row 2.
        # select_all should map end to visual row 2, not doc row 1.
        long_line = "word " * 30  # forces wrap at 800px
        _, _, _, row_map = wrap_lines([long_line, "end"], 0, 0, "Hack", 14, 800)
        num_visual = len(row_map)
        assert num_visual > 2, "expected wrap to produce >2 visual rows"
        result = map_selection((0, 0, 1, 3), row_map)
        v_el = result[2]
        assert v_el == num_visual - 1

    def test_scroll_offset_subtracted(self):
        row_map = self._make_row_map(["hello", "world", "foo"])
        # scroll_offset=1 means visual row 1 becomes index 0 in visible area
        result = map_selection((1, 0, 2, 3), row_map, scroll_offset=1)
        assert result == (0, 0, 1, 3)


# --- wrap cache tests ---


def test_wrap_cache_hit_skips_recomputation():
    """Same line wrapped twice populates cache on first call; second call is a hit."""
    line = "The quick brown fox"
    result1, *_ = wrap_lines([line], 0, 0, "Hack", 14, 800)
    assert len(_wrap_cache) == 1
    result2, *_ = wrap_lines([line], 0, 0, "Hack", 14, 800)
    assert len(_wrap_cache) == 1
    assert result1 == result2


def test_clear_wrap_cache_forces_recomputation():
    """After clear_wrap_cache() the cache is empty."""
    wrap_lines(["some text"], 0, 0, "Hack", 14, 800)
    assert len(_wrap_cache) == 1
    clear_wrap_cache()
    assert len(_wrap_cache) == 0


def test_clear_wrap_cache_also_clears_char_width_cache():
    """The font-keyed char-width cache must be cleared too: it keys on id(font),
    which can be reused after a font-LRU eviction, so a stale entry would give a
    wrong width if left behind on a font change."""
    _text_width(get_font("Hack", 14), "hello world")
    assert len(_char_width_cache) > 0
    clear_wrap_cache()
    assert len(_char_width_cache) == 0


def test_wrap_cache_different_font_size_is_different_key():
    """Same line at two different font sizes produces two distinct cache entries."""
    line = "The quick brown fox"
    wrap_lines([line], 0, 0, "Hack", 14, 800)
    wrap_lines([line], 0, 0, "Hack", 16, 800)
    assert len(_wrap_cache) == 2


def test_wrap_cache_bounded_at_2000():
    """Inserting 2001 unique lines keeps the cache at or below 2000 entries."""
    for i in range(2001):
        unique_line = f"unique line content number {i:05d}"
        wrap_lines([unique_line], 0, 0, "Hack", 14, 800)
    assert len(_wrap_cache) <= 2000
