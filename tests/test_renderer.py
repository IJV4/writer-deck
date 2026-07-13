"""Tests for the renderer — verifies rendered images have correct properties."""

from __future__ import annotations

from PIL import Image

from writerdeck.display.driver import WIDTH, HEIGHT
from writerdeck.display.renderer import render
from writerdeck.modes.base_mode import RenderFrame


def _pixel(img: Image.Image, x: int, y: int) -> int:
    """Return pixel value at (x, y). 0=black, 255=white for mode '1'."""
    return img.getpixel((x, y))


class TestRenderBasic:
    def test_output_dimensions(self):
        frame = RenderFrame(text_lines=["Hello"])
        img = render(frame, "Hack", 14)
        assert img.size == (WIDTH, HEIGHT)

    def test_output_mode_is_1bit(self):
        frame = RenderFrame(text_lines=["Hello"])
        img = render(frame, "Hack", 14)
        assert img.mode == "1"






    def test_empty_frame(self):
        frame = RenderFrame(text_lines=[])
        img = render(frame, "Hack", 14)
        assert img.size == (WIDTH, HEIGHT)
        # Mostly white (no text drawn)
        white_count = sum(1 for x in range(WIDTH) for y in range(HEIGHT) if _pixel(img, x, y) == 255)
        assert white_count > (WIDTH * HEIGHT * 0.95)

    def test_text_draws_black_pixels(self):
        frame = RenderFrame(text_lines=["XXXXX XXXXX XXXXX"])
        img = render(frame, "Hack", 14)
        # There should be some black pixels in the text area
        black_count = sum(
            1 for x in range(8, 200) for y in range(8, 30)
            if _pixel(img, x, y) == 0
        )
        assert black_count > 0


class TestRenderCursor:
    def test_cursor_draws_black_rect(self):
        frame = RenderFrame(
            text_lines=["Hello"],
            cursor_line=0,
            cursor_col=0,
            show_cursor=True,
        )
        img = render(frame, "Hack", 14)
        # Cursor should be at margin_left (8), first line
        # Check there are black pixels around cursor position
        margin_left = 8
        margin_top = 8
        # Pixel at cursor x=8, y within first line should be black
        found_cursor = False
        for y in range(margin_top, margin_top + 18):
            if _pixel(img, margin_left, y) == 0:
                found_cursor = True
                break
        assert found_cursor

    def test_cursor_hidden(self):
        # Render same text with cursor hidden vs shown and compare
        frame_shown = RenderFrame(
            text_lines=[""],
            cursor_line=0,
            cursor_col=0,
            show_cursor=True,
        )
        frame_hidden = RenderFrame(
            text_lines=[""],
            cursor_line=0,
            cursor_col=0,
            show_cursor=False,
        )
        img_shown = render(frame_shown, "Hack", 14)
        img_hidden = render(frame_hidden, "Hack", 14)
        # With cursor shown on empty line, there should be more black pixels
        black_shown = sum(
            1 for x in range(0, 20) for y in range(0, 30)
            if _pixel(img_shown, x, y) == 0
        )
        black_hidden = sum(
            1 for x in range(0, 20) for y in range(0, 30)
            if _pixel(img_hidden, x, y) == 0
        )
        assert black_shown > black_hidden


class TestRenderStatusMessage:
    def test_status_message_draws_inverted_bar(self):
        frame = RenderFrame(
            text_lines=["Hello"],
            status_message="Saved",
        )
        img = render(frame, "Hack", 14)
        # Top 24px should be mostly black (inverted bar)
        black_top = sum(
            1 for x in range(WIDTH) for y in range(24)
            if _pixel(img, x, y) == 0
        )
        total_top = WIDTH * 24
        assert black_top > total_top * 0.8  # >80% black

    def test_no_status_message(self):
        frame = RenderFrame(text_lines=["Hello"])
        img = render(frame, "Hack", 14)
        # Top 24px should be mostly white (no inverted bar)
        white_top = sum(
            1 for x in range(WIDTH) for y in range(5)
            if _pixel(img, x, y) == 255
        )
        assert white_top > WIDTH * 5 * 0.9


class TestRenderTitleBar:
    def test_title_bar_draws_text_and_line(self):
        frame = RenderFrame(
            text_lines=["Hello"],
            title="My Document *",
        )
        img = render(frame, "Hack", 14)
        # Title area should have some black pixels (text + separator line)
        black_title = sum(
            1 for x in range(8, 200) for y in range(8, 26)
            if _pixel(img, x, y) == 0
        )
        assert black_title > 0

    def test_status_message_takes_precedence_over_title(self):
        frame = RenderFrame(
            text_lines=["Hello"],
            title="My Document",
            status_message="Saved",
        )
        img = render(frame, "Hack", 14)
        # Top 24px should be inverted bar (status), not title
        black_top = sum(
            1 for x in range(WIDTH) for y in range(24)
            if _pixel(img, x, y) == 0
        )
        total_top = WIDTH * 24
        assert black_top > total_top * 0.8


