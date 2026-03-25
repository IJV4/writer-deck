"""Renderer — converts a RenderFrame into a 1-bit PIL Image for the e-ink display."""

from __future__ import annotations

from PIL import Image, ImageDraw

from writerdeck.display.driver import WIDTH, HEIGHT
from writerdeck.display.fonts import get_font
from writerdeck.modes.base_mode import RenderFrame


def render(
    frame: RenderFrame,
    font_family: str,
    font_size: int,
    *,
    grayscale: bool = False,
) -> Image.Image:
    """Render a RenderFrame to an 800x480 image.

    With grayscale=False (default) the image is 1-bit ('1' mode) for standard
    e-ink refresh. With grayscale=True it is 8-bit greyscale ('L' mode); PIL
    automatically anti-aliases TrueType glyphs in this mode, producing smooth
    edges that the 4Gray waveform can render as intermediate grey levels.
    """
    mode = "L" if grayscale else "1"
    img = Image.new(mode, (WIDTH, HEIGHT), 255)  # white background
    draw = ImageDraw.Draw(img)
    font = get_font(font_family, font_size)

    y = frame.margin_top
    line_height = font_size + 4

    # Status message bar (inverted, top 24px)
    if frame.status_message:
        draw.rectangle([0, 0, WIDTH, 24], fill=0)
        status_font = get_font(font_family, 12)
        draw.text((8, 4), frame.status_message, font=status_font, fill=255)
        y = max(y, 28)

    # Title bar
    elif frame.title:
        title_font = get_font(font_family, 10)
        draw.text((frame.margin_left, y), frame.title, font=title_font, fill=0)
        draw.line([(frame.margin_left, y + 14), (WIDTH - frame.margin_right, y + 14)], fill=0)
        y += 18

    for i, line_text in enumerate(frame.text_lines):
        if y + line_height > HEIGHT - frame.margin_bottom:
            break

        # Selection highlight (inverted region)
        if frame.selection is not None:
            _draw_selection_line(draw, frame, font, i, line_text, frame.margin_left, y, line_height)

        draw.text((frame.margin_left, y), line_text, font=font, fill=0)

        # Re-draw selected text in white on top of black highlight
        if frame.selection is not None:
            _draw_selected_text(draw, frame, font, i, line_text, frame.margin_left, y)

        # Draw cursor on the active line
        if i == frame.cursor_line and frame.show_cursor:
            col = frame.cursor_col
            prefix = line_text[:col]
            bbox = font.getbbox(prefix) if prefix else (0, 0, 0, 0)
            cx = frame.margin_left + bbox[2]
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
    x1 = x + (font.getbbox(prefix)[2] if prefix else 0)
    x2 = x + (font.getbbox(selected)[2] if selected else 0)
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
    sx = x + (font.getbbox(prefix)[2] if prefix else 0)
    draw.text((sx, y), sel_text, font=font, fill=255)


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
        draw.text((frame.margin_left, y), text, font=small, fill=0)

    elif frame.stats_position == "sidebar":
        x = WIDTH - frame.sidebar_width + 8
        # Vertical divider
        draw.line([(x - 8, 0), (x - 8, HEIGHT)], fill=0, width=1)
        y = 12
        for key, val in frame.stats.items():
            draw.text((x, y), str(key), font=small, fill=0)
            draw.text((x, y + 16), str(val), font=small, fill=0)
            y += 40
