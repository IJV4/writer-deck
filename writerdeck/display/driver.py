"""E-ink display driver — wraps Waveshare epd7in5_V2 with a NullDriver fallback."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Protocol

from PIL import Image

logger = logging.getLogger(__name__)

WIDTH = 800
HEIGHT = 480

# FAULT-6: number of attempts (1 initial + retries) for each hardware display op.
# The current waveform is re-initialised between tries. On repeated failure the
# op raises DisplayError, which the app catches to skip the frame / degrade to a
# headless state (FAULT-7) rather than crash.
DISPLAY_OP_ATTEMPTS = 3


class DisplayError(Exception):
    """Raised when a display op fails after all bounded retries (FAULT-6).

    A specific signal so the app-level render path (FAULT-7) can distinguish a
    dead/glitchy panel from an ordinary bug and degrade to headless instead of
    crashing. Hardware-free drivers (Null/Pygame) never raise this.
    """

# When merging changed row-bands, bands separated by a vertical gap of at most
# this many *unchanged* rows are coalesced into one windowed refresh; larger gaps
# split into separate windows so we don't sweep the unchanged middle (e.g. the
# cursor line at ~row 100 vs the footer at ~row 462). Keeping the number small
# means adjacent glyph edits still merge, while distant regions stay disjoint.
BAND_MERGE_GAP = 32


def compute_dirty_bands(
    old_buf: bytes,
    new_buf: bytes,
    height: int,
    row_bytes: int,
    gap: int = BAND_MERGE_GAP,
) -> tuple[list[tuple[int, int]], int]:
    """Diff two e-paper row buffers into a list of disjoint changed row-bands.

    Pure and hardware-free so it can be unit-tested with plain buffers. Does a
    single pass over the rows, grouping runs of changed rows into ``(y_start,
    y_end)`` half-open bands. Bands separated by ``<= gap`` unchanged rows are
    merged into one band; larger gaps split into separate bands.

    Returns ``(bands, changed_rows)`` where ``changed_rows`` is the total count
    of differing rows across all bands (used by the caller for the escalation
    threshold — this is deliberately independent of the merged band spans).
    """
    bands: list[tuple[int, int]] = []
    changed_rows = 0
    cur_start: int | None = None
    cur_end = 0  # exclusive; end of the current (possibly gap-extended) band
    for y in range(height):
        offset = y * row_bytes
        if old_buf[offset : offset + row_bytes] != new_buf[offset : offset + row_bytes]:
            changed_rows += 1
            if cur_start is None:
                cur_start = y
            elif y - cur_end > gap:
                # Gap since the last changed row is too large — close the band.
                bands.append((cur_start, cur_end))
                cur_start = y
            cur_end = y + 1
    if cur_start is not None:
        bands.append((cur_start, cur_end))
    return bands, changed_rows


def compute_x_window(
    old_buf: bytes,
    new_buf: bytes,
    y_start: int,
    y_end: int,
    row_bytes: int,
) -> tuple[int, int]:
    """Compute the horizontal changed-column window for a band, in bytes.

    Pure/hardware-free. Scans rows ``[y_start, y_end)`` and returns the
    half-open *byte*-column range ``(col_start, col_end)`` covering every byte
    that differs between the buffers. Because each byte is 8 pixels, snapping to
    byte boundaries automatically aligns Xstart/Xend to 8-px boundaries as the
    panel requires. Returns ``(0, row_bytes)`` (full width) if the band somehow
    has no differing bytes, so the caller always sends a valid window.
    """
    col_start: int | None = None
    col_end = 0  # exclusive, in bytes
    for y in range(y_start, y_end):
        base = y * row_bytes
        for c in range(row_bytes):
            if old_buf[base + c] != new_buf[base + c]:
                if col_start is None or c < col_start:
                    col_start = c
                if c + 1 > col_end:
                    col_end = c + 1
    if col_start is None:
        return 0, row_bytes
    return col_start, col_end


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
        # Last buffer sent to display, held as a mutable bytearray so partial
        # updates can be spliced in place without reallocating 48000 bytes on
        # every keystroke (PERF-3). None after sleep-clear.
        self._last_buf: bytearray | None = None
        self._slept = False  # guards sleep()/close() against double-invocation
        # EPD SPI is not thread-safe: the Power thread's emergency path can call
        # sleep() while the main loop is mid display_partial/display_full. This
        # reentrant lock serializes every hardware op (and the retry/re-init that
        # public methods run while already holding it — hence RLock, not Lock).
        # It also protects the shared _last_buf / _mode / _slept state.
        self._lock = threading.RLock()

    def _reinit_current_waveform(self) -> None:
        """Re-run the init sequence for the CURRENT waveform (FAULT-6 retry).

        Called between retries so a transient SPI/CRC/busy glitch is followed by
        a fresh controller init before the op is attempted again. Reuses the same
        _mode-aware init calls as the normal path; leaves _mode unchanged (it
        already reflects the intended waveform). A None mode (post-sleep) re-inits
        with the full waveform.
        """
        assert self._epd is not None
        if self._mode == "part":
            self._epd.init_part()
        elif self._mode == "fast":
            self._epd.init_fast()
        else:
            self._epd.init()

    def _run_with_retry(self, op_name: str, op) -> None:
        """Run a hardware display op with bounded retries (FAULT-6).

        Attempts ``op`` up to DISPLAY_OP_ATTEMPTS times, re-initialising the
        current waveform between tries. A busy-timeout is surfaced by ``op``
        raising (see _check_busy), so it takes the retry path rather than being
        silently ignored. On repeated failure raises DisplayError so the caller
        (app render path, FAULT-7) can skip the frame / go headless.
        """
        last_exc: Exception | None = None
        with self._lock:
            for attempt in range(DISPLAY_OP_ATTEMPTS):
                try:
                    op()
                    return
                except DisplayError:
                    raise
                except Exception as exc:  # noqa: BLE001 — any SPI/CRC/busy fault
                    last_exc = exc
                    logger.warning(
                        "Display op %r failed (attempt %d/%d): %s",
                        op_name, attempt + 1, DISPLAY_OP_ATTEMPTS, exc,
                    )
                    if attempt + 1 < DISPLAY_OP_ATTEMPTS:
                        try:
                            self._reinit_current_waveform()
                        except Exception as reinit_exc:  # noqa: BLE001
                            logger.warning(
                                "Re-init before retry failed: %s", reinit_exc
                            )
        raise DisplayError(
            f"Display op {op_name!r} failed after {DISPLAY_OP_ATTEMPTS} attempts"
        ) from last_exc

    def _check_busy(self) -> None:
        """Treat a busy-pin timeout as a failed op (FAULT-6 policy).

        The vendored ``ReadBusy`` loops ``while busy == 0`` (0 = busy) and simply
        ``break``s after a 5 s timeout, leaving the pin still busy — and the stock
        driver ignores that. We re-read the busy pin once after an op: if it is
        still 0 the op did not complete, so we raise to enter the retry path
        instead of continuing with a half-updated panel. No-op if the busy pin /
        epdconfig aren't available (e.g. under a mock or a driver variant), so
        this never interferes with the desktop/test paths.
        """
        assert self._epd is not None
        busy_pin = getattr(self._epd, "busy_pin", None)
        if busy_pin is None:
            return
        try:
            from waveshare_epd import epdconfig  # type: ignore[import-untyped]
        except Exception:
            return
        # The panel latches its busy state only in response to a get-status
        # command (0x71) — the vendored ReadBusy always sends it before every
        # sample. Reading the pin cold (without 0x71) can return a stale value.
        # Best-effort: no-op on mocks / driver variants that lack send_command,
        # so the desktop/test paths are unaffected.
        send_command = getattr(self._epd, "send_command", None)
        if callable(send_command):
            try:
                send_command(0x71)
            except Exception:  # noqa: BLE001 — never let the status probe raise
                pass
        # 0 == busy in the vendored driver; a lingering 0 means ReadBusy timed out.
        if epdconfig.digital_read(busy_pin) == 0:
            raise RuntimeError("panel still BUSY after op (ReadBusy timeout)")

    def init(self) -> None:
        from waveshare_epd import epd7in5_V2  # type: ignore[import-untyped]
        with self._lock:
            # Recovery re-init: if a previous controller exists (e.g. a failed
            # panel being re-initialised), tear it down first so we don't leak
            # the old GPIO/SPI handle by constructing a fresh EPD on top of it.
            # Best-effort — must not raise if the old controller is already dead.
            if self._epd is not None:
                try:
                    self._epd.sleep()
                except Exception:  # noqa: BLE001 — old controller may be dead
                    pass
                try:
                    from waveshare_epd import epdconfig  # type: ignore[import-untyped]
                    epdconfig.module_exit()
                except Exception:  # noqa: BLE001 — best-effort teardown
                    pass
            self._epd = epd7in5_V2.EPD()
            self._epd.init_fast()
            self._mode = "fast"
            self._last_buf = None
            self._slept = False
            logger.info("EPaperDriver initialized (%dx%d)", WIDTH, HEIGHT)

    def display_full(self, image: Image.Image) -> None:
        """Fast full refresh (~1s, 2-3 blink cycles). Use for streak/idle cleans.

        FAULT-6: bounded-retry wrapped; raises DisplayError on repeated failure.
        """
        self._run_with_retry("display_full", lambda: self._do_display_full(image))

    def _do_display_full(self, image: Image.Image) -> None:
        assert self._epd is not None
        if self._mode != "fast":
            self._epd.init_fast()
            self._mode = "fast"
        buf = self._epd.getbuffer(image)
        self._epd.display(buf)
        self._check_busy()
        self._last_buf = bytearray(buf)

    def display_clean(self, image: Image.Image) -> None:
        """GC16 deep clean (~3-4s, many blink cycles). Eliminates accumulated ghosting.
        Use sparingly — only after extended idle when the user is away from the desk.

        FAULT-6: bounded-retry wrapped; raises DisplayError on repeated failure.
        """
        self._run_with_retry("display_clean", lambda: self._do_display_clean(image))

    def _do_display_clean(self, image: Image.Image) -> None:
        assert self._epd is not None
        # Always re-init with the full GC16 waveform, regardless of current mode.
        self._epd.init()
        self._mode = "full"
        buf = self._epd.getbuffer(image)
        self._epd.display(buf)
        self._check_busy()
        self._last_buf = bytearray(buf)
        logger.info("EPaperDriver GC16 deep clean")

    def display_partial(self, image: Image.Image) -> None:
        """Bounding-box partial refresh. FAULT-6: bounded-retry wrapped."""
        self._run_with_retry(
            "display_partial", lambda: self._do_display_partial(image)
        )

    def _do_display_partial(self, image: Image.Image) -> None:
        assert self._epd is not None
        buf = self._epd.getbuffer(image)
        row_bytes = WIDTH // 8  # 100 bytes per row

        if self._last_buf is not None:
            # Diff against last displayed frame into disjoint changed row-bands
            # (PERF-1). Distant regions — e.g. the cursor line vs a stats band —
            # become separate small windows instead of one giant merged box.
            bands, changed_rows = compute_dirty_bands(
                self._last_buf, buf, HEIGHT, row_bytes
            )

            if not bands:
                return  # nothing changed — skip refresh entirely

            if changed_rows / HEIGHT > self.PARTIAL_ESCALATE_THRESHOLD:
                # Large update (scroll, mode switch, paste) — fast full refresh
                # avoids ghosting that wide bounding-box partials would leave.
                if self._mode != "fast":
                    self._epd.init_fast()
                    self._mode = "fast"
                self._epd.display(buf)
                self._check_busy()
                self._last_buf = bytearray(buf)
            else:
                if self._mode != "part":
                    self._epd.init_part()
                    self._mode = "part"
                # Splice updates happen in place, so ensure the reference frame
                # is mutable (real code paths already store a bytearray).
                if not isinstance(self._last_buf, bytearray):
                    self._last_buf = bytearray(self._last_buf)
                for y_start, y_end in bands:
                    # Window in X too (PERF-2): only clock the changed columns.
                    col_start, col_end = compute_x_window(
                        self._last_buf, buf, y_start, y_end, row_bytes
                    )
                    x_start = col_start * 8
                    x_end = col_end * 8
                    # Slice the buffer to the band's row range AND column range,
                    # pre-inverting for the CDI 0xA9 polarity flip that
                    # display_Partial uses (white=0x00 → 0xFF at the wire). The
                    # inversion still applies to the windowed slice.
                    partial_slice = bytearray()
                    for y in range(y_start, y_end):
                        base = y * row_bytes
                        partial_slice.extend(
                            b ^ 0xFF for b in buf[base + col_start : base + col_end]
                        )
                    self._epd.display_Partial(
                        bytes(partial_slice), x_start, y_start, x_end, y_end
                    )
                    self._check_busy()
                    # Splice the changed rows into _last_buf in place (PERF-3):
                    # no full-buffer reallocation per keystroke.
                    for y in range(y_start, y_end):
                        base = y * row_bytes
                        self._last_buf[base : base + row_bytes] = buf[
                            base : base + row_bytes
                        ]
        else:
            # No reference frame — fall back to fast full refresh.
            if self._mode != "fast":
                self._epd.init_fast()
                self._mode = "fast"
            self._epd.display(buf)
            self._check_busy()
            self._last_buf = bytearray(buf)

    def wake(self) -> None:
        """Re-initialise the controller after sleep without clearing the screen.

        E-ink retains its image without power, so there is no need to call
        Clear() — which causes a ~2s white flash. The caller must still force a
        full display() before attempting partial refreshes, because the
        controller RAM (DTM1/DTM2) is reset by the hardware init sequence.
        """
        assert self._epd is not None
        with self._lock:
            self._epd.init_fast()
            self._mode = "fast"
            self._slept = False  # panel is powered again
            # _last_buf is intentionally preserved: the physical screen still shows
            # what it was showing before sleep, so the diff reference remains valid.
            logger.info("EPaperDriver woken from sleep (no clear)")

    def sleep(self) -> None:
        # Idempotent: safe to call from both a signal handler and atexit.
        with self._lock:
            if self._epd is not None and not self._slept:
                self._epd.sleep()
                self._mode = None  # hardware power cut — must re-init before next display
                self._slept = True
                # _last_buf preserved: e-ink retains its image without power
                logger.info("EPaperDriver sleeping")

    def close(self) -> None:
        # Idempotent: skip the Clear() if already slept so double-invocation
        # (signal handler + atexit) is safe and never raises.
        with self._lock:
            if self._epd is not None and not self._slept:
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
        # Hardware init FAILED — the panel is dead/misconfigured. Fall back to a
        # NullDriver so input/autosave keep running, but log LOUDLY at ERROR: the
        # device is now running headless-from-boot with frames going to /tmp
        # instead of the e-ink panel. Without this the Pi looks healthy while the
        # user sees a blank screen. No on-panel signal is possible here (the panel
        # itself is what failed), so a loud log is the only signal we can give.
        logger.error(
            "EPaperDriver hardware init FAILED — running HEADLESS-FROM-BOOT; "
            "the e-ink panel will NOT update, frames are being written to /tmp. "
            "Check the panel wiring / SPI config.",
            exc_info=True,
        )
        drv_null = NullDriver()
        drv_null.init()
        return drv_null
