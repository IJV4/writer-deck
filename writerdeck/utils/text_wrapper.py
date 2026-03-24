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
) -> tuple[list[str], int, int]:
    """Wrap document lines to fit within max_width_px.

    Returns:
        (wrapped_lines, new_cursor_line, new_cursor_col)
    """
    font = get_font(font_family, font_size)
    wrapped: list[str] = []
    new_cursor_line = 0
    new_cursor_col = cursor_col

    for line_idx, line in enumerate(doc_lines):
        if not line:
            if line_idx == cursor_line:
                new_cursor_line = len(wrapped)
                new_cursor_col = 0
            wrapped.append("")
            continue

        sub_lines = _wrap_single_line(line, font, max_width_px)

        if line_idx == cursor_line:
            # Find which sub-line the cursor falls in
            pos = 0
            for i, sub in enumerate(sub_lines):
                sub_end = pos + len(sub)
                if cursor_col <= sub_end or i == len(sub_lines) - 1:
                    new_cursor_line = len(wrapped) + i
                    new_cursor_col = cursor_col - pos
                    break
                pos = sub_end

        wrapped.extend(sub_lines)

    return wrapped, new_cursor_line, new_cursor_col


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
