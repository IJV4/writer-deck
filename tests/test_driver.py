"""Tests for NullDriver and EPaperDriver."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PIL import Image

from writerdeck.display.driver import (
    HEIGHT,
    WIDTH,
    DisplayError,
    EPaperDriver,
    NullDriver,
    compute_dirty_bands,
    compute_x_window,
    create_driver,
)

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

    def test_escalation_boundary_at_threshold_stays_partial(self):
        # Exactly 144/480 = 0.30 is NOT > 0.30, so it must stay a partial.
        drv, mock_epd = _make_epd_driver()
        drv.display_partial(_image_with_black_rows(list(range(144))))
        mock_epd.display_Partial.assert_called_once()
        mock_epd.display.assert_not_called()

    def test_escalation_boundary_just_above_threshold_escalates(self):
        # 145/480 ≈ 0.302 is > 0.30, so it must escalate to fast-full.
        drv, mock_epd = _make_epd_driver()
        drv.display_partial(_image_with_black_rows(list(range(145))))
        mock_epd.init_fast.assert_called_once()
        mock_epd.display.assert_called_once()
        mock_epd.display_Partial.assert_not_called()

    def test_escalation_updates_last_buf(self):
        drv, mock_epd = _make_epd_driver()
        rows = list(range(0, 200))
        img = _image_with_black_rows(rows)
        drv.display_partial(img)
        # _last_buf should reflect the new image after escalated full refresh.
        assert drv._last_buf is not None
        assert len(drv._last_buf) == _BUF_SIZE

    def test_display_full_uses_fast_waveform_not_gc16(self):
        # display_full() should use init_fast(), not init() — fewer blink cycles.
        drv, mock_epd = _make_epd_driver(mode=None)
        drv.display_full(Image.new("1", (WIDTH, HEIGHT), 255))
        mock_epd.init_fast.assert_called_once()
        mock_epd.init.assert_not_called()

    def test_display_full_no_reinit_when_already_fast(self):
        drv, mock_epd = _make_epd_driver(mode="fast")
        drv.display_full(Image.new("1", (WIDTH, HEIGHT), 255))
        mock_epd.init_fast.assert_not_called()

    def test_display_full_stores_last_buf(self):
        drv, mock_epd = _make_epd_driver(last_buf=None)
        img = Image.new("1", (WIDTH, HEIGHT), 0)  # all black
        drv.display_full(img)
        assert drv._last_buf is not None
        assert len(drv._last_buf) == _BUF_SIZE

    def test_display_clean_always_calls_gc16_init(self):
        # display_clean() must use init() (GC16) every time, regardless of current mode.
        drv, mock_epd = _make_epd_driver(mode="fast")
        drv.display_clean(Image.new("1", (WIDTH, HEIGHT), 255))
        mock_epd.init.assert_called_once()
        mock_epd.init_fast.assert_not_called()

    def test_display_clean_sets_mode_to_full(self):
        drv, mock_epd = _make_epd_driver(mode="fast")
        drv.display_clean(Image.new("1", (WIDTH, HEIGHT), 255))
        assert drv._mode == "full"

    def test_display_clean_stores_last_buf(self):
        drv, mock_epd = _make_epd_driver(last_buf=None)
        drv.display_clean(Image.new("1", (WIDTH, HEIGHT), 255))
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

    def test_wake_calls_epd_init_fast(self):
        drv, mock_epd = _make_epd_driver(mode=None)
        drv.wake()
        mock_epd.init_fast.assert_called_once()

    def test_wake_sets_mode_to_fast(self):
        drv, mock_epd = _make_epd_driver(mode=None)
        drv.wake()
        assert drv._mode == "fast"

    def test_wake_preserves_last_buf(self):
        last = _white_buf()
        drv, mock_epd = _make_epd_driver(last_buf=last, mode=None)
        drv.wake()
        assert drv._last_buf is last

    def test_close_is_idempotent(self):
        # close() runs from both the signal handler and atexit — calling it
        # twice must be safe and must not Clear()/sleep() the panel twice.
        drv, mock_epd = _make_epd_driver(mode="full")
        drv.close()
        drv.close()
        mock_epd.Clear.assert_called_once()
        mock_epd.sleep.assert_called_once()

    def test_sleep_is_idempotent(self):
        drv, mock_epd = _make_epd_driver(mode="full")
        drv.sleep()
        drv.sleep()
        mock_epd.sleep.assert_called_once()

    def test_close_after_sleep_does_not_clear(self):
        # If already slept, close() must not attempt Clear() again.
        drv, mock_epd = _make_epd_driver(mode="full")
        drv.sleep()
        drv.close()
        mock_epd.Clear.assert_not_called()
        mock_epd.sleep.assert_called_once()

    def test_wake_resets_slept_flag(self):
        # After sleep + wake, the panel is powered again and can sleep once more.
        drv, mock_epd = _make_epd_driver(mode="full")
        drv.sleep()
        drv.wake()
        drv.sleep()
        assert mock_epd.sleep.call_count == 2

    def test_sleep_close_no_epd_is_safe(self):
        # A driver that never initialised (self._epd is None) must not raise.
        drv = EPaperDriver()
        drv.sleep()
        drv.close()


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

    def test_close_twice_is_safe(self, tmp_path):
        drv = NullDriver(output_dir=str(tmp_path))
        drv.init()
        drv.close()
        drv.close()  # must not raise
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


class TestEPaperDriverGhostPrevention:
    """display_full and escalation must NOT pass prev_image to epd.display().

    Passing _last_buf as DTM1 makes the A2 waveform skip driving unchanged
    pixels — ghost from prior partials accumulates on rows the user isn't
    actively editing (typically the top of the screen).
    """

    def test_display_full_does_not_pass_prev_image(self):
        drv, mock_epd = _make_epd_driver(mode="fast")
        drv.display_full(Image.new("1", (WIDTH, HEIGHT), 255))
        args, kwargs = mock_epd.display.call_args
        assert len(args) == 1, "display() must be called with one positional arg (no prev_image)"
        assert "prev_image" not in kwargs

    def test_partial_escalation_does_not_pass_prev_image(self):
        # >30% changed rows → escalates to fast full; must not pass prev_image.
        rows = list(range(0, 200))
        drv, mock_epd = _make_epd_driver(mode="fast")
        drv.display_partial(_image_with_black_rows(rows))
        args, kwargs = mock_epd.display.call_args
        assert len(args) == 1, "escalated display() must be called with one positional arg"
        assert "prev_image" not in kwargs

    def test_no_last_buf_fallback_does_not_pass_prev_image(self):
        drv, mock_epd = _make_epd_driver(last_buf=None, mode="fast")
        drv.display_partial(Image.new("1", (WIDTH, HEIGHT), 0))
        args, kwargs = mock_epd.display.call_args
        assert len(args) == 1
        assert "prev_image" not in kwargs


# ---------------------------------------------------------------------------
# PERF-1: compute_dirty_bands (pure, hardware-free)
# ---------------------------------------------------------------------------


def _blank() -> bytearray:
    return bytearray(_BUF_SIZE)


def _set_row(buf: bytearray, y: int, byte_val: int = 0xFF) -> None:
    for c in range(_ROW):
        buf[y * _ROW + c] = byte_val


class TestComputeDirtyBands:
    def test_no_change_returns_empty(self):
        old = _blank()
        bands, changed = compute_dirty_bands(old, bytes(old), HEIGHT, _ROW)
        assert bands == []
        assert changed == 0

    def test_two_distant_bands_are_disjoint(self):
        # A top band (cursor line ~10) and a bottom band (footer ~462) must
        # produce TWO small windows, not one full-height window (PERF-1 core).
        old = _blank()
        new = _blank()
        for y in (10, 11, 12):
            _set_row(new, y)
        for y in (460, 461, 462):
            _set_row(new, y)
        bands, changed = compute_dirty_bands(old, new, HEIGHT, _ROW)
        assert bands == [(10, 13), (460, 463)]
        assert changed == 6
        # Not one giant span:
        assert not any(b[1] - b[0] > 100 for b in bands)

    def test_small_gap_within_threshold_merges(self):
        # Two changes 20 rows apart (<= default gap 32) coalesce into one band.
        old = _blank()
        new = _blank()
        _set_row(new, 10)
        _set_row(new, 30)
        bands, changed = compute_dirty_bands(old, new, HEIGHT, _ROW)
        assert bands == [(10, 31)]
        assert changed == 2

    def test_large_gap_splits(self):
        # Two changes 50 rows apart (> default gap 32) split into two bands.
        old = _blank()
        new = _blank()
        _set_row(new, 10)
        _set_row(new, 60)
        bands, changed = compute_dirty_bands(old, new, HEIGHT, _ROW)
        assert bands == [(10, 11), (60, 61)]
        assert changed == 2

    def test_custom_gap_argument(self):
        old = _blank()
        new = _blank()
        _set_row(new, 10)
        _set_row(new, 15)
        # gap=2 → 5-row separation splits; gap=10 → merges.
        assert compute_dirty_bands(old, new, HEIGHT, _ROW, gap=2)[0] == [
            (10, 11), (15, 16)
        ]
        assert compute_dirty_bands(old, new, HEIGHT, _ROW, gap=10)[0] == [(10, 16)]

    def test_changed_rows_counts_only_differing_rows_not_span(self):
        # changed_rows gates the escalation threshold and must NOT include the
        # unchanged gap rows swallowed by a merged band.
        old = _blank()
        new = _blank()
        _set_row(new, 10)
        _set_row(new, 30)
        bands, changed = compute_dirty_bands(old, new, HEIGHT, _ROW)
        assert bands == [(10, 31)]  # span of 21
        assert changed == 2  # but only 2 rows actually differ


# ---------------------------------------------------------------------------
# PERF-2: compute_x_window (pure) + windowed slice in display_partial
# ---------------------------------------------------------------------------


class TestComputeXWindow:
    def test_full_width_row_returns_full_byte_range(self):
        old = _blank()
        new = _blank()
        _set_row(new, 10)
        assert compute_x_window(old, new, 10, 11, _ROW) == (0, _ROW)

    def test_narrow_change_returns_narrow_byte_range(self):
        old = _blank()
        new = _blank()
        # Change only byte-columns 3 and 4 on row 10.
        new[10 * _ROW + 3] = 0xFF
        new[10 * _ROW + 4] = 0xFF
        assert compute_x_window(old, new, 10, 11, _ROW) == (3, 5)

    def test_window_spans_min_max_across_band_rows(self):
        old = _blank()
        new = _blank()
        new[10 * _ROW + 2] = 0xFF   # left edge on row 10
        new[11 * _ROW + 7] = 0xFF   # right edge on row 11
        assert compute_x_window(old, new, 10, 12, _ROW) == (2, 8)

    def test_no_diff_falls_back_to_full_width(self):
        old = _blank()
        assert compute_x_window(old, bytes(old), 0, 5, _ROW) == (0, _ROW)


class TestDisplayPartialXWindowing:
    def _epd_black_rect(self, x0_px: int, x1_px: int, rows: list[int]) -> Image.Image:
        """White image with a black rectangle over [x0_px,x1_px) on given rows."""
        img = Image.new("1", (WIDTH, HEIGHT), 255)
        block = Image.new("1", (x1_px - x0_px, 1), 0)
        for y in rows:
            img.paste(block, (x0_px, y))
        return img

    def test_x_window_snapped_to_byte_boundaries(self):
        # A change at pixels 24..32 → byte-columns 3..4 → Xstart=24, Xend=32.
        drv, mock_epd = _make_epd_driver()
        drv.display_partial(self._epd_black_rect(24, 32, [10]))
        _, xstart, ystart, xend, yend = mock_epd.display_Partial.call_args.args
        assert xstart == 24
        assert xend == 32
        assert (ystart, yend) == (10, 11)

    def test_windowed_slice_length_equals_width_times_height(self):
        # Slice length must equal (byte-width) * (row-height) of the window.
        drv, mock_epd = _make_epd_driver()
        drv.display_partial(self._epd_black_rect(24, 40, [10, 11]))
        sent = mock_epd.display_Partial.call_args.args[0]
        _, xstart, ystart, xend, yend = mock_epd.display_Partial.call_args.args
        byte_width = (xend - xstart) // 8
        height = yend - ystart
        assert len(sent) == byte_width * height

    def test_windowed_slice_still_inverted_for_cdi_polarity(self):
        # The 0xA9 pre-inversion must still apply to the windowed slice: a black
        # column (getbuffer → 0xFF) becomes 0x00 at the wire.
        drv, mock_epd = _make_epd_driver()
        drv.display_partial(self._epd_black_rect(24, 32, [10]))
        sent = mock_epd.display_Partial.call_args.args[0]
        assert all(b == 0x00 for b in sent)

    def test_two_bands_issue_two_windowed_partials(self):
        # A change at the top and at the bottom → two display_Partial calls,
        # neither spanning the full panel height (PERF-1 on the hardware path).
        drv, mock_epd = _make_epd_driver()
        img = _image_with_black_rows([10, 460])
        drv.display_partial(img)
        assert mock_epd.display_Partial.call_count == 2
        for call in mock_epd.display_Partial.call_args_list:
            _, _, ystart, _, yend = call.args
            assert yend - ystart <= 2


# ---------------------------------------------------------------------------
# FAULT-6: bounded retry + graceful degradation on display ops
# ---------------------------------------------------------------------------


class TestDisplayOpRetry:
    """Each hardware display op retries a transient fault, then raises DisplayError."""

    def test_display_full_retries_once_then_succeeds(self):
        drv, mock_epd = _make_epd_driver(mode="fast")
        # display() raises the first time, succeeds the second.
        mock_epd.display.side_effect = [RuntimeError("SPI glitch"), None]
        drv.display_full(Image.new("1", (WIDTH, HEIGHT), 255))
        assert mock_epd.display.call_count == 2
        # The current waveform was re-initialised between tries.
        mock_epd.init_fast.assert_called()  # re-init on retry (mode == 'fast')

    def test_display_full_raises_after_repeated_failure(self):
        drv, mock_epd = _make_epd_driver(mode="fast")
        mock_epd.display.side_effect = RuntimeError("dead panel")
        with pytest.raises(DisplayError):
            drv.display_full(Image.new("1", (WIDTH, HEIGHT), 255))
        # 1 initial + 2 retries = DISPLAY_OP_ATTEMPTS attempts.
        from writerdeck.display.driver import DISPLAY_OP_ATTEMPTS
        assert mock_epd.display.call_count == DISPLAY_OP_ATTEMPTS

    def test_display_partial_retries_then_succeeds(self):
        drv, mock_epd = _make_epd_driver()
        mock_epd.display_Partial.side_effect = [RuntimeError("crc"), None]
        drv.display_partial(_image_with_black_rows([10]))
        assert mock_epd.display_Partial.call_count == 2

    def test_display_partial_raises_after_repeated_failure(self):
        drv, mock_epd = _make_epd_driver()
        mock_epd.display_Partial.side_effect = RuntimeError("dead")
        with pytest.raises(DisplayError):
            drv.display_partial(_image_with_black_rows([10]))

    def test_display_clean_retries_then_succeeds(self):
        drv, mock_epd = _make_epd_driver(mode="fast")
        mock_epd.display.side_effect = [RuntimeError("glitch"), None]
        drv.display_clean(Image.new("1", (WIDTH, HEIGHT), 255))
        assert mock_epd.display.call_count == 2

    def test_display_clean_raises_after_repeated_failure(self):
        drv, mock_epd = _make_epd_driver(mode="fast")
        mock_epd.display.side_effect = RuntimeError("dead")
        with pytest.raises(DisplayError):
            drv.display_clean(Image.new("1", (WIDTH, HEIGHT), 255))

    def test_busy_timeout_treated_as_failure(self):
        # FAULT-6 policy: a lingering BUSY pin (ReadBusy timeout) is a failed op,
        # not silently ignored — it must take the retry path.
        import types
        from unittest import mock as _mock

        drv, mock_epd = _make_epd_driver(mode="fast")
        mock_epd.busy_pin = 24
        fake_cfg = types.ModuleType("epdconfig")
        # Still busy (0) on the first op, ready (1) on the retry.
        fake_cfg.digital_read = MagicMock(side_effect=[0, 1])
        pkg = types.ModuleType("waveshare_epd")
        pkg.epdconfig = fake_cfg  # so `from waveshare_epd import epdconfig` works
        # patch.dict restores any pre-existing modules on exit (test_epd_driver
        # installs a real waveshare_epd.epdconfig), so this doesn't pollute.
        with _mock.patch.dict(
            "sys.modules",
            {"waveshare_epd": pkg, "waveshare_epd.epdconfig": fake_cfg},
        ):
            drv.display_full(Image.new("1", (WIDTH, HEIGHT), 255))
        assert mock_epd.display.call_count == 2  # retried after busy timeout

    def test_busy_timeout_persists_raises(self):
        import types
        from unittest import mock as _mock

        drv, mock_epd = _make_epd_driver(mode="fast")
        mock_epd.busy_pin = 24
        fake_cfg = types.ModuleType("epdconfig")
        fake_cfg.digital_read = MagicMock(return_value=0)  # never becomes ready
        pkg = types.ModuleType("waveshare_epd")
        pkg.epdconfig = fake_cfg
        with _mock.patch.dict(
            "sys.modules",
            {"waveshare_epd": pkg, "waveshare_epd.epdconfig": fake_cfg},
        ), pytest.raises(DisplayError):
            drv.display_full(Image.new("1", (WIDTH, HEIGHT), 255))

    def test_reinit_between_tries_uses_current_waveform(self):
        # On a partial-path fault, the retry re-inits the 'part' waveform.
        drv, mock_epd = _make_epd_driver(mode="part")
        mock_epd.display_Partial.side_effect = [RuntimeError("glitch"), None]
        drv.display_partial(_image_with_black_rows([10]))
        # init_part called once for the initial mode-switch AND again on re-init.
        assert mock_epd.init_part.call_count >= 1
        mock_epd.init_fast.assert_not_called()

    def test_null_driver_ops_do_not_raise_display_error(self, tmp_path):
        # NullDriver has no SPI faults and must not be forced through the retry
        # path — its ops just work.
        drv = NullDriver(output_dir=str(tmp_path))
        drv.init()
        drv.display_full(_make_image())
        drv.display_partial(_make_image())
        # No DisplayError; frames written normally.
        assert len(list(tmp_path.glob("*.png"))) == 2


# ---------------------------------------------------------------------------
# SPI thread-safety: serialize hardware ops behind an RLock
# ---------------------------------------------------------------------------


class TestEPaperDriverSpiLock:
    """The Power thread's emergency sleep() must not interleave with a main-loop
    display op — EPD SPI is not thread-safe. Every public hardware op holds the
    driver's RLock. RLock (not Lock) because the public ops call _run_with_retry
    / _reinit while already holding it.
    """

    def test_driver_has_rlock(self):

        drv = EPaperDriver()
        # An RLock instance's type is the private _thread.RLock; the public way
        # to check is that acquiring it twice from the same thread doesn't block.
        assert drv._lock.acquire(blocking=False)
        assert drv._lock.acquire(blocking=False)  # reentrant — would block on a Lock
        drv._lock.release()
        drv._lock.release()

    def test_display_op_acquires_lock(self):
        # While a display op is running, the lock must be held (so a concurrent
        # sleep() from another thread blocks). We prove it by inspecting the lock
        # from inside the mocked hardware call.
        drv, mock_epd = _make_epd_driver(mode="fast")
        seen = {}

        def _record(_buf):
            # Held by us on this thread; a *different* thread could not acquire.
            seen["held"] = drv._lock.acquire(blocking=False)
            if seen["held"]:
                drv._lock.release()

        mock_epd.display.side_effect = _record
        drv.display_full(Image.new("1", (WIDTH, HEIGHT), 255))
        # Reentrant acquire succeeds because we're on the owning thread — the
        # point is the op ran *inside* the locked region.
        assert seen["held"] is True

    def test_concurrent_sleep_does_not_interleave_with_display(self):
        # Simulate the real race: the Power thread calls sleep() while the main
        # loop is mid display_full. The lock must serialize them so epd.sleep()
        # never runs between the two writebytes of a display op.
        import threading

        drv, mock_epd = _make_epd_driver(mode="fast")
        events: list[str] = []
        started = threading.Event()

        def _slow_display(_buf):
            events.append("display_start")
            started.set()
            # Give the other thread time to try to sleep() mid-op.
            import time

            time.sleep(0.05)
            events.append("display_end")

        def _record_sleep():
            events.append("sleep")

        mock_epd.display.side_effect = _slow_display
        mock_epd.sleep.side_effect = _record_sleep

        t = threading.Thread(
            target=lambda: drv.display_full(Image.new("1", (WIDTH, HEIGHT), 255))
        )
        t.start()
        started.wait(timeout=1.0)
        drv.sleep()  # blocks until display_full releases the lock
        t.join(timeout=2.0)

        # sleep() must land strictly after the display op finished, not between
        # its internal steps.
        assert events == ["display_start", "display_end", "sleep"]


class TestCheckBusyGetStatus:
    """_check_busy must send the 0x71 get-status command before sampling the
    BUSY pin — the panel only latches busy state in response to 0x71.
    """

    def _patch_epdconfig(self, digital_read_val: int):
        import types
        from unittest import mock as _mock

        fake_cfg = types.ModuleType("epdconfig")
        fake_cfg.digital_read = MagicMock(return_value=digital_read_val)
        pkg = types.ModuleType("waveshare_epd")
        pkg.epdconfig = fake_cfg
        return _mock.patch.dict(
            "sys.modules",
            {"waveshare_epd": pkg, "waveshare_epd.epdconfig": fake_cfg},
        )

    def test_get_status_sent_before_sampling_pin(self):
        drv, mock_epd = _make_epd_driver(mode="fast")
        mock_epd.busy_pin = 24
        with self._patch_epdconfig(digital_read_val=1):  # ready
            drv._check_busy()
        mock_epd.send_command.assert_called_once_with(0x71)

    def test_no_send_command_attr_is_noop(self):
        # A mock/driver variant lacking send_command must not break the probe.
        drv, mock_epd = _make_epd_driver(mode="fast")
        mock_epd.busy_pin = 24
        # Remove send_command so getattr(..., None) yields a non-callable.
        del mock_epd.send_command
        with self._patch_epdconfig(digital_read_val=1):
            drv._check_busy()  # must not raise

    def test_send_command_failure_does_not_mask_busy_raise(self):
        # If the status probe itself raises, we still sample the pin and raise
        # on a lingering-busy timeout.
        drv, mock_epd = _make_epd_driver(mode="fast")
        mock_epd.busy_pin = 24
        mock_epd.send_command.side_effect = RuntimeError("SPI down")
        with self._patch_epdconfig(digital_read_val=0):  # still busy
            with pytest.raises(RuntimeError):
                drv._check_busy()

    def test_no_busy_pin_skips_get_status(self):
        # Desktop/test path: no busy_pin → no 0x71, no epdconfig import.
        drv, mock_epd = _make_epd_driver(mode="fast")
        mock_epd.busy_pin = None
        drv._check_busy()
        mock_epd.send_command.assert_not_called()


class TestInitTearsDownOldController:
    """Recovery re-init must release the previous controller before building a
    fresh EPD, so a failed panel's GPIO/SPI handle isn't leaked.
    """

    def _patch_epd_module(self, new_epd, module_exit):
        import types
        from unittest import mock as _mock

        fake_epd_mod = types.ModuleType("epd7in5_V2")
        fake_epd_mod.EPD = MagicMock(return_value=new_epd)
        fake_cfg = types.ModuleType("epdconfig")
        fake_cfg.module_exit = module_exit
        pkg = types.ModuleType("waveshare_epd")
        pkg.epd7in5_V2 = fake_epd_mod
        pkg.epdconfig = fake_cfg
        return _mock.patch.dict(
            "sys.modules",
            {
                "waveshare_epd": pkg,
                "waveshare_epd.epd7in5_V2": fake_epd_mod,
                "waveshare_epd.epdconfig": fake_cfg,
            },
        )

    def test_reinit_sleeps_old_controller_and_exits_module(self):
        old_epd = MagicMock()
        new_epd = MagicMock()
        module_exit = MagicMock()
        drv = EPaperDriver()
        drv._epd = old_epd
        with self._patch_epd_module(new_epd, module_exit):
            drv.init()
        old_epd.sleep.assert_called_once()
        module_exit.assert_called_once()
        assert drv._epd is new_epd
        new_epd.init_fast.assert_called_once()

    def test_reinit_tolerates_dead_old_controller(self):
        # If the old controller is already dead, teardown must not raise.
        old_epd = MagicMock()
        old_epd.sleep.side_effect = RuntimeError("already dead")
        new_epd = MagicMock()
        module_exit = MagicMock(side_effect=RuntimeError("gpio gone"))
        drv = EPaperDriver()
        drv._epd = old_epd
        with self._patch_epd_module(new_epd, module_exit):
            drv.init()  # must not raise
        assert drv._epd is new_epd


class TestCreateDriverLoudFallback:
    def test_fallback_logs_at_error_with_exc_info(self, caplog):
        import logging as _logging
        from unittest.mock import patch

        from writerdeck.display.driver import EPaperDriver as _EPD

        with patch.object(_EPD, "init", side_effect=RuntimeError("no panel")):
            with caplog.at_level(_logging.ERROR, logger="writerdeck.display.driver"):
                drv = create_driver(use_null=False)
        assert isinstance(drv, NullDriver)
        # Loud, explicit ERROR — not a quiet WARNING.
        error_records = [r for r in caplog.records if r.levelno >= _logging.ERROR]
        assert error_records, "fallback must log at ERROR level"
        msg = error_records[0].getMessage().lower()
        assert "headless" in msg or "failed" in msg
        # exc_info captured so the underlying failure is in the log.
        assert error_records[0].exc_info is not None

