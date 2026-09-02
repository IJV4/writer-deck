"""Geometry helpers shared by the lid, base and hinge modules.

Coordinate convention for every part in this package:

    origin  centre of the 245 x 160 body footprint
    +X      right, across the width
    +Y      rearwards, toward the hinge
    +Z      up, away from the desk

Each part is modelled in the pose it occupies in the assembled, closed device,
not in its print orientation. ``export.py`` re-orients for printing.
"""

from __future__ import annotations

import params as P
from build123d import (
    Align,
    Cylinder,
    Part,
    Pos,
    RectangleRounded,
    Rot,
    Sketch,
    extrude,
)

# ---------------------------------------------------------------------------
# Footprint
# ---------------------------------------------------------------------------


#: Y of the hinge axis: ON the rear face plane, so the barrel stands proud of
#: the body. This placement is what makes the lid swing at all -- see below.
AXIS_Y = P.BODY_D / 2
#: Z of the hinge axis: level with the joint between base rim and lid, so the
#: lid carries no material below the seating plane except the knuckles.
AXIS_Z = P.BASE_H

# Why the axis sits on the rear face, not inside the body:
#
# All lid material lies at y <= AXIS_Y and z >= AXIS_Z, i.e. in the quadrant
# spanning 90..180 degrees measured from +Y about the axis. Opening by up to
# 105 degrees maps that arc to -15..75 degrees. Every point that ends up below
# the seating plane (negative angle) also ends up at cos > 0, meaning y > the
# rear face -- behind the base, in free air.
#
# Move the axis even one radius forward and that stops holding: lid material
# then sweeps down through the base's rear wall, and relieving for it would cut
# an 11mm gap across the full 245mm width. The swing test in hinge.py fails
# loudly if this invariant is ever broken.


def body_outline(inset: float = 0.0) -> Sketch:
    """The rounded body footprint, optionally shrunk by ``inset`` all round.

    Corner radius shrinks with the outline so the offset stays a true parallel
    curve -- that is what keeps wall thickness constant around the corners.
    """
    return RectangleRounded(
        P.BODY_W - 2 * inset,
        P.BODY_D - 2 * inset,
        max(P.CORNER_R - inset, 0.5),
    )


def shell(height: float, floor: float, wall: float = P.WALL) -> Part:
    """An open-topped rounded tray: full-body outer, hollowed from ``floor`` up."""
    outer = extrude(body_outline(), height)
    cavity = Pos(Z=floor) * extrude(body_outline(inset=wall), height - floor + 1)
    return outer - cavity


def lip_ring(height: float, width: float = 2.5) -> Part:
    """A shallow locating rim that seats inside the mating shell's wall.

    A ring, not a plate: extruding the inset outline solid would add a full
    sheet of plastic across the whole footprint.
    """
    inset = P.WALL + P.LIP_CLEAR
    return extrude(body_outline(inset=inset), height) - extrude(
        body_outline(inset=inset + width), height + 2
    )


# ---------------------------------------------------------------------------
# Hinge knuckles
# ---------------------------------------------------------------------------

#: X centres of the four knuckles, outermost first. Each barrel end holds one
#: base knuckle and one lid knuckle sharing a single M3 stub axle.
def knuckle_centres() -> tuple[float, float, float, float]:
    """X positions of the four knuckles, left pair then right pair."""
    outer = P.BARREL_W / 2 - P.KNUCKLE_W / 2
    inner = P.BARREL_W / 2 - P.KNUCKLE_W * 1.5
    return (-outer, -inner, inner, outer)


def knuckle(x_centre: float) -> Part:
    """One barrel knuckle, bored for its stub axle, centred on the hinge axis."""
    body = Rot(Y=90) * Cylinder(P.BARREL_R, P.KNUCKLE_W)
    bore = Rot(Y=90) * Cylinder(P.AXLE_BORE / 2, P.KNUCKLE_W + 2)
    return Pos(x_centre, AXIS_Y, AXIS_Z) * (body - bore)


def knuckles(which: str) -> Part:
    """The two knuckles belonging to one shell.

    ``which`` is ``"base"`` for the outer pair or ``"lid"`` for the inner pair.
    Splitting them this way puts a lid knuckle inboard of a base knuckle at each
    barrel end, so the joint takes load in both directions.
    """
    a, b, c, d = knuckle_centres()
    pair = (a, d) if which == "base" else (b, c)
    out = knuckle(pair[0]) + knuckle(pair[1])
    if which == "lid":
        # Groove goes on the lid knuckle's outboard face -- the one that meets a
        # base knuckle -- so the ring is captured between the two.
        out -= oring_groove(pair[0] - P.KNUCKLE_W / 2, -1)
        out -= oring_groove(pair[1] + P.KNUCKLE_W / 2, +1)
    return out


