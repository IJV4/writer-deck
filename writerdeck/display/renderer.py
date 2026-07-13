"""Renderer — converts a RenderFrame into a 1-bit PIL Image for the e-ink display."""

from __future__ import annotations

from PIL import Image, ImageDraw

from writerdeck.display.driver import HEIGHT, WIDTH
from writerdeck.display.fonts import get_font
from writerdeck.display.glyph_cache import draw_text_cached, text_width_cached
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.utils.headings import HEADING_FONT_DELTA, HEADING_PREFIX


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

    prev_kind: str | None = None
    for i, line_text in enumerate(frame.text_lines):
        kind = frame.line_kinds[i] if frame.line_kinds else "body"
        row_font_size = font_size + HEADING_FONT_DELTA.get(kind, 0)
        row_font = font if kind == "body" else get_font(font_family, row_font_size)
        line_height = row_font_size + 4

        # Blank line's worth of vertical space before a heading, unless it's
        # the first row drawn in this frame (matches base_mode's own
        # first-on-page rule so pagination and rendering agree).
        if kind in HEADING_FONT_DELTA and i > 0 and prev_kind != kind:
            y += font_size + 4

        if y + line_height > HEIGHT - frame.margin_bottom:
            break

        prefix = HEADING_PREFIX.get(kind)
        strip_len = len(prefix) if (prefix and line_text.startswith(prefix)) else 0
        display_text = line_text[strip_len:]

        # Selection highlight (inverted region)
        if frame.selection is not None:
            _draw_selection_line(
                draw, frame, row_font, i, display_text,
                frame.margin_left, y, line_height, strip_len,
            )

        draw_text_cached(draw, (frame.margin_left, y), display_text, row_font, fill=0)

        # Re-draw selected text in white on top of black highlight
        if frame.selection is not None:
            _draw_selected_text(
                draw, frame, row_font, i, display_text, frame.margin_left, y, strip_len,
            )

        # Draw cursor on the active line
        if i == frame.cursor_line and frame.show_cursor:
            display_col = max(0, frame.cursor_col - strip_len)
            col_prefix = display_text[:display_col]
            cx = frame.margin_left + round(
                text_width_cached(col_prefix, row_font) if col_prefix else 0
            )
            draw.rectangle(
                [cx, y, cx + 2, y + line_height],
                fill=0,
            )
        y += line_height
        prev_kind = kind

    # Stats footer / sidebar
    if frame.stats:
        _draw_stats(draw, frame, font_family)

    return img


def _draw_selection_line(
    draw: ImageDraw.ImageDraw, frame: RenderFrame, font,
    line_idx: int, line_text: str, x: int, y: int, line_height: int,
    strip_len: int = 0,
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
        start_col, end_col = sc, len(line_text) + strip_len
    elif line_idx == el:
        start_col, end_col = 0, ec
    else:
        start_col, end_col = 0, len(line_text) + strip_len

    start_col = max(0, start_col - strip_len)
    end_col = max(0, end_col - strip_len)

    prefix = line_text[:start_col]
    selected = line_text[:end_col]
    x1 = x + round(text_width_cached(prefix, font) if prefix else 0)
    x2 = x + round(text_width_cached(selected, font) if selected else 0)
    if x2 > x1:
        draw.rectangle([x1, y, x2, y + line_height], fill=0)


def _draw_selected_text(
    draw: ImageDraw.ImageDraw, frame: RenderFrame, font,
    line_idx: int, line_text: str, x: int, y: int,
    strip_len: int = 0,
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
        start_col, end_col = sc, len(line_text) + strip_len
    elif line_idx == el:
        start_col, end_col = 0, ec
    else:
        start_col, end_col = 0, len(line_text) + strip_len

    start_col = max(0, start_col - strip_len)
    end_col = max(0, end_col - strip_len)

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
