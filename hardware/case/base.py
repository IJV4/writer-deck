"""The base: keyboard tray at the front, electronics bay behind, hinge at the rear.

Modelled in the assembled, closed pose -- the base occupies z in [0, BASE_H]
and the lid sits on top of it. See ``lid.py`` for the layers above.

    z = 34.0   rim, where the lid seats
    z = 31.5   rear bay ceiling, underside
    z = 25.7   front keycap tops
    z =  2.0   base_tray / base_bottom joint
    z =  0.0   desk

Two layout points that differ from the first draft of spec section 3:

*No palm rest.* With 18mm keycaps the rear key row has to fit under the closed
lid, which puts the front row ~8mm below rim height. A palm rest at rim height
would leave a cliff in front of the keys, so the keyboard runs to the front lip
instead -- as on the Penkesu and Beepy -- and every board lives in the rear bay.

*What mounts where.* ``base_bottom`` is the structural floor and carries
everything that bolts down -- the Pi and the keyboard both. ``base_tray`` is
walls, deck skirt and ceiling only, so no post is left floating when the two
parts are separated.
"""

from __future__ import annotations

from math import cos, radians, sin

import _common as C
import params as P
from build123d import Align, Box, Part, Pos, Rot, extrude

# Layer heights ------------------------------------------------------------

BOTTOM_T = 2.0  # base_bottom plate thickness
Z_RIM = P.BASE_H
Z_CEIL = Z_RIM - P.WALL_TOP  # rear bay ceiling, underside

#: Underside of the keyboard PCB at the front of the deck. Components on the
#: PCB's underside hang into the gap below it.
Z_PCB_FRONT = BOTTOM_T + P.KBD_UNDER_H

#: Deck plate: its underside sits just above the PCB, so the plate hides the
#: switch bodies and only the caps come through the aperture.
DECK_T = 2.0
Z_DECK_FRONT = Z_PCB_FRONT + P.KBD_PCB_T + 0.5

#: Overlap into the wall, so trimmed features fuse rather than touch tangentially.
_BITE = 0.6

_SLOPE = radians(P.DECK_SLOPE)


def _tilted(width: float, depth: float, thickness: float, z0: float, y0: float = None) -> Part:
    """A slab spanning the deck zone, tilted nose-down by DECK_SLOPE.

    Built flat then rotated about the deck's front edge, so the front edge stays
    at ``z0`` and the rear edge rises by ``DECK_D * sin(slope)``.
    """
    slab = Box(width, depth, thickness, align=(Align.CENTER, Align.MIN, Align.MIN))
    return Pos(0, C.DECK_Y0 if y0 is None else y0, z0) * Rot(X=P.DECK_SLOPE) * slab


def _interior(inset: float = P.WALL - _BITE) -> Part:
    """Solid filling the shell interior, used to trim tilted geometry."""
    return extrude(C.body_outline(inset=inset), Z_RIM + 10)


def _deck() -> Part:
    """Sloped keyboard deck with its aperture, trimmed to the shell interior."""
    plate = _tilted(P.BODY_W, P.DECK_D, DECK_T, Z_DECK_FRONT) & _interior()
    # The aperture clears the whole PCB, not just the keycap field: the board is
    # bottom-mounted, so the deck plate is a skirt bridging PCB edge to wall and
    # must not sit over the board.
    aperture = _tilted(
        P.KBD_W + 1.0, P.KBD_D + 1.0, DECK_T + 10, Z_DECK_FRONT - 5, y0=C.DECK_Y0 - 0.5
    )
    return plate - aperture


def _deck_walls() -> Part:
    """Closes the wedge-shaped gaps the tilted deck leaves fore and aft."""
    out = Part()

    # Front: from the deck's low edge down to the floor.
    out += (
        Pos(0, C.DECK_Y0, 0)
        * Box(P.BODY_W, 3.0, Z_DECK_FRONT + DECK_T, align=(Align.CENTER, Align.MAX, Align.MIN))
    ) & _interior()

    # Rear: from the deck's high edge up to the bay ceiling.
    rear_top = Z_DECK_FRONT + P.DECK_D * sin(_SLOPE) + DECK_T
    out += (
        Pos(0, C.DECK_Y1, 0)
        * Box(P.BODY_W, 3.0, rear_top, align=(Align.CENTER, Align.MIN, Align.MIN))
    ) & _interior()
    return out


def _rear_ceiling() -> Part:
    """Top surface over the electronics bay, from the deck's rear edge back."""
    depth = P.BODY_D / 2 - C.REAR_Y0
    slab = Pos(0, C.REAR_Y0, Z_CEIL) * Box(
        P.BODY_W, depth, P.WALL_TOP, align=(Align.CENTER, Align.MIN, Align.MIN)
    )
    return slab & extrude(C.body_outline(), Z_RIM)


