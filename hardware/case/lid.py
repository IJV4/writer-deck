"""The lid: bezel tray carrying the panel and Driver HAT, plus its back cover.

Modelled in the assembled, closed pose. The base occupies z in [0, BASE_H];
the lid sits directly on top of it, z in [BASE_H, BASE_H + LID_H].

    z = 45.0   lid_back outer face
    z = 43.0   lid_back / lid_front joint
    z = 40.7   HAT pocket ceiling
    z = 37.7   panel back face
    z = 36.5   panel front face, bonding ledge
    z = 34.0   bezel outer face -- faces the keyboard when closed
"""

from __future__ import annotations

from math import atan2, degrees, hypot

import _common as C
import params as P
from build123d import Align, Box, Part, Pos, Rectangle, Rot, extrude, loft

# Layer heights ------------------------------------------------------------

Z0 = P.BASE_H  # bezel outer face
BEZEL_T = 2.5
LID_BACK_T = 2.0

Z_LEDGE = Z0 + BEZEL_T  # panel front face rests here
Z_PANEL_BACK = Z_LEDGE + P.PANEL_T
Z_HAT_TOP = Z_PANEL_BACK + P.HAT_T
Z_JOINT = Z0 + P.LID_H - LID_BACK_T  # lid_front / lid_back interface
Z_TOP = Z0 + P.LID_H

#: Bezel overlap onto the panel -- the actual bonding width for the VHB.
LEDGE_OVERLAP = (P.POCKET_W - P.WINDOW_W) / 2

# Panel and HAT placement --------------------------------------------------

#: The panel sits centred, biased 2mm forward so the rear keeps clearance for
#: the spine rail and the ribbon drop. Bezels land at 40.7 side, ~24 front,
#: ~28 rear -- deliberately chunky, which is what the r28 corners are for.
PANEL_Y = -2.0

#: The HAT lies behind the panel, on the centreline. Centring it is what lets
#: the ribbon run straight back and drop into the barrel void without a jog.
HAT_X = 0.0
HAT_Y = PANEL_Y + P.POCKET_D / 2 - P.HAT_D / 2 - 6


#: How far the window flares outward toward the viewer, per side.
WINDOW_FLARE = 1.2


def _window() -> Part:
    """Through-cut for the active area, flared toward the viewer.

    The flare keeps the bezel edge from casting a hard shadow line across the
    panel, and prints as a chamfer rather than an overhang.
    """
    outer = Pos(0, PANEL_Y, Z0) * Rectangle(
        P.WINDOW_W + 2 * WINDOW_FLARE, P.WINDOW_D + 2 * WINDOW_FLARE
    )
    inner = Pos(0, PANEL_Y, Z_LEDGE) * Rectangle(P.WINDOW_W, P.WINDOW_D)
    flare = loft([outer, inner])

    # Extend a hair past both faces so the boolean leaves no zero-thickness skin.
    over = Pos(0, PANEL_Y, Z0 - 1) * Box(
        P.WINDOW_W + 2 * WINDOW_FLARE,
        P.WINDOW_D + 2 * WINDOW_FLARE,
        1,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )
    return flare + over


def _panel_pocket() -> Part:
    """Recess the panel drops into, from the ledge up to its back face."""
    return Pos(0, PANEL_Y, Z_LEDGE) * Box(
        P.POCKET_W,
        P.POCKET_D,
        Z_TOP - Z_LEDGE + 1,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )


def _hat_pocket() -> Part:
    """Clearance for the Driver HAT sitting behind the panel."""
    return Pos(HAT_X, HAT_Y, Z_PANEL_BACK) * Box(
        P.HAT_W + 1.0,
        P.HAT_D + 1.0,
        P.HAT_T + 0.4,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )


def _spine_rail() -> Part:
    """Full-width 4 x 8 rail along the rear inner wall.

    Spec section 4.1: this is the single largest contributor to lid stiffness.
    It turns the 110mm barrel's point load into one distributed across 245mm.
    """
    y = P.BODY_D / 2 - P.WALL - 4 / 2
    return Pos(0, y, Z_LEDGE) * Box(
        P.BODY_W - 2 * P.WALL - 2 * P.CORNER_R,
        4.0,
        8.0,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )


def _gussets() -> Part:
    """Two diagonals tying the rail forward into the side walls."""
    out = Part()
    y_rail = P.BODY_D / 2 - P.WALL - 2
    for sign, x_knuckle in ((-1, C.knuckle_centres()[1]), (1, C.knuckle_centres()[2])):
        x_wall = sign * (P.BODY_W / 2 - P.WALL - P.CORNER_R * 0.5)
        dx, dy = x_wall - x_knuckle, -46.0
        length = hypot(dx, dy)
        angle = 90 - degrees(atan2(dy, dx))
        rib = Box(3.0, length, 7.0, align=(Align.CENTER, Align.MIN, Align.MIN))
        out += Pos(x_knuckle, y_rail, Z_LEDGE) * Rot(Z=angle) * rib
    return out


def _ribbon_slot() -> Part:
    """Path for the 10-way ribbon from the HAT pocket down into the barrel void."""
    w = P.RIBBON_W + 2.0
    h = P.RIBBON_T + 2.0
    # Horizontal run from the HAT back to the hinge axis, at panel-back height.
    y_end = C.AXIS_Y
    run = Pos(HAT_X, (HAT_Y + y_end) / 2, Z_PANEL_BACK) * Box(
        w, y_end - HAT_Y, h, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    # Vertical drop at the axis, down through the bezel into the barrel void.
    drop = Pos(HAT_X, y_end, C.AXIS_Z - 1) * Box(
        w,
        h + 4,
        Z_PANEL_BACK - C.AXIS_Z + h + 1,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )
    return run + drop


def lid_front() -> Part:
    """Bezel tray: window, panel ledge, HAT pocket, stiffening, hinge knuckles."""
    part = C.shell(height=P.LID_H, floor=BEZEL_T, wall=P.WALL)
    part = Pos(Z=Z0) * part

    # Trim the tray back to where lid_back takes over.
    part -= Pos(0, 0, Z_JOINT) * extrude(C.body_outline(inset=P.WALL), Z_TOP - Z_JOINT + 1)

    part += _spine_rail() + _gussets()
    part -= _panel_pocket()
    part -= _window()
    part -= _hat_pocket()
    part -= _ribbon_slot()

    part += C.knuckles("lid")
    part -= C.knuckle_clearance("base")
    part -= C.barrel_void()

    # Closure bosses rise from the bezel floor to the lid_back interface.
    for x, y in C.closure_points():
        part += C.insert_boss(x, y, Z_LEDGE, Z_JOINT - Z_LEDGE)

    # Bosses must not swallow the panel pocket or the window.
    part -= _panel_pocket()
    part -= _window()
    return part


def lid_back() -> Part:
    """Flat cover closing the lid. Removing it exposes the HAT and the panel."""
    plate = Pos(0, 0, Z_JOINT) * extrude(C.body_outline(), Z_TOP - Z_JOINT)
    lip = Pos(0, 0, Z_JOINT - 1.2) * C.lip_ring(1.2)
    part = plate + lip

    for x, y in C.closure_points():
        part -= C.screw_hole(x, y, Z_TOP, Z_TOP - Z_JOINT + 1.2)

    part -= C.knuckle_clearance("base")
    part -= C.knuckle_clearance("lid")
    return part


PARTS = {"lid_front": lid_front, "lid_back": lid_back}
