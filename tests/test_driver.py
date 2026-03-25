"""Tests for NullDriver and EPaperDriver."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

from writerdeck.display.driver import EPaperDriver, NullDriver, create_driver, WIDTH, HEIGHT

# ---------------------------------------------------------------------------
# EPaperDriver bounding-box partial refresh
# ---------------------------------------------------------------------------

_ROW = WIDTH // 8       # 100 bytes per row
_BUF_SIZE = _ROW * HEIGHT  # 48 000 bytes


def _white_buf() -> bytes:
    """E-paper buffer for all-white screen (all zeros = e-paper white)."""
    return bytes(_BUF_SIZE)


def _image_with_black_rows(rows: list[int]) -> Image.Image:
    """800×480 white image with the given row indices set to black."""
    img = Image.new("1", (WIDTH, HEIGHT), 255)
    black_row = Image.new("1", (WIDTH, 1), 0)
    for y in rows:
        img.paste(black_row, (0, y))
    return img


def _make_epd_driver(
    last_buf: bytes | None = _white_buf(),
    mode: str = "full",
) -> tuple[EPaperDriver, MagicMock]:
    """EPaperDriver with a mock _epd. getbuffer inverts PIL bytes (matches real driver)."""
    mock_epd = MagicMock()
    mock_epd.getbuffer.side_effect = lambda img: bytes(
        b ^ 0xFF for b in img.convert("1").tobytes("raw")
    )
    drv = EPaperDriver()
    drv._epd = mock_epd
    drv._mode = mode
    drv._last_buf = last_buf
    return drv, mock_epd


class TestEPaperDriverBoundingBoxPartial:
    def test_calls_display_partial_with_correct_y_bounds(self):
        drv, mock_epd = _make_epd_driver()
        drv.display_partial(_image_with_black_rows([10]))
        mock_epd.display_Partial.assert_called_once()
        _, xstart, ystart, xend, yend = mock_epd.display_Partial.call_args.args
        assert ystart == 10
        assert yend == 11

    def test_partial_buffer_size_matches_changed_rows(self):
        drv, mock_epd = _make_epd_driver()
        drv.display_partial(_image_with_black_rows([5, 6, 7]))
        buf = mock_epd.display_Partial.call_args.args[0]
        assert len(buf) == 3 * _ROW

    def test_partial_buffer_is_inverted_for_cdi_polarity(self):
        # display_Partial uses CDI=0xA9 which inverts pixel polarity vs full mode.
        # EPaperDriver must pre-invert so the wire bytes are opposite to getbuffer output.
        drv, mock_epd = _make_epd_driver()
        # Black row: getbuffer → 0xFF bytes; after inversion sent to display_Partial → 0x00
        drv.display_partial(_image_with_black_rows([10]))
        sent = mock_epd.display_Partial.call_args.args[0]
        assert all(b == 0x00 for b in sent)  # 0xFF inverted = 0x00

    def test_xstart_is_zero_and_xend_is_full_width(self):
        drv, mock_epd = _make_epd_driver()
        drv.display_partial(_image_with_black_rows([10]))
        _, xstart, _, xend, _ = mock_epd.display_Partial.call_args.args
        assert xstart == 0
        assert xend == WIDTH

    def test_no_change_skips_display(self):
        drv, mock_epd = _make_epd_driver()
        # White image matches _white_buf — nothing changed.
        drv.display_partial(Image.new("1", (WIDTH, HEIGHT), 255))
        mock_epd.display_Partial.assert_not_called()
        mock_epd.display.assert_not_called()

    def test_no_last_buf_falls_back_to_fast_full_refresh(self):
        drv, mock_epd = _make_epd_driver(last_buf=None, mode=None)
        drv.display_partial(Image.new("1", (WIDTH, HEIGHT), 255))
        mock_epd.init_fast.assert_called_once()
        mock_epd.display.assert_called_once()
        mock_epd.display_Partial.assert_not_called()

    def test_consecutive_partials_init_part_only_once(self):
        drv, mock_epd = _make_epd_driver()
        drv.display_partial(_image_with_black_rows([10]))
        drv.display_partial(_image_with_black_rows([20]))
        mock_epd.init_part.assert_called_once()

    def test_last_buf_updated_with_new_rows_after_partial(self):
        drv, mock_epd = _make_epd_driver()
        drv.display_partial(_image_with_black_rows([15]))
        # Row 15 should now be 0xFF (black in e-paper format).
        row_start = 15 * _ROW
        assert all(b == 0xFF for b in drv._last_buf[row_start : row_start + _ROW])
        # All other rows still white (zeros).
        assert drv._last_buf[:row_start] == bytes(row_start)
        assert drv._last_buf[row_start + _ROW :] == bytes(_BUF_SIZE - row_start - _ROW)

    def test_large_change_escalates_to_fast_full(self):
        # Change > 30% of rows → init_fast + display, not display_Partial.
        drv, mock_epd = _make_epd_driver()
        # Make > 30% of rows (>144) black in a white-screen reference.
        rows = list(range(0, 200))  # 200/480 ≈ 42% — above threshold
        drv.display_partial(_image_with_black_rows(rows))
        mock_epd.init_fast.assert_called_once()
        mock_epd.display.assert_called_once()
        mock_epd.display_Partial.assert_not_called()

    def test_small_change_uses_bounding_box_partial(self):
        # Change < 30% of rows → init_part + display_Partial.
        drv, mock_epd = _make_epd_driver()
        drv.display_partial(_image_with_black_rows([10, 11, 12]))  # 3/480 ≈ 0.6%
        mock_epd.init_part.assert_called_once()
        mock_epd.display_Partial.assert_called_once()
        mock_epd.display.assert_not_called()

    def test_escalation_updates_last_buf(self):
        drv, mock_epd = _make_epd_driver()
        rows = list(range(0, 200))
        img = _image_with_black_rows(rows)
        drv.display_partial(img)
        # _last_buf should reflect the new image after escalated full refresh.
        assert drv._last_buf is not None
        assert len(drv._last_buf) == _BUF_SIZE

    def test_display_full_stores_last_buf(self):
        drv, mock_epd = _make_epd_driver(last_buf=None)
        img = Image.new("1", (WIDTH, HEIGHT), 0)  # all black
        # getbuffer returns all 0xFF for black image
        mock_epd.getbuffer.side_effect = lambda i: bytes(
            b ^ 0xFF for b in i.convert("1").tobytes("raw")
        )
        drv.display_full(img)
        assert drv._last_buf is not None
        assert len(drv._last_buf) == _BUF_SIZE

    def test_sleep_preserves_last_buf(self):
        # E-ink retains its image without power — _last_buf stays valid through sleep.
        last = _white_buf()
        drv, mock_epd = _make_epd_driver(last_buf=last)
        drv.sleep()
        assert drv._last_buf is last

    def test_wake_does_not_call_clear(self):
        drv, mock_epd = _make_epd_driver(mode=None)
        drv.wake()
        mock_epd.Clear.assert_not_called()

    def test_wake_calls_epd_init(self):
        drv, mock_epd = _make_epd_driver(mode=None)
        drv.wake()
        mock_epd.init.assert_called_once()

    def test_wake_sets_mode_to_full(self):
        drv, mock_epd = _make_epd_driver(mode=None)
        drv.wake()
        assert drv._mode == "full"

    def test_wake_preserves_last_buf(self):
        last = _white_buf()
        drv, mock_epd = _make_epd_driver(last_buf=last, mode=None)
        drv.wake()
        assert drv._last_buf is last


def _make_image() -> Image.Image:
    return Image.new("1", (WIDTH, HEIGHT), 255)


class TestNullDriverInit:
    def test_init_creates_directory(self, tmp_path):
        out = tmp_path / "frames"
        drv = NullDriver(output_dir=str(out))
        drv.init()
        assert out.exists()
        assert out.is_dir()

    def test_init_resets_sleeping(self, tmp_path):
        drv = NullDriver(output_dir=str(tmp_path / "frames"))
        drv.init()
        drv.sleep()
        assert drv._sleeping is True
        drv.init()
        assert drv._sleeping is False


class TestNullDriverDisplay:
    def test_display_full_saves_png(self, tmp_path):
        drv = NullDriver(output_dir=str(tmp_path))
        drv.init()
        drv.display_full(_make_image())
        pngs = list(tmp_path.glob("*.png"))
        assert len(pngs) == 1
        assert "full" in pngs[0].name

    def test_display_partial_saves_png(self, tmp_path):
        drv = NullDriver(output_dir=str(tmp_path))
        drv.init()
        drv.display_partial(_make_image())
        pngs = list(tmp_path.glob("*.png"))
        assert len(pngs) == 1
        assert "partial" in pngs[0].name

    def test_frame_counter_increments(self, tmp_path):
        drv = NullDriver(output_dir=str(tmp_path))
        drv.init()
        drv.display_full(_make_image())
        drv.display_full(_make_image())
        drv.display_partial(_make_image())
        pngs = sorted(tmp_path.glob("*.png"))
        assert len(pngs) == 3
        assert "0000" in pngs[0].name
        assert "0001" in pngs[1].name
        assert "0002" in pngs[2].name

    def test_saved_png_is_valid_image(self, tmp_path):
        drv = NullDriver(output_dir=str(tmp_path))
        drv.init()
        drv.display_full(_make_image())
        pngs = list(tmp_path.glob("*.png"))
        img = Image.open(str(pngs[0]))
        assert img.size == (WIDTH, HEIGHT)


class TestEPaperDriver4Gray:
    def test_calls_init_4gray_on_first_call(self):
        drv, mock_epd = _make_epd_driver(mode="full")
        drv.display_full_4gray(Image.new("L", (WIDTH, HEIGHT), 255))
        mock_epd.init_4Gray.assert_called_once()

    def test_does_not_reinit_when_already_in_4gray_mode(self):
        drv, mock_epd = _make_epd_driver(mode="4gray")
        drv.display_full_4gray(Image.new("L", (WIDTH, HEIGHT), 255))
        mock_epd.init_4Gray.assert_not_called()

    def test_calls_getbuffer_4gray_and_display_4gray(self):
        drv, mock_epd = _make_epd_driver(mode="full")
        img = Image.new("L", (WIDTH, HEIGHT), 255)
        drv.display_full_4gray(img)
        mock_epd.getbuffer_4Gray.assert_called_once_with(img)
        mock_epd.display_4Gray.assert_called_once()

    def test_sets_mode_to_4gray(self):
        drv, mock_epd = _make_epd_driver(mode="full")
        drv.display_full_4gray(Image.new("L", (WIDTH, HEIGHT), 255))
        assert drv._mode == "4gray"

    def test_clears_last_buf(self):
        # After 4Gray, controller RAM is in 4Gray format — _last_buf must be
        # cleared so the next display_partial() reloads DTM1/DTM2 via fast full.
        drv, mock_epd = _make_epd_driver(last_buf=_white_buf(), mode="full")
        drv.display_full_4gray(Image.new("L", (WIDTH, HEIGHT), 255))
        assert drv._last_buf is None

    def test_next_partial_after_4gray_falls_back_to_fast_full(self):
        drv, mock_epd = _make_epd_driver(last_buf=None, mode="4gray")
        drv.display_partial(Image.new("1", (WIDTH, HEIGHT), 255))
        mock_epd.init_fast.assert_called_once()
        mock_epd.display.assert_called_once()


class TestNullDriverSleep:
    def test_sleep_sets_flag(self, tmp_path):
        drv = NullDriver(output_dir=str(tmp_path))
        drv.init()
        drv.sleep()
        assert drv._sleeping is True

    def test_wake_clears_sleeping_flag(self, tmp_path):
        drv = NullDriver(output_dir=str(tmp_path))
        drv.init()
        drv.sleep()
        assert drv._sleeping is True
        drv.wake()
        assert drv._sleeping is False

    def test_close_calls_sleep(self, tmp_path):
        drv = NullDriver(output_dir=str(tmp_path))
        drv.init()
        drv.close()
        assert drv._sleeping is True

    def test_display_after_sleep_wakes(self, tmp_path):
        drv = NullDriver(output_dir=str(tmp_path))
        drv.init()
        drv.sleep()
        assert drv._sleeping is True
        # _save resets sleeping flag
        drv.display_full(_make_image())
        assert drv._sleeping is False
        pngs = list(tmp_path.glob("*.png"))
        assert len(pngs) == 1


class TestCreateDriver:
    def test_use_null_returns_null_driver(self):
        drv = create_driver(use_null=True)
        assert isinstance(drv, NullDriver)

    def test_epaper_unavailable_falls_back(self):
        # create_driver catches any init failure and falls back to NullDriver.
        # We simulate hardware unavailability by making EPaperDriver.init raise.
        from unittest.mock import patch
        from writerdeck.display.driver import EPaperDriver
        with patch.object(EPaperDriver, "init", side_effect=RuntimeError("no hardware")):
            drv = create_driver(use_null=False)
        assert isinstance(drv, NullDriver)
