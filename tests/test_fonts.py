"""Tests for font loading and its always-safe fallback."""

from __future__ import annotations

from PIL import ImageFont

from writerdeck.display import fonts
from writerdeck.display.fonts import (
    font_style_label,
    get_font,
    list_available_fonts,
    list_available_fonts_labeled,
)


def test_get_font_returns_usable_font():
    font = get_font("Hack", 14)
    assert font is not None
    assert font.getlength("abc") > 0


def test_get_font_unknown_family_falls_back_not_raises():
    # An unknown family must resolve to the bundled fallback, never raise.
    font = get_font("NoSuchFontFamilyXYZ", 14)
    assert font is not None


def test_get_font_never_raises_when_truetype_unavailable(monkeypatch):
    # If every TrueType load fails (minimal Pi image with no DejaVu and no
    # bundled asset), get_font must fall back to PIL's built-in bitmap font
    # rather than raise OSError — the render loop only catches DisplayError,
    # so a raise here would crash the whole app.
    def boom(*args, **kwargs):
        raise OSError("no truetype font available")

    monkeypatch.setattr(ImageFont, "truetype", boom)
    get_font.cache_clear()
    try:
        font = get_font("AnyFamily", 12)
    finally:
        get_font.cache_clear()
    assert font is not None


class TestListAvailableFonts:
    """FIX-4/5 follow-up: the picker must not surface icon fonts or a
    separate entry per weight/style variant of the same family."""

    def _fake_font_dir(self, tmp_path, names):
        for name in names:
            (tmp_path / f"{name}.ttf").write_bytes(b"")
        return tmp_path

    def test_weight_variants_collapse_to_one_family(self, tmp_path, monkeypatch):
        self._fake_font_dir(
            tmp_path,
            [
                "Lato-Regular", "Lato-Bold", "Lato-Black", "Lato-BlackItalic",
                "Lato-Hairline", "Lato-HairlineItalic", "Lato-Semibold",
                "Lato-SemiboldItalic", "Lato-Thin", "Lato-ThinItalic",
            ],
        )
        monkeypatch.setattr(fonts, "_SYSTEM_FONT_DIRS", [tmp_path])
        assert list_available_fonts() == ["Lato"]

    def test_icon_fonts_excluded(self, tmp_path, monkeypatch):
        self._fake_font_dir(
            tmp_path, ["Hack-Regular", "fontawesome-webfont", "MaterialIcons-Regular"]
        )
        monkeypatch.setattr(fonts, "_SYSTEM_FONT_DIRS", [tmp_path])
        assert list_available_fonts() == ["Hack"]

    def test_distinct_families_kept_separate(self, tmp_path, monkeypatch):
        self._fake_font_dir(tmp_path, ["Hack-Regular", "DejaVuSerif-Bold", "Lato-Italic"])
        monkeypatch.setattr(fonts, "_SYSTEM_FONT_DIRS", [tmp_path])
        assert list_available_fonts() == ["DejaVuSerif", "Hack", "Lato"]

    def test_otf_files_discovered(self, tmp_path, monkeypatch):
        for name in ("Courier Prime", "Courier Prime Bold", "Courier Prime Bold Italic"):
            (tmp_path / f"{name}.otf").write_bytes(b"")
        monkeypatch.setattr(fonts, "_SYSTEM_FONT_DIRS", [tmp_path])
        assert list_available_fonts() == ["Courier Prime"]

    def test_ambiguous_subfamilies_excluded(self, tmp_path, monkeypatch):
        # "Courier Prime Sans"/"Code" share a slug prefix with the base family
        # and would make font lookup ambiguous, so they're filtered out.
        for name in ("Courier Prime", "Courier Prime Sans", "Courier Prime Code"):
            (tmp_path / f"{name}.otf").write_bytes(b"")
        monkeypatch.setattr(fonts, "_SYSTEM_FONT_DIRS", [tmp_path])
        assert list_available_fonts() == ["Courier Prime"]

    def test_optical_size_suffix_collapsed_and_aliased(self, tmp_path, monkeypatch):
        for name in ("EBGaramond08-Regular", "EBGaramond12-Regular", "EBGaramond12-Bold"):
            (tmp_path / f"{name}.otf").write_bytes(b"")
        monkeypatch.setattr(fonts, "_SYSTEM_FONT_DIRS", [tmp_path])
        assert list_available_fonts() == ["EB Garamond"]


class TestFontStyleLabel:
    """The picker should hint at typology (Serif/Sans/Monospace) so entries
    are distinguishable without selecting each one to preview it. The name
    heuristic is only a tiebreaker once the metric-based monospace check
    (which depends on which font file is actually resolvable on this
    machine) says no, so that check is stubbed here for isolation."""

    def test_monospace_detected_by_metrics(self):
        assert font_style_label("Hack") == "Monospace"

    def test_serif_detected_by_name(self, monkeypatch):
        monkeypatch.setattr(fonts, "_is_monospace", lambda family: False)
        assert font_style_label("DejaVu Serif") == "Serif"

    def test_sans_is_default(self, monkeypatch):
        monkeypatch.setattr(fonts, "_is_monospace", lambda family: False)
        assert font_style_label("Lato") == "Sans"

    def test_labeled_list_pairs_family_with_label(self, tmp_path, monkeypatch):
        (tmp_path / "Hack-Regular.ttf").write_bytes(b"")
        monkeypatch.setattr(fonts, "_SYSTEM_FONT_DIRS", [tmp_path])
        pairs = list_available_fonts_labeled()
        assert pairs == [("Hack", "Hack — Monospace")]
