#!/usr/bin/env python3
"""Standalone panel deep-sleep backstop (FAULT-2).

Run by the systemd unit as ``ExecStopPost=`` so the Waveshare 7.5" panel is put
into deep sleep (POWER_OFF + DEEP_SLEEP) even when the main app crashes or is
SIGKILLed and never runs its own cleanup. ``ExecStopPost`` fires on every exit
(clean, timeout, or crash), unlike ``ExecStop`` which only runs on a clean stop.

This is a *separate process* from the main app: it re-inits SPI from scratch and
may briefly race the dying main process for the bus. The unit's
``TimeoutStopSec=15`` gives the in-process signal handler time to win the bus
first; this script is the belt-and-suspenders backstop for when it doesn't.

Everything is wrapped in try/except and the process ALWAYS exits 0 — a failure
to sleep the panel (e.g. no hardware, import error on a dev machine, transient
SPI fault) must never make ``systemctl stop`` report a failed unit. On desktop
the vendored ``waveshare_epd`` package is not importable, so this is a clean
no-op there.
"""

from __future__ import annotations

import sys


def main() -> None:
    try:
        # Vendored, Pi-only driver — not importable on desktop (PYTHONPATH=lib
        # is set by the systemd unit; import fails cleanly elsewhere).
        from waveshare_epd import epd7in5_V2  # type: ignore[import-untyped]

        epd = epd7in5_V2.EPD()
        epd.init()
        epd.sleep()  # 0x02 POWER_OFF + 0x07 DEEP_SLEEP
        print("epd_sleep: panel deep-sleep OK", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - backstop must never propagate
        print(f"epd_sleep: skipped ({exc!r})", file=sys.stderr)


if __name__ == "__main__":
    main()
    sys.exit(0)
