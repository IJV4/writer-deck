"""Pixel-aware word wrapping for e-ink rendering."""

from __future__ import annotations

from writerdeck.display.fonts import get_font
from writerdeck.utils.perf import get_perf

_wrap_cache: dict[tuple[str, str, int, int], list[str]] = {}


def clear_wrap_cache() -> None:
    """Clear the per-line wrap cache."""
    _wrap_cache.clear()


def wrap_lines(
    doc_lines: list[str],
    cursor_line: int,
    cursor_col: int,
    font_family: str,
    font_size: int,
    max_width_px: int,
) -> tuple[list[str], int, int, list[tuple[int, int]]]:
    """Wrap document lines to fit within max_width_px.

    Returns:
        (wrapped_lines, new_cursor_line, new_cursor_col, row_map)

        row_map[i] = (doc_line_idx, char_start_in_doc_line) for visual row i.
        Use row_map for visual up/down navigation.
    """
    font = get_font(font_family, font_size)

    with get_perf().time("wrap_lines"):
        wrapped: list[str] = []
        row_map: list[tuple[int, int]] = []
        new_cursor_line = 0
        new_cursor_col = cursor_col

        for line_idx, line in enumerate(doc_lines):
            if not line:
                if line_idx == cursor_line:
                    new_cursor_line = len(wrapped)
                    new_cursor_col = 0
                row_map.append((line_idx, 0))
                wrapped.append("")
                continue

            cache_key = (line, font_family, font_size, max_width_px)
            sub_lines = _wrap_cache.get(cache_key)
            if sub_lines is None:
                if len(_wrap_cache) >= 2000:
                    _wrap_cache.clear()
                sub_lines = _wrap_single_line(line, font, max_width_px)
                _wrap_cache[cache_key] = sub_lines
            offsets = _subline_offsets(line, sub_lines)

            if line_idx == cursor_line:
                # Find which sub-line the cursor falls in using real char offsets
                for i, (sub, start) in enumerate(zip(sub_lines, offsets)):
                    end = start + len(sub)
                    if cursor_col <= end or i == len(sub_lines) - 1:
                        new_cursor_line = len(wrapped) + i
                        new_cursor_col = cursor_col - start
                        break

            for sub, start in zip(sub_lines, offsets):
                row_map.append((line_idx, start))
                wrapped.append(sub)

    return wrapped, new_cursor_line, new_cursor_col, row_map


def map_selection(
    ordered_sel: tuple[int, int, int, int],
    row_map: list[tuple[int, int]],
    scroll_offset: int = 0,
) -> tuple[int, int, int, int]:
    """Convert ordered doc-space (line, col) selection to visual wrapped-line coordinates.

    row_map[i] = (doc_line_idx, char_start_in_doc_line) as returned by wrap_lines.
    scroll_offset is subtracted so coords align with the visible slice of wrapped lines.
    """
    sl, sc, el, ec = ordered_sel

    def doc_to_visual(doc_line: int, doc_col: int) -> tuple[int, int]:
        best = 0
        for i, (dl, offset) in enumerate(row_map):
            if dl == doc_line and offset <= doc_col:
                best = i
            elif dl > doc_line:
                break
        return best - scroll_offset, doc_col - row_map[best][1]

    v_sl, v_sc = doc_to_visual(sl, sc)
    v_el, v_ec = doc_to_visual(el, ec)
    return v_sl, v_sc, v_el, v_ec


def _subline_offsets(line: str, sub_lines: list[str]) -> list[int]:
    """Find the start offset of each sub-line within the original line.

    Uses str.find advancing from the previous match end, so it handles
    repeated sub-strings and both word-wrap and char-break cases correctly.
    """
    offsets: list[int] = []
    search_from = 0
    for sub in sub_lines:
        if not sub:
            offsets.append(search_from)
            continue
        idx = line.find(sub, search_from)
        if idx < 0:
            # Shouldn't happen with valid wrapping, but safe fallback
            offsets.append(search_from)
        else:
            offsets.append(idx)
            search_from = idx + len(sub)
    return offsets


def _text_width(font, text: str) -> float:
    """Measure text width in pixels.

    Prefers getlength() (width only, ~2x faster than getbbox() on this
    hardware) with a fallback for older Pillow builds that lack it.
    """
    getlength = getattr(font, "getlength", None)
    if getlength is not None:
        return float(getlength(text))
    return float(font.getbbox(text)[2])


def _wrap_single_line(line: str, font, max_width_px: int) -> list[str]:
    """Break a single line at word boundaries to fit within max_width_px."""
    if _text_width(font, line) <= max_width_px:
        return [line]

    words = line.split(" ")
    result: list[str] = []
    current = ""

    for word in words:
        trial = (current + " " + word) if current else word
        if _text_width(font, trial) <= max_width_px:
            current = trial
        else:
            if current:
                result.append(current)
            # If a single word exceeds width, force-break it
            if _text_width(font, word) > max_width_px:
                result.extend(_break_word(word, font, max_width_px))
                current = ""
            else:
                current = word

    if current:
        result.append(current)

    return result if result else [""]


def _break_word(word: str, font, max_width_px: int) -> list[str]:
    """Character-level break for words wider than max_width_px.

    Binary-searches each segment's fit point (O(log n) width measurements per
    segment) instead of growing a trial string one character at a time. The
    old approach did O(n) measurements per segment, each itself costing
    O(current length) on this font backend — an O(n^2) pattern overall that
    measured ~41s for a single ~650-character unbroken run on a Pi Zero 2W.
    """
    parts: list[str] = []
    n = len(word)
    start = 0
    while start < n:
        lo, hi = start + 1, n  # lo..hi: candidate end positions, at least 1 char
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if _text_width(font, word[start:mid]) <= max_width_px:
                lo = mid
            else:
                hi = mid - 1
        parts.append(word[start:lo])
        start = lo
    return parts
