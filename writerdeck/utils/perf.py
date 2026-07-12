"""Lightweight performance metrics — timing regions and gauges for render pipeline."""

import logging
import time as _time
from collections import deque
from collections.abc import Generator
from contextlib import contextmanager

logger = logging.getLogger("writerdeck.perf")


class PerfMetrics:
    def __init__(self) -> None:
        self.enabled: bool = False
        self._frames: deque[dict[str, float]] = deque(maxlen=120)
        self._current: dict[str, float] = {}
        self._gauges: dict[str, int | float] = {}

    @contextmanager
    def time(self, region: str) -> Generator[None, None, None]:
        if not self.enabled:
            yield
            return
        t0 = _time.monotonic()
        try:
            yield
        finally:
            elapsed = _time.monotonic() - t0
            self._current[region] = self._current.get(region, 0.0) + elapsed
            if region == "total_frame":
                self._frames.append(self._current)
                self._current = {}

    def record_gauge(self, name: str, value: int | float) -> None:
        if not self.enabled:
            return
        self._gauges[name] = value

    def log_summary(self) -> None:
        if not self._frames:
            logger.info("PerfMetrics: no frames recorded yet")
            return

        # Collect all region names across frames
        regions: set[str] = set()
        for frame in self._frames:
            regions.update(frame.keys())

        lines = [f"PerfMetrics summary ({len(self._frames)} frames):"]
        for region in sorted(regions):
            values = [f[region] for f in self._frames if region in f]
            if not values:
                continue
            sorted_vals = sorted(values)
            n = len(sorted_vals)
            p50 = sorted_vals[n // 2]
            p95 = sorted_vals[int(n * 0.95)]
            mx = sorted_vals[-1]
            lines.append(
                f"  {region}: p50={p50*1000:.1f}ms  p95={p95*1000:.1f}ms  max={mx*1000:.1f}ms"
            )

        if self._gauges:
            lines.append("  gauges: " + "  ".join(f"{k}={v}" for k, v in sorted(self._gauges.items())))

        logger.info("\n".join(lines))

    def reset(self) -> None:
        self._frames.clear()
        self._current = {}
        self._gauges = {}


_singleton: PerfMetrics = PerfMetrics()


def get_perf() -> PerfMetrics:
    return _singleton
