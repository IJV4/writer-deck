"""Tests for the vendored epdconfig.py hardware interface.

epdconfig.py runs hardware detection at module level, so we load it via
importlib with subprocess and GPIO dependencies patched out. This lets us
test the RaspberryPi class methods — especially the bugs we fixed — without
real hardware.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_LIB = Path(__file__).parent.parent / "lib"
_EPDCONFIG = _LIB / "waveshare_epd" / "epdconfig.py"


def _load_as_raspberry_pi():
    """
    Load epdconfig.py in a controlled environment that looks like a Pi.

    Patches:
    - subprocess.Popen  → returns 'Raspberry Pi' so RaspberryPi() is chosen
    - spidev            → mock so SpiDev() doesn't need hardware
    - gpiozero          → mock so LED/Button don't need GPIO
    """
    mock_spi = MagicMock()
    mock_gpio = MagicMock()

    spec = importlib.util.spec_from_file_location("_epdconfig_test_isolated", _EPDCONFIG)
    module = importlib.util.module_from_spec(spec)
    # Must be in sys.modules before exec so setattr(sys.modules[__name__], ...)
    # inside epdconfig works correctly.
    sys.modules["_epdconfig_test_isolated"] = module

    try:
        with (
            patch.dict("sys.modules", {"spidev": mock_spi, "gpiozero": mock_gpio}),
            patch("subprocess.Popen") as mock_popen,
        ):
            mock_popen.return_value.communicate.return_value = ("Raspberry Pi Zero 2 W", None)
            spec.loader.exec_module(module)
    finally:
        del sys.modules["_epdconfig_test_isolated"]

    return module, mock_spi, mock_gpio


@pytest.fixture(scope="module")
def rpi_module():
    return _load_as_raspberry_pi()


@pytest.fixture()
def rpi(rpi_module):
    """RaspberryPi instance with reset mock history for each test."""
    module, mock_spi, mock_gpio = rpi_module
    mock_spi.reset_mock()
    mock_gpio.reset_mock()
    return module.implementation


# ---------------------------------------------------------------------------
# digital_write
# ---------------------------------------------------------------------------

class TestDigitalWrite:
    def test_rst_pin_on(self, rpi):
        rpi.digital_write(rpi.RST_PIN, 1)
        rpi.GPIO_RST_PIN.on.assert_called_once()

    def test_rst_pin_off(self, rpi):
        rpi.digital_write(rpi.RST_PIN, 0)
        rpi.GPIO_RST_PIN.off.assert_called_once()

    def test_dc_pin_on(self, rpi):
        rpi.digital_write(rpi.DC_PIN, 1)
        rpi.GPIO_DC_PIN.on.assert_called_once()

    def test_dc_pin_off(self, rpi):
        rpi.digital_write(rpi.DC_PIN, 0)
        rpi.GPIO_DC_PIN.off.assert_called_once()

    def test_pwr_pin_on(self, rpi):
        rpi.digital_write(rpi.PWR_PIN, 1)
        rpi.GPIO_PWR_PIN.on.assert_called_once()


# ---------------------------------------------------------------------------
# digital_read — verifies the RST/DC attribute bug fix
# ---------------------------------------------------------------------------

class TestDigitalRead:
    def test_busy_pin_returns_button_value(self, rpi):
        rpi.GPIO_BUSY_PIN.value = 1
        assert rpi.digital_read(rpi.BUSY_PIN) == 1

    def test_busy_pin_returns_zero_when_low(self, rpi):
        rpi.GPIO_BUSY_PIN.value = 0
        assert rpi.digital_read(rpi.BUSY_PIN) == 0

    def test_rst_pin_returns_gpio_object_value(self, rpi):
        # Bug fix: was `return self.RST_PIN.value` (int has no .value → AttributeError).
        # Now: `return self.GPIO_RST_PIN.value`.
        rpi.GPIO_RST_PIN.value = 1
        assert rpi.digital_read(rpi.RST_PIN) == 1

    def test_dc_pin_returns_gpio_object_value(self, rpi):
        # Same bug applied to DC_PIN.
        rpi.GPIO_DC_PIN.value = 0
        assert rpi.digital_read(rpi.DC_PIN) == 0


# ---------------------------------------------------------------------------
# module_init
# ---------------------------------------------------------------------------

class TestModuleInit:
    def test_returns_zero_on_success(self, rpi):
        assert rpi.module_init() == 0

    def test_opens_spi_bus(self, rpi):
        rpi.module_init()
        rpi.SPI.open.assert_called_with(0, 0)

    def test_sets_spi_speed(self, rpi):
        rpi.module_init()
        assert rpi.SPI.max_speed_hz == 4_000_000

    def test_sets_spi_mode(self, rpi):
        rpi.module_init()
        assert rpi.SPI.mode == 0b00
