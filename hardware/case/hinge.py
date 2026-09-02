"""Hinge hardware: the cosmetic barrel shroud, and a swing interference test.

The hinge itself is not a printed mechanism -- it is two M3 x 25 stub axles
running through interleaved knuckles, with an O-ring at each joint face taking
up the friction. Geometry for the knuckles lives in ``_common``; this module
covers the one extra printed piece and the check that the lid actually opens.
"""

from __future__ import annotations

import _common as C
import params as P
from build123d import Align, Box, Cylinder, Part, Pos, Rot


def barrel_shroud() -> Part:
    """Half-tube filling the lower half of the 66mm void between knuckle pairs.

    Purely cosmetic and purely below the hinge axis: the lid sweeps through
    everything *above* the axis at this radius, so a full tube would jam it. The
    lower half hides the ribbon from behind without entering the swing path.
    """
    outer = Pos(0, C.AXIS_Y, C.AXIS_Z) * (
        Rot(Y=90) * Cylinder(P.BARREL_R - 0.3, P.BARREL_VOID_W - 2 * P.KNUCKLE_GAP)
    )
    bore = Pos(0, C.AXIS_Y, C.AXIS_Z) * (
        Rot(Y=90) * Cylinder(P.BARREL_R - 0.3 - P.WALL, P.BARREL_VOID_W)
    )
    tube = outer - bore

    # Keep the lower half only.
    lower = Pos(0, C.AXIS_Y, C.AXIS_Z - P.BARREL_R) * Box(
        P.BARREL_W, 2 * P.BARREL_R + 2, 2 * P.BARREL_R, align=(Align.CENTER,) * 3
    )
    return tube & lower


def _rotate_open(part: Part, angle_deg: float) -> Part:
    """Swing a lid part open about the hinge axis by ``angle_deg``."""
    return (
        Pos(0, C.AXIS_Y, C.AXIS_Z)
        * Rot(X=-angle_deg)
        * Pos(0, -C.AXIS_Y, -C.AXIS_Z)
        * part
    )


def swing_interference(step: float = 15.0) -> list[tuple[float, float]]:
    """Volume of lid-into-base overlap at sampled opening angles, in mm^3.

    Anything above a rounding-error volume means the lid cannot reach that
    angle. Sampling rather than sweeping is a deliberate shortcut: the lid is
    rigid and the swept envelope is monotonic in radius, so a collision shows up
    at some sampled angle unless it is narrower than the step.
    """
    import base
    import lid

    base_solid = base.base_tray() + base.base_bottom()
    lid_solid = lid.lid_front() + lid.lid_back()

    out: list[tuple[float, float]] = []
    n = max(int(round(P.OPEN_ANGLE / step)), 1)
    for i in range(n + 1):
        angle = P.OPEN_ANGLE * i / n  # always includes the full-open endpoint
        overlap = base_solid & _rotate_open(lid_solid, angle)
        out.append((angle, overlap.volume if overlap is not None else 0.0))
    return out


PARTS = {"barrel_shroud": barrel_shroud}