def knuckle_solids(which: str) -> Part:
    """The two knuckle cylinders of one shell, unbored -- a masking volume."""
    a, b, c, d = knuckle_centres()
    pair = (a, d) if which == "base" else (b, c)
    out = Part()
    for x in pair:
        out += Pos(x, AXIS_Y, AXIS_Z) * (Rot(Y=90) * Cylinder(P.BARREL_R, P.KNUCKLE_W))
    return out



def knuckle_clearance(which: str) -> Part:
    """Swept clearance to subtract from the *other* shell.

    Each knuckle is widened by ``KNUCKLE_GAP`` per face and cut out of the
    mating shell so the two never rub.
    """
    a, b, c, d = knuckle_centres()
    pair = (a, d) if which == "base" else (b, c)
    out = Part()
    for x in pair:
        out += Pos(x, AXIS_Y, AXIS_Z) * (
            Rot(Y=90) * Cylinder(P.BARREL_R + P.KNUCKLE_GAP, P.KNUCKLE_W + 2 * P.KNUCKLE_GAP)
        )
    return out


def oring_groove(x_face: float, facing: int) -> Part:
    """Annular groove on a knuckle face, holding the friction O-ring.

    The ring is trapped between the lid and base knuckle faces and compressed by
    the stub axle, so tightening the M3 sets the friction. Groove depth is 2/3
    of the cord, leaving 1/3 as squeeze.
    """
    depth = P.ORING_CS * 0.67
    r_in = P.ORING_ID / 2
    r_out = r_in + P.ORING_CS
    x0 = x_face if facing > 0 else x_face - depth
    ring = Pos(x0 + depth / 2, AXIS_Y, AXIS_Z) * (
        Rot(Y=90) * Cylinder(r_out, depth)
    )
    core = Pos(x0 + depth / 2, AXIS_Y, AXIS_Z) * (
        Rot(Y=90) * Cylinder(r_in, depth + 2)
    )
    return ring - core


def barrel_void() -> Part:
    """The clear centre span the ribbon twists through. Cut from both shells."""
    return Pos(0, AXIS_Y, AXIS_Z) * (
        Rot(Y=90) * Cylinder(P.BARREL_R + P.KNUCKLE_GAP, P.BARREL_VOID_W)
    )


# ---------------------------------------------------------------------------
# Fasteners
# ---------------------------------------------------------------------------

#: X, Y of the ten shell-closure screws, shared by lid and base so a single
#: pattern serves both halves.
#: Radius of an insert boss, wall to bore centre.
BOSS_R = P.INSERT_D / 2 + 1.6


def closure_points() -> list[tuple[float, float]]:
    """Screw positions, each hugging a straight run of wall.

    A boss out in open space would be a floating island with nothing to fuse to,
    so every point sits one boss-radius off the inner wall face and only on the
    flat runs, clear of the r28 corners.
    """
    # The 0.6 bite pushes each boss into the wall so the two fuse into one
    # solid; tangent contact alone leaves a separate island.
    x = P.BODY_W / 2 - P.WALL - BOSS_R + 0.6
    y = P.BODY_D / 2 - P.WALL - BOSS_R + 0.6
    return [
        (-x, -45.0),
        (-x, 0.0),
        (-x, 45.0),
        (x, -45.0),
        (x, 0.0),
        (x, 45.0),
        (-70.0, -y),
        (70.0, -y),
        (-70.0, y),
        (70.0, y),
    ]


def insert_boss(x: float, y: float, z: float, height: float) -> Part:
    """A heat-set insert boss standing ``height`` tall from ``z``, minus its pilot."""
    outer = Pos(x, y, z) * Cylinder(
        P.INSERT_D / 2 + 1.6, height, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    pilot = Pos(x, y, z + height - P.INSERT_H) * Cylinder(
        P.INSERT_D / 2, P.INSERT_H + 1, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    return outer - pilot


def screw_hole(x: float, y: float, z: float, depth: float) -> Part:
    """Through-hole plus counterbore for one M3 closure screw, drilled downward."""
    shaft = Pos(x, y, z - depth) * Cylinder(
        P.SCREW_CLEAR / 2, depth + 2, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    head = Pos(x, y, z - 0.01) * Cylinder(
        P.SCREW_HEAD_D / 2, 2.6, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    return shaft + head


def standoff(x: float, y: float, z: float, height: float) -> Part:
    """An M2.5 self-tapping PCB standoff."""
    outer = Pos(x, y, z) * Cylinder(
        P.STANDOFF_D / 2, height, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    bore = Pos(x, y, z + height - 6) * Cylinder(
        P.STANDOFF_BORE / 2, 7, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    return outer - bore


# ---------------------------------------------------------------------------
# Base interior zone boundaries, in body coordinates
# ---------------------------------------------------------------------------

#: Y of the front and rear edge of each interior zone, front to rear.
FRONT_Y0 = -P.BODY_D / 2 + P.WALL
DECK_Y0 = FRONT_Y0 + P.FRONT_D
DECK_Y1 = DECK_Y0 + P.DECK_D
REAR_Y0 = DECK_Y1
REAR_Y1 = REAR_Y0 + P.REAR_D
