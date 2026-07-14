"""Platform detection — Pi Zero 2 W vs Pi 5 vs desktop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class HardwareProfile:
    name: str
    is_pi: bool
    is_pi_zero: bool
    partial_refresh_max_streak: int
    render_interval_ms: int
    font_size: int


_PI_MODEL_PATH = Path("/proc/device-tree/model")


def detect_platform() -> HardwareProfile:
    model = ""
    if _PI_MODEL_PATH.exists():
        model = _PI_MODEL_PATH.read_text(errors="replace").strip().lower()

    if "zero 2" in model:
        return HardwareProfile(
            name="pi_zero_2w",
            is_pi=True,
            is_pi_zero=True,
            partial_refresh_max_streak=20,
            render_interval_ms=500,
            font_size=14,
        )
    elif "raspberry pi 5" in model:
        return HardwareProfile(
            name="pi5",
            is_pi=True,
            is_pi_zero=False,
            partial_refresh_max_streak=40,
            render_interval_ms=200,
            font_size=16,
        )
    elif "raspberry pi" in model:
        return HardwareProfile(
            name="pi_other",
            is_pi=True,
            is_pi_zero=False,
            partial_refresh_max_streak=30,
            render_interval_ms=300,
            font_size=14,
        )
    else:
        return HardwareProfile(
            name="desktop",
            is_pi=False,
            is_pi_zero=False,
            partial_refresh_max_streak=50,
            render_interval_ms=100,
            font_size=16,
        )
