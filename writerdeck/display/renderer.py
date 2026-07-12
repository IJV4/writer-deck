"""Renderer — converts a RenderFrame into a 1-bit PIL Image for the e-ink display."""

from __future__ import annotations

from PIL import Image, ImageDraw

from writerdeck.display.driver import HEIGHT, WIDTH
from writerdeck.display.fonts import get_font
from writerdeck.display.glyph_cache import draw_text_cached, text_width_cached
from writerdeck.modes.base_mode import RenderFrame


def render(
    frame: RenderFrame,
    font_family: str,
    font_size: int,
) -> Image.Image:
    """Render a RenderFrame to an 800x480 1-bit PIL Image for the e-ink display."""
    mode = "1"
    img = Image.new(mode, (WIDTH, HEIGHT), 255)  # white background
    draw = ImageDraw.Draw(img)
    font = get_font(font_family, font_size)

    y = frame.margin_top
    line_height = font_size + 4

    # Status message bar (inverted, top 24px)
    if frame.status_message:
        draw.rectangle([0, 0, WIDTH, 24], fill=0)
        status_font = get_font(font_family, 12)
        draw_text_cached(draw, (8, 4), frame.status_message, status_font, fill=255)
        y = max(y, 28)

    # Title bar
    elif frame.title:
        title_font = get_font(font_family, 10)
        draw_text_cached(draw, (frame.margin_left, y), frame.title, title_font, fill=0)
        draw.line([(frame.margin_left, y + 14), (WIDTH - frame.margin_right, y + 14)], fill=0)
        y += 18

    for i, line_text in enumerate(frame.text_lines):
        if y + line_height > HEIGHT - frame.margin_bottom:
            break

        # Selection highlight (inverted region)
        if frame.selection is not None:
            _draw_selection_line(draw, frame, font, i, line_text, frame.margin_left, y, line_height)

        draw_text_cached(draw, (frame.margin_left, y), line_text, font, fill=0)

        # Re-draw selected text in white on top of black highlight
        if frame.selection is not None:
            _draw_selected_text(draw, frame, font, i, line_text, frame.margin_left, y)

        # Draw cursor on the active line
        if i == frame.cursor_line and frame.show_cursor:
            col = frame.cursor_col
            prefix = line_text[:col]
            cx = frame.margin_left + round(text_width_cached(prefix, font) if prefix else 0)
            draw.rectangle(
                [cx, y, cx + 2, y + line_height],
                fill=0,
            )
        y += line_height

    # Stats footer / sidebar
    if frame.stats:
        _draw_stats(draw, frame, font_family)

    return img


def _draw_selection_line(
    draw: ImageDraw.ImageDraw, frame: RenderFrame, font,
    line_idx: int, line_text: str, x: int, y: int, line_height: int,
) -> None:
    """Draw black highlight rectangle for selected portion of a line."""
    if frame.selection is None:
        return
    sl, sc, el, ec = frame.selection
    if line_idx < sl or line_idx > el:
        return

    if line_idx == sl and line_idx == el:
        start_col, end_col = sc, ec
    elif line_idx == sl:
        start_col, end_col = sc, len(line_text)
    elif line_idx == el:
        start_col, end_col = 0, ec
    else:
        start_col, end_col = 0, len(line_text)

    prefix = line_text[:start_col]
    selected = line_text[:end_col]
    x1 = x + round(text_width_cached(prefix, font) if prefix else 0)
    x2 = x + round(text_width_cached(selected, font) if selected else 0)
    if x2 > x1:
        draw.rectangle([x1, y, x2, y + line_height], fill=0)


def _draw_selected_text(
    draw: ImageDraw.ImageDraw, frame: RenderFrame, font,
    line_idx: int, line_text: str, x: int, y: int,
) -> None:
    """Draw the selected text in white over the black highlight."""
    if frame.selection is None:
        return
    sl, sc, el, ec = frame.selection
    if line_idx < sl or line_idx > el:
        return

    if line_idx == sl and line_idx == el:
        start_col, end_col = sc, ec
    elif line_idx == sl:
        start_col, end_col = sc, len(line_text)
    elif line_idx == el:
        start_col, end_col = 0, ec
    else:
        start_col, end_col = 0, len(line_text)

    prefix = line_text[:start_col]
    sel_text = line_text[start_col:end_col]
    if not sel_text:
        return
    sx = x + round(text_width_cached(prefix, font) if prefix else 0)
    draw_text_cached(draw, (sx, y), sel_text, font, fill=255)


def _draw_stats(
    draw: ImageDraw.ImageDraw, frame: RenderFrame, font_family: str
) -> None:
    small = get_font(font_family, 12)

    if frame.stats_position == "footer":
        y = HEIGHT - 18
        parts = []
        for key, val in frame.stats.items():
            parts.append(f"{key}: {val}")
        text = "  |  ".join(parts)
        draw_text_cached(draw, (frame.margin_left, y), text, small, fill=0)

    elif frame.stats_position == "sidebar":
        x = WIDTH - frame.sidebar_width + 8
        # Vertical divider
        draw.line([(x - 8, 0), (x - 8, HEIGHT)], fill=0, width=1)
        y = 12
        for key, val in frame.stats.items():
            draw_text_cached(draw, (x, y), str(key), small, fill=0)
            draw_text_cached(draw, (x, y + 16), str(val), small, fill=0)
            y += 40
