"""Splash screen — shown at startup."""

from __future__ import annotations

from PIL import Image, ImageDraw

from writerdeck.display.driver import HEIGHT, WIDTH
from writerdeck.display.fonts import get_font


def render_splash() -> Image.Image:
    """Render a splash screen image (800x480, 1-bit)."""
    img = Image.new("1", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(img)

    # Title
    title_font = get_font("Hack", 36)
    title = "Writer Deck"
    bbox = title_font.getbbox(title)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (WIDTH - tw) // 2
    ty = (HEIGHT - th) // 2 - 30
    draw.text((tx, ty), title, font=title_font, fill=0)

    # Subtitle
    sub_font = get_font("Hack", 14)
    subtitle = "distraction-free writing"
    bbox = sub_font.getbbox(subtitle)
    sw = bbox[2] - bbox[0]
    sx = (WIDTH - sw) // 2
    sy = ty + th + 20
    draw.text((sx, sy), subtitle, font=sub_font, fill=0)

    return img


def render_paused(hint: str = "Paused — press any key") -> Image.Image:
    """Render a mostly-white "paused" screensaver frame (LONG-3).

    Shown just before entering the long-idle deep-sleep tier so a static
    high-contrast page doesn't sit on the panel for hours (retention
    mitigation). Almost the entire panel is white; a small centered hint is the
    only ink. On wake the app forces a full refresh, so the previous page is
    restored cleanly.
    """
    img = Image.new("1", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(img)

    hint_font = get_font("Hack", 14)
    bbox = hint_font.getbbox(hint)
    hw = bbox[2] - bbox[0]
    hh = bbox[3] - bbox[1]
    hx = (WIDTH - hw) // 2
    hy = (HEIGHT - hh) // 2
    draw.text((hx, hy), hint, font=hint_font, fill=0)

    return img
