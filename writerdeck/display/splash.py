"""Splash screen — shown at startup."""

from __future__ import annotations

from PIL import Image, ImageDraw

from writerdeck.display.driver import WIDTH, HEIGHT
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
