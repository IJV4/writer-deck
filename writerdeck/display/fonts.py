"""Font cache — LRU with a small cap suitable for Pi Zero."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

logger = logging.getLogger(__name__)

_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"

# Bundled monospace font, shipped in assets/ and therefore present in every
# release — unlike system fonts on a minimal Pi image. Used as the fallback
# before PIL's built-in bitmap font so a missing family never crashes rendering.
_BUNDLED_FALLBACK = _ASSETS_DIR / "Hack-Regular.ttf"

# System font search paths
_SYSTEM_FONT_DIRS = [
    Path("/usr/share/fonts/truetype"),
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    _ASSETS_DIR,
]


def _find_font_file(family: str, bold: bool = False, italic: bool = False) -> str | None:
    slug = family.lower().replace(" ", "")
    # Build suffix variants to search for
    suffixes = []
    if bold and italic:
        suffixes = ["bolditalic", "boldoblique", "bi", "bolditalic"]
    elif bold:
        suffixes = ["bold", "bd"]
    elif italic:
        suffixes = ["italic", "oblique", "it"]

    for d in _SYSTEM_FONT_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*.ttf"):
            stem = p.stem.lower().replace("-", "").replace(" ", "")
            if slug not in stem:
                continue
            if suffixes:
                if any(s in stem for s in suffixes):
                    return str(p)
            else:
                # Prefer regular/non-bold/non-italic
                if not any(s in stem for s in ("bold", "italic", "oblique")):
                    return str(p)

    # Fallback: if looking for variant, try without suffix restriction
    if suffixes:
        return _find_font_file(family)

    # Last resort: any match
    for d in _SYSTEM_FONT_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*.ttf"):
            if slug in p.stem.lower().replace("-", "").replace(" ", ""):
                return str(p)
    return None


@lru_cache(maxsize=16)
def get_font(
    family: str, size: int, bold: bool = False, italic: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _find_font_file(family, bold=bold, italic=italic)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            logger.warning("Font %r failed to load; falling back", path)
    # Fallbacks, most-preferred first. get_font must NEVER raise: it runs deep
    # inside the render path, which only catches DisplayError — an OSError here
    # (e.g. no DejaVu on a minimal Pi image) would crash the main loop instead
    # of degrading. The bundled Hack font ships in every release, so the first
    # candidate practically always succeeds.
    for candidate in (str(_BUNDLED_FALLBACK), "DejaVuSansMono.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    logger.error("No TrueType font available; using PIL's built-in bitmap font")
    # load_default(size) itself calls truetype() under the hood on modern
    # Pillow (it bundles a TTF and only skips truetype when FreeType support
    # is entirely absent), so it can also raise OSError when every TrueType
    # path is unavailable — not just TypeError on Pillow < 10, which lacks the
    # size parameter entirely. get_font must never raise, so the true last
    # resort is load_default_imagefont(), which never touches truetype().
    try:
        return ImageFont.load_default(size)
    except TypeError:  # Pillow < 10 has no size parameter
        return ImageFont.load_default()
    except OSError:
        return ImageFont.load_default_imagefont()


def list_available_fonts() -> list[str]:
    """Return a sorted list of unique font family names found on the system."""
    seen: set[str] = set()
    for d in _SYSTEM_FONT_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*.ttf"):
            # Use the stem, strip common suffixes
            name = p.stem
            for suffix in ("-Regular", "-Bold", "-Italic", "-BoldItalic", "-Light", "-Medium"):
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            seen.add(name)
    return sorted(seen)