class TestRenderStats:
    def test_footer_stats(self):
        frame = RenderFrame(
            text_lines=["Hello"],
            stats={"Words": "42"},
            stats_position="footer",
        )
        img = render(frame, "Hack", 14)
        # Bottom area should have some black pixels (footer text)
        black_bottom = sum(
            1 for x in range(8, 200) for y in range(HEIGHT - 18, HEIGHT)
            if _pixel(img, x, y) == 0
        )
        assert black_bottom > 0

    def test_sidebar_stats(self):
        frame = RenderFrame(
            text_lines=["Hello"],
            stats={"Words": "42", "Session": "5m"},
            stats_position="sidebar",
            sidebar_width=220,
        )
        img = render(frame, "Hack", 14)
        # Right side should have a vertical divider (black pixels)
        divider_x = WIDTH - 220
        black_divider = sum(
            1 for y in range(HEIGHT)
            if _pixel(img, divider_x, y) == 0
        )
        assert black_divider > HEIGHT * 0.5


class TestRenderSelection:
    def test_selection_inverts_pixels(self):
        frame = RenderFrame(
            text_lines=["Hello World"],
            cursor_line=0,
            cursor_col=5,
            show_cursor=False,
            selection=(0, 0, 0, 5),  # Select "Hello"
        )
        img = render(frame, "Hack", 14)
        # Selected region should have some black fill (highlight)
        black_selected = sum(
            1 for x in range(8, 60) for y in range(8, 26)
            if _pixel(img, x, y) == 0
        )
        assert black_selected > 0

    def test_no_selection(self):
        frame_no_sel = RenderFrame(
            text_lines=["Hello World"],
            show_cursor=False,
            selection=None,
        )
        frame_sel = RenderFrame(
            text_lines=["Hello World"],
            show_cursor=False,
            selection=(0, 0, 0, 5),
        )
        img_no = render(frame_no_sel, "Hack", 14)
        img_sel = render(frame_sel, "Hack", 14)
        # With selection, there should be more black pixels
        black_no = sum(
            1 for x in range(8, 80) for y in range(8, 26)
            if _pixel(img_no, x, y) == 0
        )
        black_sel = sum(
            1 for x in range(8, 80) for y in range(8, 26)
            if _pixel(img_sel, x, y) == 0
        )
        assert black_sel > black_no


class TestHeadingRendering:
    def test_heading_prefix_is_stripped_from_output(self):
        # Rendering "# Title" as h1 must be pixel-identical to rendering the
        # already-stripped "Title" as h1 — proving the "# " prefix is
        # actually removed before drawing, not just present without crashing.
        frame_with_prefix = RenderFrame(text_lines=["# Title"], line_kinds=["h1"])
        frame_stripped = RenderFrame(text_lines=["Title"], line_kinds=["h1"])
        img_with_prefix = render(frame_with_prefix, "Hack", 14)
        img_stripped = render(frame_stripped, "Hack", 14)
        assert img_with_prefix.tobytes() == img_stripped.tobytes()

    def test_heading_row_is_taller_than_body_row(self):
        # Same two-line content, second line's row-kind differs: an h1 first
        # line should push the second line down further than an all-body
        # page, since h1's row is taller (font_size+6+4) than body's
        # (font_size+4). Verified by finding where each line's ink actually
        # starts on the page, not just overall image dimensions.
        frame_h1_first = RenderFrame(
            text_lines=["M", "M"], line_kinds=["h1", "body"], margin_bottom=8,
        )
        frame_all_body = RenderFrame(
            text_lines=["M", "M"], line_kinds=["body", "body"], margin_bottom=8,
        )
        img_h1 = render(frame_h1_first, "Hack", 14)
        img_body = render(frame_all_body, "Hack", 14)

        def second_row_top(img):
            # Scan rows top-down over the columns where text is drawn; the
            # first contiguous dark band is row 0's "M", the second band
            # (after a run of ink-free rows) is row 1's "M".
            height = img.size[1]
            bands = []
            in_band = False
            for y in range(height):
                has_ink = any(img.getpixel((x, y)) == 0 for x in range(0, 40))
                if has_ink and not in_band:
                    bands.append(y)
                    in_band = True
                elif not has_ink:
                    in_band = False
            return bands[1]  # start of second ink band

        assert second_row_top(img_h1) > second_row_top(img_body)

    def test_no_line_kinds_defaults_to_body(self):
        # Backward compatibility: existing callers that never set line_kinds
        # must still render without error.
        frame = RenderFrame(text_lines=["plain line"])
        img = render(frame, "Hack", 14)
        assert img.size == (WIDTH, HEIGHT)

    def test_cursor_on_heading_row_does_not_crash(self):
        frame = RenderFrame(
            text_lines=["# Title"],
            line_kinds=["h1"],
            cursor_line=0,
            cursor_col=3,
            show_cursor=True,
        )
        img = render(frame, "Hack", 14)
        assert img.size == (WIDTH, HEIGHT)
