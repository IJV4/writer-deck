"""Font cache — LRU with a small cap suitable for Pi Zero."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"

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
) -> ImageFont.FreeTypeFont:
    path = _find_font_file(family, bold=bold, italic=italic)
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.truetype("DejaVuSansMono.ttf", size)


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