def keyboard_bosses() -> Part:
    """Posts rising from the floor to the tilted keyboard PCB plane.

    Bottom-mounted rather than hung from the deck: the deck aperture has to clear
    the whole board, which leaves no deck material above the mounting points.
    The cost is that the deck angle and the PCB angle are set by two different
    parts -- both read DECK_SLOPE from params, so they agree by construction.

    Positions are nominal. KBD_W/KBD_D are ESTIMATED and the real mounting-hole
    pattern is unmeasured, so these move once the board is on the calipers.
    """
    out = Part()
    inset = 10.0
    for sx in (-1, 1):
        for u in (inset, P.KBD_D - inset):
            x = sx * (P.KBD_W / 2 - inset)
            y = C.DECK_Y0 + u * cos(_SLOPE)
            top = Z_PCB_FRONT + u * sin(_SLOPE)
            out += C.standoff(x, y, BOTTOM_T, top - BOTTOM_T)
    return out


def _ports() -> Part:
    """Side cutouts. Micro-SD is deliberately absent -- see spec section 8."""
    out = Part()
    x_wall = P.BODY_W / 2

    # PiSugar USB-C charge, right side of the rear bay.
    out += Pos(x_wall, C.REAR_Y0 + 25, BOTTOM_T + 2) * Box(
        2 * P.WALL + 6, 10.0, 4.0, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    # PiSugar power button, right side, sized for a printed cap.
    out += Pos(x_wall, C.REAR_Y0 + 45, BOTTOM_T + 4) * (
        Rot(Y=90) * Box(4.0, 4.0, 2 * P.WALL + 6, align=(Align.CENTER,) * 3)
    )
    return out


def _front_relief() -> Part:
    """Chamfer on the inner top edge of the front rim.

    The rim has to stand at lid height all the way round, so it sits ~8mm proud
    of the front key row -- normal for a high-profile keyboard case, but the
    square inner corner is what the hand would actually feel. This bevels it.
    """
    y = -P.BODY_D / 2 + P.WALL
    return Pos(0, y, Z_RIM) * Rot(X=45) * Box(
        P.BODY_W + 10, 5.0, 5.0, align=(Align.CENTER, Align.CENTER, Align.CENTER)
    )


def base_tray() -> Part:
    """Rim, sloped keyboard deck, rear bay ceiling, ports and hinge knuckles."""
    walls = Pos(0, 0, BOTTOM_T) * (
        extrude(C.body_outline(), Z_RIM - BOTTOM_T)
        - extrude(C.body_outline(inset=P.WALL), Z_RIM - BOTTOM_T)
    )
    part = walls + _rear_ceiling() + _deck_walls() + _deck()

    for x, y in C.closure_points():
        part += C.insert_boss(x, y, BOTTOM_T, 8.0)

    part += C.knuckles("base")
    part -= C.knuckle_clearance("lid")
    part -= _ports()
    part -= _front_relief()

    # Cosmetic chamfer on the front-bottom edge -- keeps the wedge read that the
    # level rim gave up. Spec section 2.2.
    part -= Pos(0, -P.BODY_D / 2, BOTTOM_T) * Rot(X=45) * Box(
        P.BODY_W + 10,
        P.FRONT_CHAMFER,
        P.FRONT_CHAMFER,
        align=(Align.CENTER, Align.MAX, Align.CENTER),
    )
    return part


def _board_standoffs() -> Part:
    """Posts for the Pi, on the floor plate.

    The Pi sits left of centre so its GPIO header, and the ribbon leaving it,
    land under the barrel void rather than under a knuckle. PiSugar and cell go
    on adhesive pads -- they have no usable mounting holes in this build.
    """
    out = Part()
    cx, cy = -60.0, C.REAR_Y0 + 8 + P.PI_D / 2
    for dx in (-P.PI_HOLE_DX / 2, P.PI_HOLE_DX / 2):
        for dy in (-P.PI_HOLE_DY / 2, P.PI_HOLE_DY / 2):
            out += C.standoff(cx + dx, cy + dy, BOTTOM_T, 3.0)
    return out


def base_bottom() -> Part:
    """Floor plate. Carries the boards; removing it takes them out as a unit."""
    plate = extrude(C.body_outline(), BOTTOM_T)
    lip = Pos(0, 0, BOTTOM_T) * C.lip_ring(1.2)
    part = plate + lip + _board_standoffs() + keyboard_bosses()

    for x, y in C.closure_points():
        # Drilled from the underside, head recessed flush into the desk face.
        part -= Pos(x, y, 0) * Rot(X=180) * C.screw_hole(0, 0, 0, BOTTOM_T + 2.4)

    # Foot recesses for adhesive pads, inboard of the corner radius.
    for sx in (-1, 1):
        for sy in (-1, 1):
            part -= Pos(
                sx * (P.BODY_W / 2 - P.CORNER_R),
                sy * (P.BODY_D / 2 - P.CORNER_R),
                -0.1,
            ) * Box(18.0, 18.0, 0.7, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return part


PARTS = {"base_tray": base_tray, "base_bottom": base_bottom}
