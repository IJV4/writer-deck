"""Tests for the vendored Waveshare epd7in5_V2 display driver.

epdconfig.py executes hardware detection at module level (subprocess + GPIO
instantiation), which fails on desktop. We intercept it by injecting a mock
into sys.modules before importing EPD. All hardware calls go to the mock,
letting us test the driver's pure logic in isolation.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

# ---------------------------------------------------------------------------
# Bootstrap: add lib/ to sys.path and mock epdconfig before EPD is imported.
# ---------------------------------------------------------------------------
_LIB = Path(__file__).parent.parent / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

_mock_cfg = MagicMock()
_mock_cfg.RST_PIN = 17
_mock_cfg.DC_PIN = 25
_mock_cfg.CS_PIN = 8
_mock_cfg.BUSY_PIN = 24
_mock_cfg.module_init.return_value = 0
_mock_cfg.digital_read.return_value = 1  # default: not busy

# Only mock epdconfig — let Python find the real waveshare_epd package via _LIB.
# Setting waveshare_epd itself to a MagicMock would block submodule resolution.
sys.modules["waveshare_epd.epdconfig"] = _mock_cfg

from waveshare_epd.epd7in5_V2 import EPD, EPD_HEIGHT, EPD_WIDTH  # noqa: E402

BUF_SIZE = EPD_WIDTH // 8 * EPD_HEIGHT  # 48 000 bytes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _img(color: int = 0) -> Image.Image:
    """Create a solid 800×480 1-bit image. color=0 → black, 1 → white."""
    return Image.new("1", (EPD_WIDTH, EPD_HEIGHT), color)


def _sent_bytes() -> list[int]:
    """All bytes sent via spi_writebyte (commands + single-byte data)."""
    return [c.args[0][0] for c in _mock_cfg.spi_writebyte.call_args_list]


def _bulk_sends() -> list:
    """All bulk buffers sent via SPI.writebytes2, in order."""
    return [c.args[0] for c in _mock_cfg.SPI.writebytes2.call_args_list]


@pytest.fixture()
def epd() -> EPD:
    """Fresh EPD instance with a clean mock call history for each test."""
    _mock_cfg.reset_mock()
    _mock_cfg.module_init.return_value = 0
    _mock_cfg.digital_read.return_value = 1
    _mock_cfg.digital_read.side_effect = None
    return EPD()


# ---------------------------------------------------------------------------
# getbuffer
# ---------------------------------------------------------------------------

class TestGetBuffer:
    def test_black_image_produces_all_ones(self, epd):
        # PIL black (0) → e-paper black (0xFF = all pixels set)
        buf = epd.getbuffer(_img(0))
        assert all(b == 0xFF for b in buf)

    def test_white_image_produces_all_zeros(self, epd):
        # PIL white (1) → e-paper white (0x00 = all pixels clear)
        buf = epd.getbuffer(_img(1))
        assert all(b == 0x00 for b in buf)

    def test_buffer_size_is_correct(self, epd):
        assert len(epd.getbuffer(_img())) == BUF_SIZE

    def test_return_type_is_bytes(self, epd):
        assert isinstance(epd.getbuffer(_img()), bytes)

    def test_wrong_dimensions_returns_bytes(self, epd):
        buf = epd.getbuffer(Image.new("1", (10, 10)))
        assert isinstance(buf, bytes)

    def test_wrong_dimensions_returns_correct_size(self, epd):
        buf = epd.getbuffer(Image.new("1", (10, 10)))
        assert len(buf) == BUF_SIZE

    def test_rotated_dimensions_accepted(self, epd):
        # 480×800 (height×width) should be auto-rotated and accepted
        buf = epd.getbuffer(Image.new("1", (EPD_HEIGHT, EPD_WIDTH), 0))
        assert len(buf) == BUF_SIZE
        assert isinstance(buf, bytes)

    def test_inversion_is_bitwise_complement(self, epd):
        # Every byte in black-image buffer XOR white-image buffer must be 0xFF
        black = epd.getbuffer(_img(0))
        white = epd.getbuffer(_img(1))
        assert all(a ^ b == 0xFF for a, b in zip(black, white))


# ---------------------------------------------------------------------------
# display — full-screen refresh
# ---------------------------------------------------------------------------

class TestDisplay:
    def test_dtm1_receives_inverted_image(self, epd):
        # DTM1 (cmd 0x10, old-frame data) must be the bitwise inverse of the buffer.
        buf = epd.getbuffer(_img(0))   # all-black → 0xFF bytes
        epd.display(buf)
        dtm1 = _bulk_sends()[0]
        assert all(b == 0x00 for b in dtm1)   # 0xFF ^ 0xFF = 0x00

    def test_dtm2_receives_original_image(self, epd):
        # DTM2 (cmd 0x13, new-frame data) must be the buffer unchanged.
        buf = epd.getbuffer(_img(0))
        epd.display(buf)
        dtm2 = _bulk_sends()[1]
        assert bytes(dtm2) == buf

    def test_dtm1_sent_before_dtm2(self, epd):
        epd.display(epd.getbuffer(_img()))
        cmds = _sent_bytes()
        assert cmds.index(0x10) < cmds.index(0x13)

    def test_master_activation_sent(self, epd):
        epd.display(epd.getbuffer(_img()))
        assert 0x12 in _sent_bytes()


# ---------------------------------------------------------------------------
# ReadBusy — busy-pin polling with timeout
# ---------------------------------------------------------------------------

class TestReadBusy:
    def test_exits_immediately_when_pin_high(self, epd):
        _mock_cfg.digital_read.return_value = 1
        epd.ReadBusy()
        assert _mock_cfg.digital_read.call_count == 1

    def test_loops_until_pin_goes_high(self, epd):
        _mock_cfg.digital_read.side_effect = [0, 0, 0, 1]
        epd.ReadBusy()
        assert _mock_cfg.digital_read.call_count == 4

    def test_times_out_after_5000ms(self, epd):
        # delay_ms is mocked (no-op), so 500 × 10ms iterations run instantly.
        _mock_cfg.digital_read.return_value = 0
        epd.ReadBusy()
        # 1 call before loop + 500 calls inside loop = 501 total
        assert _mock_cfg.digital_read.call_count == 501

    def test_timeout_logs_warning(self, epd, caplog):
        _mock_cfg.digital_read.return_value = 0
        with caplog.at_level(logging.WARNING, logger="waveshare_epd.epd7in5_V2"):
            epd.ReadBusy()
        assert "timed out" in caplog.text.lower()


# ---------------------------------------------------------------------------
# display_Partial — bounding-box update
# ---------------------------------------------------------------------------

class TestDisplayPartial:
    def _buf(self, size: int = BUF_SIZE, val: int = 0xAB) -> bytes:
        return bytes([val] * size)

    def test_full_screen_sends_correct_byte_count(self, epd):
        epd.display_Partial(self._buf(), 0, 0, EPD_WIDTH, EPD_HEIGHT)
        assert len(_bulk_sends()[0]) == BUF_SIZE

    def test_partial_region_sends_correct_byte_count(self, epd):
        # 400 px wide × 240 px tall → Width = 50 bytes, Height = 240 → 12 000 bytes
        epd.display_Partial(self._buf(50 * 240), 0, 0, 400, 240)
        assert len(_bulk_sends()[0]) == 50 * 240

    def test_data_sent_unmodified(self, epd):
        # Fixes the old double-inversion bug: data must arrive unchanged.
        pattern = bytes(range(256)) * (BUF_SIZE // 256)
        epd.display_Partial(pattern, 0, 0, EPD_WIDTH, EPD_HEIGHT)
        assert bytes(_bulk_sends()[0]) == pattern[:BUF_SIZE]

    def test_partial_mode_enter_command_sent(self, epd):
        epd.display_Partial(self._buf(), 0, 0, EPD_WIDTH, EPD_HEIGHT)
        assert 0x91 in _sent_bytes()   # enter partial mode

    def test_window_resolution_command_sent(self, epd):
        epd.display_Partial(self._buf(), 0, 0, EPD_WIDTH, EPD_HEIGHT)
        assert 0x90 in _sent_bytes()   # resolution / window setting

    def test_dtm2_command_sent(self, epd):
        epd.display_Partial(self._buf(), 0, 0, EPD_WIDTH, EPD_HEIGHT)
        assert 0x13 in _sent_bytes()

    def test_master_activation_sent(self, epd):
        epd.display_Partial(self._buf(), 0, 0, EPD_WIDTH, EPD_HEIGHT)
        assert 0x12 in _sent_bytes()

    def test_window_end_coordinates_sent(self, epd):
        # (800-1) = 799 → high byte 3, low byte 31
        # (480-1) = 479 → high byte 1, low byte 223
        epd.display_Partial(self._buf(), 0, 0, EPD_WIDTH, EPD_HEIGHT)
        sent = _sent_bytes()
        assert 3 in sent    # (EPD_WIDTH - 1) // 256
        assert 31 in sent   # (EPD_WIDTH - 1) % 256
        assert 1 in sent    # (EPD_HEIGHT - 1) // 256
        assert 223 in sent  # (EPD_HEIGHT - 1) % 256


# ---------------------------------------------------------------------------
# Init modes
# ---------------------------------------------------------------------------

class TestInitModes:
    def test_init_returns_zero_on_success(self, epd):
        assert epd.init() == 0

    def test_init_fast_returns_zero(self, epd):
        assert epd.init_fast() == 0

    def test_init_part_returns_zero(self, epd):
        assert epd.init_part() == 0

    def test_init_returns_minus_one_on_module_failure(self, epd):
        _mock_cfg.module_init.return_value = -1
        assert epd.init() == -1

    def test_init_sends_power_on(self, epd):
        epd.init()
        assert 0x04 in _sent_bytes()   # POWER ON command

    def test_init_fast_sets_fast_waveform(self, epd):
        epd.init_fast()
        cmds = _sent_bytes()
        idx = cmds.index(0xE5)         # waveform mode register
        assert cmds[idx + 1] == 0x5A  # fast waveform value

    def test_init_part_sets_partial_waveform(self, epd):
        epd.init_part()
        cmds = _sent_bytes()
        idx = cmds.index(0xE5)
        assert cmds[idx + 1] == 0x6E  # partial waveform value
