"""The three validation coupons from spec section 10.

Each coupon is cut out of the *real* part with a boolean, never re-modelled.
That is the whole point: a coupon that was drawn separately can pass while the
part it stands for fails, because the two drift apart on the next edit.

Print these before committing to a full part. Together they are about 25cm3 --
roughly an hour on an Ender-class machine, 20 minutes on a Bambu.
"""

from __future__ import annotations

import _common as C
import base
import lid
import params as P
from build123d import Align, Box, Part, Pos


def _crop(part: Part, centre: tuple[float, float, float], size: tuple[float, float, float]) -> Part:
    """Intersect a part with a box, then drop it onto z = 0 for printing."""
    cx, cy, cz = centre
    piece = part & (Pos(cx, cy, cz) * Box(*size, align=(Align.CENTER,) * 3))
    bb = piece.bounding_box()
    return Pos(-bb.center().X, -bb.center().Y, -bb.min.Z) * piece


def hinge_coupon_base() -> Part:
    """Base side of one knuckle pair, with a stub of rear wall to hold it."""
    x = C.knuckle_centres()[3]
    # Kept clear of the closure boss at x = 70; grazing it leaves a sliver.
    return _crop(
        base.base_tray(), (x - 8, P.BODY_D / 2 - 12, P.BASE_H / 2), (40, 40, P.BASE_H + 24)
    )


def hinge_coupon_lid() -> Part:
    """Lid side of the same pair, including the O-ring groove."""
    x = C.knuckle_centres()[3]
    return _crop(
        lid.lid_front(),
        (x - 8, P.BODY_D / 2 - 12, P.BASE_H + P.LID_H / 2),
        (40, 40, P.LID_H + 24),
    )


def window_corner_coupon() -> Part:
    """One r28 corner of the bezel: window edge, flare, ledge and pocket step.

    Tests two things at once -- whether the panel actually drops into the pocket,
    and how a 28mm radius reads at real scale next to a 40mm bezel.
    """
    x = -(P.BODY_W / 2 - 30)
    y = -(P.BODY_D / 2 - 30)
    return _crop(lid.lid_front(), (x, y, P.BASE_H + P.LID_H / 2), (70, 70, P.LID_H + 4))


def keyboard_deck_coupon() -> Part:
    """A slice of the sloped deck at its aperture edge, plus a mounting boss.

    Cut at the rear of the deck, where the slope has lifted the board highest
    and the keycap-to-rim clearance is tightest.
    """
    tray = base.base_tray() & (
        Pos(-(P.KBD_W / 2 - 10), C.DECK_Y1 - 18, P.BASE_H / 2)
        * Box(50, 44, P.BASE_H + 20, align=(Align.CENTER,) * 3)
    )
    floor = base.base_bottom() & (
        Pos(-(P.KBD_W / 2 - 10), C.DECK_Y1 - 18, 10)
        * Box(50, 44, 40, align=(Align.CENTER,) * 3)
    )
    piece = tray + floor
    bb = piece.bounding_box()
    return Pos(-bb.center().X, -bb.center().Y, -bb.min.Z) * piece


PARTS = {
    "coupon_hinge_base": hinge_coupon_base,
    "coupon_hinge_lid": hinge_coupon_lid,
    "coupon_window_corner": window_corner_coupon,
    "coupon_keyboard_deck": keyboard_deck_coupon,
}
