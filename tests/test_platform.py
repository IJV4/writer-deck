"""Tests for platform detection with mocked /proc/device-tree/model."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from writerdeck.utils.platform import HardwareProfile, detect_platform


class TestDetectPlatformPiZero2W:
    @patch.object(Path, "exists", return_value=True)
    @patch.object(Path, "read_text", return_value="Raspberry Pi Zero 2 W Rev 1.0\x00")
    def test_detects_pi_zero_2w(self, mock_read, mock_exists):
        hw = detect_platform()
        assert hw.name == "pi_zero_2w"
        assert hw.is_pi is True
        assert hw.is_pi_zero is True

    @patch.object(Path, "exists", return_value=True)
    @patch.object(Path, "read_text", return_value="Raspberry Pi Zero 2 W Rev 1.0\x00")
    def test_pi_zero_tuning(self, mock_read, mock_exists):
        hw = detect_platform()
        assert hw.partial_refresh_max_streak == 20
        assert hw.render_interval_ms == 500
        assert hw.font_size == 14


class TestDetectPlatformPi5:
    @patch.object(Path, "exists", return_value=True)
    @patch.object(Path, "read_text", return_value="Raspberry Pi 5 Model B Rev 1.0\x00")
    def test_detects_pi5(self, mock_read, mock_exists):
        hw = detect_platform()
        assert hw.name == "pi5"
        assert hw.is_pi is True
        assert hw.is_pi_zero is False

    @patch.object(Path, "exists", return_value=True)
    @patch.object(Path, "read_text", return_value="Raspberry Pi 5 Model B Rev 1.0\x00")
    def test_pi5_tuning(self, mock_read, mock_exists):
        hw = detect_platform()
        assert hw.partial_refresh_max_streak == 40
        assert hw.render_interval_ms == 200
        assert hw.font_size == 16


class TestDetectPlatformPiOther:
    @patch.object(Path, "exists", return_value=True)
    @patch.object(Path, "read_text", return_value="Raspberry Pi 4 Model B Rev 1.2\x00")
    def test_detects_other_pi(self, mock_read, mock_exists):
        hw = detect_platform()
        assert hw.name == "pi_other"
        assert hw.is_pi is True
        assert hw.is_pi_zero is False

    @patch.object(Path, "exists", return_value=True)
    @patch.object(Path, "read_text", return_value="Raspberry Pi 3 Model B+\x00")
    def test_pi3_also_matches(self, mock_read, mock_exists):
        hw = detect_platform()
        assert hw.name == "pi_other"
        assert hw.is_pi is True

    @patch.object(Path, "exists", return_value=True)
    @patch.object(Path, "read_text", return_value="Raspberry Pi 4 Model B Rev 1.2\x00")
    def test_other_pi_tuning(self, mock_read, mock_exists):
        hw = detect_platform()
        assert hw.partial_refresh_max_streak == 30
        assert hw.render_interval_ms == 300
        assert hw.font_size == 14


class TestDetectPlatformDesktop:
    @patch.object(Path, "exists", return_value=False)
    def test_no_model_file_is_desktop(self, mock_exists):
        hw = detect_platform()
        assert hw.name == "desktop"
        assert hw.is_pi is False
        assert hw.is_pi_zero is False

    @patch.object(Path, "exists", return_value=False)
    def test_desktop_tuning(self, mock_exists):
        hw = detect_platform()
        assert hw.partial_refresh_max_streak == 50
        assert hw.render_interval_ms == 100
        assert hw.font_size == 16

    @patch.object(Path, "exists", return_value=True)
    @patch.object(Path, "read_text", return_value="Some Unknown Board\x00")
    def test_unknown_board_is_desktop(self, mock_read, mock_exists):
        hw = detect_platform()
        assert hw.name == "desktop"
        assert hw.is_pi is False

    @patch.object(Path, "exists", return_value=True)
    @patch.object(Path, "read_text", return_value="")
    def test_empty_model_file_is_desktop(self, mock_read, mock_exists):
        hw = detect_platform()
        assert hw.name == "desktop"


class TestHardwareProfileDataclass:
    def test_fields_accessible(self):
        hw = HardwareProfile(
            name="test", is_pi=True, is_pi_zero=False,
            partial_refresh_max_streak=10, render_interval_ms=50, font_size=12,
        )
        assert hw.name == "test"
        assert hw.is_pi is True
        assert hw.is_pi_zero is False
        assert hw.partial_refresh_max_streak == 10
        assert hw.render_interval_ms == 50
        assert hw.font_size == 12

    def test_equality(self):
        a = HardwareProfile("x", True, False, 10, 50, 12)
        b = HardwareProfile("x", True, False, 10, 50, 12)
        assert a == b

    def test_inequality(self):
        a = HardwareProfile("x", True, False, 10, 50, 12)
        b = HardwareProfile("y", True, False, 10, 50, 12)
        assert a != b


class TestModelStringEdgeCases:
    @patch.object(Path, "exists", return_value=True)
    @patch.object(Path, "read_text", return_value="RASPBERRY PI ZERO 2 W REV 1.0")
    def test_case_insensitive_matching(self, mock_read, mock_exists):
        hw = detect_platform()
        assert hw.name == "pi_zero_2w"

    @patch.object(Path, "exists", return_value=True)
    @patch.object(Path, "read_text", return_value="  Raspberry Pi 5 Model B  \n")
    def test_whitespace_stripped(self, mock_read, mock_exists):
        hw = detect_platform()
        assert hw.name == "pi5"

    @patch.object(Path, "exists", return_value=True)
    @patch.object(Path, "read_text", return_value="raspberry pi zero 2 w\x00\x00\x00")
    def test_null_bytes_in_model(self, mock_read, mock_exists):
        hw = detect_platform()
        assert hw.name == "pi_zero_2w"
