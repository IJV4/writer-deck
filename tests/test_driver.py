"""Tests for NullDriver."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from writerdeck.display.driver import NullDriver, create_driver, WIDTH, HEIGHT


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
