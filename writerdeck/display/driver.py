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
    def wake(self) -> None: ...
    def display_full(self, image: Image.Image) -> None: ...
    def display_clean(self, image: Image.Image) -> None: ...
    def display_partial(self, image: Image.Image) -> None: ...
    def sleep(self) -> None: ...
    def close(self) -> None: ...


class EPaperDriver:
    """Real Waveshare EPD driver — only works on Raspberry Pi with SPI enabled."""

    # When more than this fraction of rows change, display_partial escalates to
    # a fast full refresh (init_fast + display) instead of a bounding-box partial
    # (init_part + display_Partial). This avoids ghosting on large updates like
    # scrolling or mode switches, while keeping the ~0.3s partial path for typing.
    PARTIAL_ESCALATE_THRESHOLD = 0.3

    def __init__(self) -> None:
        self._epd = None
        self._mode: str | None = None  # 'full' | 'fast' | 'part' | None (after sleep)
        self._last_buf: bytes | None = None  # last buffer sent to display

    def init(self) -> None:
        from waveshare_epd import epd7in5_V2  # type: ignore[import-untyped]
        self._epd = epd7in5_V2.EPD()
        self._epd.init()
        self._epd.Clear()
        self._mode = "full"
        self._last_buf = None
        logger.info("EPaperDriver initialized (%dx%d)", WIDTH, HEIGHT)

    def display_full(self, image: Image.Image) -> None:
        """Fast full refresh (~1s, 2-3 blink cycles). Use for streak/idle cleans."""
        assert self._epd is not None
        if self._mode != "fast":
            self._epd.init_fast()
            self._mode = "fast"
        buf = self._epd.getbuffer(image)
        self._epd.display(buf)
        self._last_buf = buf

    def display_clean(self, image: Image.Image) -> None:
        """GC16 deep clean (~3-4s, many blink cycles). Eliminates accumulated ghosting.
        Use sparingly — only after extended idle when the user is away from the desk.
        """
        assert self._epd is not None
        # Always re-init with the full GC16 waveform, regardless of current mode.
        self._epd.init()
        self._mode = "full"
        buf = self._epd.getbuffer(image)
        self._epd.display(buf)
        self._last_buf = buf
        logger.info("EPaperDriver GC16 deep clean")

    def display_partial(self, image: Image.Image) -> None:
        assert self._epd is not None
        buf = self._epd.getbuffer(image)

        if self._last_buf is not None:
            # Diff against last displayed frame: find bounding box and count
            # changed rows in a single pass.
            row_bytes = WIDTH // 8  # 100 bytes per row
            y_start: int | None = None
            y_end = 0
            changed_rows = 0
            for y in range(HEIGHT):
                offset = y * row_bytes
                if buf[offset : offset + row_bytes] != self._last_buf[offset : offset + row_bytes]:
                    if y_start is None:
                        y_start = y
                    y_end = y + 1
                    changed_rows += 1

            if y_start is None:
                return  # nothing changed — skip refresh entirely

            if changed_rows / HEIGHT > self.PARTIAL_ESCALATE_THRESHOLD:
                # Large update (scroll, mode switch, paste) — fast full refresh
                # avoids ghosting that a wide bounding-box partial would leave.
                if self._mode != "fast":
                    self._epd.init_fast()
                    self._mode = "fast"
                self._epd.display(buf)
                self._last_buf = buf
            else:
                if self._mode != "part":
                    self._epd.init_part()
                    self._mode = "part"
                # display_Partial sets CDI register to 0xA9, which inverts pixel
                # polarity vs full/fast mode (CDI 0x10). Compensate by inverting
                # the slice before sending so white=0xFF, black=0x00 at the wire.
                partial_slice = bytes(
                    b ^ 0xFF for b in buf[y_start * row_bytes : y_end * row_bytes]
                )
                self._epd.display_Partial(partial_slice, 0, y_start, WIDTH, y_end)
                self._last_buf = (
                    self._last_buf[: y_start * row_bytes]
                    + buf[y_start * row_bytes : y_end * row_bytes]
                    + self._last_buf[y_end * row_bytes :]
                )
        else:
            # No reference frame — fall back to fast full refresh.
            if self._mode != "fast":
                self._epd.init_fast()
                self._mode = "fast"
            self._epd.display(buf)
            self._last_buf = buf

    def wake(self) -> None:
        """Re-initialise the controller after sleep without clearing the screen.

        E-ink retains its image without power, so there is no need to call
        Clear() — which causes a ~2s white flash. The caller must still force a
        full display() before attempting partial refreshes, because the
        controller RAM (DTM1/DTM2) is reset by the hardware init sequence.
        """
        assert self._epd is not None
        self._epd.init()
        self._mode = "full"
        # _last_buf is intentionally preserved: the physical screen still shows
        # what it was showing before sleep, so the diff reference remains valid.
        logger.info("EPaperDriver woken from sleep (no clear)")

    def sleep(self) -> None:
        if self._epd is not None:
            self._epd.sleep()
            self._mode = None  # hardware power cut — must re-init before next display
            # _last_buf preserved: e-ink retains its image without power
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

    def wake(self) -> None:
        self._sleeping = False
        logger.info("NullDriver woken from sleep")

    def display_full(self, image: Image.Image) -> None:
        self._save(image, "full")

    def display_clean(self, image: Image.Image) -> None:
        self._save(image, "clean")

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
