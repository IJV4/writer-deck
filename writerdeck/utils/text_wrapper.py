"""Pixel-aware word wrapping for e-ink rendering."""

from __future__ import annotations

from writerdeck.display.fonts import get_font


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

        sub_lines = _wrap_single_line(line, font, max_width_px)
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


def _wrap_single_line(line: str, font, max_width_px: int) -> list[str]:
    """Break a single line at word boundaries to fit within max_width_px."""
    bbox = font.getbbox(line)
    if bbox[2] <= max_width_px:
        return [line]

    words = line.split(" ")
    result: list[str] = []
    current = ""

    for word in words:
        trial = (current + " " + word) if current else word
        bbox = font.getbbox(trial)
        if bbox[2] <= max_width_px:
            current = trial
        else:
            if current:
                result.append(current)
            # If a single word exceeds width, force-break it
            if font.getbbox(word)[2] > max_width_px:
                result.extend(_break_word(word, font, max_width_px))
                current = ""
            else:
                current = word

    if current:
        result.append(current)

    return result if result else [""]


def _break_word(word: str, font, max_width_px: int) -> list[str]:
    """Character-level break for words wider than max_width_px."""
    parts: list[str] = []
    current = ""
    for ch in word:
        trial = current + ch
        if font.getbbox(trial)[2] > max_width_px and current:
            parts.append(current)
            current = ch
        else:
            current = trial
    if current:
        parts.append(current)
    return parts
