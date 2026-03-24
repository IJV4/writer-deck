"""E-ink display driver — wraps Waveshare epd7in5_V2 with a NullDriver fallback."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from PIL import Image

logger = logging.getLogger(__name__)

WIDTH = 800
HEIGHT = 480


class DisplayDriver(Protocol):
    def init(self) -> None: ...
    def display_full(self, image: Image.Image) -> None: ...
    def display_partial(self, image: Image.Image) -> None: ...
    def sleep(self) -> None: ...
    def close(self) -> None: ...


class EPaperDriver:
    """Real Waveshare EPD driver — only works on Raspberry Pi with SPI enabled."""

    def __init__(self) -> None:
        self._epd = None

    def init(self) -> None:
        from waveshare_epd import epd7in5_V2  # type: ignore[import-untyped]
        self._epd = epd7in5_V2.EPD()
        self._epd.init()
        self._epd.Clear()
        logger.info("EPaperDriver initialized (%dx%d)", WIDTH, HEIGHT)

    def display_full(self, image: Image.Image) -> None:
        assert self._epd is not None
        self._epd.display(self._epd.getbuffer(image))

    def display_partial(self, image: Image.Image) -> None:
        assert self._epd is not None
        # Waveshare 7.5" V2 doesn't natively support partial refresh through
        # the stock Python driver — we do a full refresh but can keep the call
        # signature consistent for future hardware that supports it.
        self._epd.display(self._epd.getbuffer(image))

    def sleep(self) -> None:
        if self._epd is not None:
            self._epd.sleep()
            logger.info("EPaperDriver sleeping")

    def close(self) -> None:
        if self._epd is not None:
            self._epd.Clear()
        self.sleep()


class NullDriver:
    """Development fallback — saves rendered frames as PNGs to /tmp."""

    def __init__(self, output_dir: str = "/tmp/writer-deck") -> None:
        self._output_dir = Path(output_dir)
        self._frame_num = 0
        self._sleeping = False

    def init(self) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._sleeping = False
        logger.info("NullDriver initialized → %s", self._output_dir)

    def display_full(self, image: Image.Image) -> None:
        self._save(image, "full")

    def display_partial(self, image: Image.Image) -> None:
        self._save(image, "partial")

    def sleep(self) -> None:
        self._sleeping = True
        logger.info("NullDriver sleeping")

    def close(self) -> None:
        self.sleep()

    def _save(self, image: Image.Image, kind: str) -> None:
        self._sleeping = False
        path = self._output_dir / f"frame_{self._frame_num:04d}_{kind}.png"
        image.save(str(path))
        self._frame_num += 1
        logger.debug("NullDriver saved %s", path)


def create_driver(use_null: bool = False) -> DisplayDriver:
    if use_null:
        return NullDriver()
    try:
        drv = EPaperDriver()
        drv.init()
        return drv
    except Exception:
        logger.warning("EPaperDriver unavailable, falling back to NullDriver")
        drv_null = NullDriver()
        drv_null.init()
        return drv_null
