"""Single source of truth for every Writer Deck case dimension.

All units are millimetres, all angles degrees.

Values are tagged in their trailing comment:

    MEASURED  taken with calipers off the actual part
    DATASHEET taken from a vendor drawing, not yet verified against the part
    ESTIMATED a guess -- see spec section 9; must be measured before printing
    DERIVED   computed from the values above; do not edit directly
    CHOSEN    a design decision, not a measurement

Run ``python params.py`` to print the audit table and the list of values that
are still ESTIMATED.

See ``docs/superpowers/specs/2026-08-16-3d-case-design.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin

# ---------------------------------------------------------------------------
# Provenance tracking
# ---------------------------------------------------------------------------

MEASURED = "MEASURED"
DATASHEET = "DATASHEET"
ESTIMATED = "ESTIMATED"
DERIVED = "DERIVED"
CHOSEN = "CHOSEN"

#: Provenance of every module-level dimension below, keyed by name.
PROVENANCE: dict[str, str] = {}


def _p(name: str, value: float, source: str) -> float:
    """Record a dimension's provenance and return it."""
    PROVENANCE[name] = source
    return value


# ---------------------------------------------------------------------------
# Build switches
# ---------------------------------------------------------------------------

#: Emit the base as two dovetailed halves instead of one piece. Set True when
#: the available printer's bed or per-job time cap cannot take a 245mm part.
SPLIT_BASE = False

#: Nozzle the parts are sliced for. Drives minimum feature widths only; it does
#: not change any outer dimension. Spec section 7.1 recommends 0.6.
NOZZLE = 0.6

# ---------------------------------------------------------------------------
# Components -- the numbers the case has to obey
# ---------------------------------------------------------------------------

# Waveshare 7.5" V2 e-Paper panel -------------------------------------------
PANEL_W = _p("PANEL_W", 170.2, DATASHEET)
PANEL_D = _p("PANEL_D", 111.2, DATASHEET)
PANEL_T = _p("PANEL_T", 1.2, DATASHEET)
#: Active area. The window is cut from this plus WINDOW_OVERCUT per side.
ACTIVE_W = _p("ACTIVE_W", 163.2, DATASHEET)
ACTIVE_D = _p("ACTIVE_D", 97.92, DATASHEET)
#: Free length of the panel's own FPC tail, from its exit edge. Sets how far
#: the connector board can sit from the panel.
PANEL_FPC_FREE = _p("PANEL_FPC_FREE", 40.0, ESTIMATED)

# Waveshare Driver HAT, 40-pin header desoldered ----------------------------
HAT_W = _p("HAT_W", 65.0, ESTIMATED)
HAT_D = _p("HAT_D", 30.0, ESTIMATED)
HAT_T = _p("HAT_T", 3.0, ESTIMATED)

# Raspberry Pi Zero 2 W -----------------------------------------------------
PI_W = _p("PI_W", 65.0, DATASHEET)
PI_D = _p("PI_D", 30.0, DATASHEET)
PI_T = _p("PI_T", 5.0, ESTIMATED)  # board + tallest bottom-side component
PI_HOLE_DX = _p("PI_HOLE_DX", 58.0, DATASHEET)
PI_HOLE_DY = _p("PI_HOLE_DY", 23.0, DATASHEET)
PI_HOLE_D = _p("PI_HOLE_D", 2.75, DATASHEET)

# KPrepublic BM43A keyboard, bare PCB ---------------------------------------
KBD_W = _p("KBD_W", 230.0, ESTIMATED)
KBD_D = _p("KBD_D", 76.0, ESTIMATED)
KBD_PCB_T = _p("KBD_PCB_T", 1.6, ESTIMATED)
#: Keycap top above the top face of the PCB. User reports a 20mm total stack.
KBD_CAP_H = _p("KBD_CAP_H", 18.4, ESTIMATED)
#: Tallest component under the PCB (switch pins, controller, USB socket).
KBD_UNDER_H = _p("KBD_UNDER_H", 4.0, ESTIMATED)

# PiSugar 3 Plus ------------------------------------------------------------
# HIGHEST RISK -- spec section 11. If the board is ~85 x 56 rather than the
# Pi-Zero-sized footprint assumed here, the base depth has to grow.
SUGAR_W = _p("SUGAR_W", 65.0, ESTIMATED)
SUGAR_D = _p("SUGAR_D", 30.0, ESTIMATED)
SUGAR_T = _p("SUGAR_T", 10.0, ESTIMATED)  # incl. cables, per user report
CELL_W = _p("CELL_W", 60.0, ESTIMATED)
CELL_D = _p("CELL_D", 50.0, ESTIMATED)
CELL_T = _p("CELL_T", 10.0, ESTIMATED)

# ---------------------------------------------------------------------------
# Shell envelope
# ---------------------------------------------------------------------------

BODY_W = _p("BODY_W", 245.0, CHOSEN)
BODY_D = _p("BODY_D", 160.0, CHOSEN)
CORNER_R = _p("CORNER_R", 28.0, CHOSEN)

WALL = _p("WALL", 1.8, CHOSEN)
WALL_STRUCTURAL = _p("WALL_STRUCTURAL", 2.4, CHOSEN)  # rail, knuckles
WALL_TOP = _p("WALL_TOP", 2.5, CHOSEN)  # rear bay lid -- spans unsupported

LID_H = _p("LID_H", 11.0, CHOSEN)
BASE_H = _p("BASE_H", 34.0, CHOSEN)

#: Cosmetic chamfer on the front-bottom edge -- keeps the wedge look that the
#: level rim gave up. See spec section 2.2.
FRONT_CHAMFER = _p("FRONT_CHAMFER", 6.0, CHOSEN)

#: Air gap the rear keycaps must keep below the closed lid. Small, but it has
#: to be non-zero -- the caps sit under a bonded glass panel.
CAP_CLEARANCE = _p("CAP_CLEARANCE", 1.0, CHOSEN)

# ---------------------------------------------------------------------------
# Base interior zones, front to rear
# ---------------------------------------------------------------------------
#
# There is deliberately NO palm rest. With 18mm keycaps the rear row has to sit
# under the closed lid, which puts the front row ~7mm below rim height; a palm
# rest at rim height would leave a cliff between the wrists and the front row.
# The keyboard therefore runs to the front edge, as on the Penkesu and Beepy,
# and every board lives in the rear bay behind it.

FRONT_D = _p("FRONT_D", 4.0, CHOSEN)  # front lip ahead of the keyboard
DECK_D = _p("DECK_D", 76.0, CHOSEN)  # keyboard aperture depth

DECK_SLOPE = _p("DECK_SLOPE", 5.0, CHOSEN)  # 6 deg leaves only 0.4mm cap clearance

# ---------------------------------------------------------------------------
# Hinge
# ---------------------------------------------------------------------------

BARREL_W = _p("BARREL_W", 110.0, CHOSEN)
BARREL_R = _p("BARREL_R", 8.0, CHOSEN)
KNUCKLE_W = _p("KNUCKLE_W", 11.0, CHOSEN)  # one knuckle; four in total
KNUCKLE_GAP = _p("KNUCKLE_GAP", 0.3, CHOSEN)  # per mating face
AXLE_BORE = _p("AXLE_BORE", 3.2, CHOSEN)  # M3 clearance
AXLE_LEN = _p("AXLE_LEN", 25.0, CHOSEN)  # M3 x 25
ORING_ID = _p("ORING_ID", 3.0, CHOSEN)
ORING_CS = _p("ORING_CS", 1.5, CHOSEN)  # cross-section
OPEN_ANGLE = _p("OPEN_ANGLE", 105.0, CHOSEN)  # max lid swing

RIBBON_W = _p("RIBBON_W", 12.7, CHOSEN)  # 10-way, 1.27mm pitch
RIBBON_T = _p("RIBBON_T", 1.0, CHOSEN)

# ---------------------------------------------------------------------------
# Fits and fastener geometry
# ---------------------------------------------------------------------------

WINDOW_OVERCUT = _p("WINDOW_OVERCUT", 0.2, CHOSEN)  # per side, around active area
POCKET_CLEAR = _p("POCKET_CLEAR", 0.3, CHOSEN)  # per side, around panel outline
LEDGE_W = _p("LEDGE_W", 1.5, CHOSEN)  # panel bonds to this
LIP_CLEAR = _p("LIP_CLEAR", 0.2, CHOSEN)  # shell-to-shell slip fit

INSERT_D = _p("INSERT_D", 4.0, CHOSEN)  # M3 heat-set pilot
INSERT_H = _p("INSERT_H", 5.0, CHOSEN)
SCREW_CLEAR = _p("SCREW_CLEAR", 3.4, CHOSEN)  # M3 through-hole
SCREW_HEAD_D = _p("SCREW_HEAD_D", 6.0, CHOSEN)

STANDOFF_D = _p("STANDOFF_D", 6.0, CHOSEN)
STANDOFF_BORE = _p("STANDOFF_BORE", 2.1, CHOSEN)  # M2.5 self-tapping

# ---------------------------------------------------------------------------
# Derived
# ---------------------------------------------------------------------------

WINDOW_W = _p("WINDOW_W", ACTIVE_W + 2 * WINDOW_OVERCUT, DERIVED)
WINDOW_D = _p("WINDOW_D", ACTIVE_D + 2 * WINDOW_OVERCUT, DERIVED)
POCKET_W = _p("POCKET_W", PANEL_W + 2 * POCKET_CLEAR, DERIVED)
POCKET_D = _p("POCKET_D", PANEL_D + 2 * POCKET_CLEAR, DERIVED)

#: Clear span between the two knuckle pairs -- the ribbon's home.
BARREL_VOID_W = _p("BARREL_VOID_W", BARREL_W - 4 * KNUCKLE_W, DERIVED)

#: Total keyboard stack, PCB underside to keycap top.
KBD_STACK_H = _p("KBD_STACK_H", KBD_UNDER_H + KBD_PCB_T + KBD_CAP_H, DERIVED)

#: Everything left over behind the keyboard: Pi, PiSugar, cell, and the barrel.
REAR_D = _p("REAR_D", BODY_D - 2 * WALL - FRONT_D - DECK_D, DERIVED)

#: Height the rear edge of the sloped deck gains over its front edge.
DECK_RISE = _p("DECK_RISE", DECK_D * sin(radians(DECK_SLOPE)), DERIVED)

#: Keycap apex above the base floor at the rear of the deck -- the number that
#: must stay under BASE_H or the lid will not close.
CAP_APEX_H = _p(
    "CAP_APEX_H", WALL + KBD_STACK_H * cos(radians(DECK_SLOPE)) + DECK_RISE, DERIVED
)

#: Keycap top at the FRONT row. The case front lip is chamfered down to this
#: so the hand crosses onto the keys without a step.
CAP_FRONT_H = _p("CAP_FRONT_H", WALL + KBD_STACK_H * cos(radians(DECK_SLOPE)), DERIVED)

#: Overall depth including the barrel, which stands proud of the rear face.
OVERALL_D = _p("OVERALL_D", BODY_D + BARREL_R, DERIVED)

#: Closed height of the whole device.
CLOSED_H = _p("CLOSED_H", BASE_H + LID_H, DERIVED)

# ---------------------------------------------------------------------------
# Self-checks
# ---------------------------------------------------------------------------


@dataclass
class Check:
    """One geometric invariant the parameter set has to satisfy."""

    name: str
    ok: bool
    detail: str


def checks() -> list[Check]:
    """Every constraint that a caliper correction could silently break."""
    out: list[Check] = []

    def add(name: str, ok: bool, detail: str) -> None:
        out.append(Check(name, ok, detail))

    add(
        "keycaps clear the closed lid",
        CAP_APEX_H + CAP_CLEARANCE <= BASE_H,
        f"apex {CAP_APEX_H:.1f} + {CAP_CLEARANCE:.1f} gap vs rim {BASE_H:.1f}",
    )
    add(
        "base zones fit the body depth",
        FRONT_D + DECK_D + REAR_D + 2 * WALL <= BODY_D,
        f"{FRONT_D + DECK_D + REAR_D + 2 * WALL:.1f} of {BODY_D:.1f}",
    )
    add(
        "panel fits the lid face",
        POCKET_W + 2 * WALL <= BODY_W and POCKET_D + 2 * WALL <= BODY_D,
        f"pocket {POCKET_W:.1f} x {POCKET_D:.1f} in {BODY_W:.1f} x {BODY_D:.1f}",
    )
    add(
        "HAT fits behind the panel",
        HAT_T + PANEL_T + 2 * WALL <= LID_H,
        f"stack {HAT_T + PANEL_T + 2 * WALL:.1f} of {LID_H:.1f}",
    )
    add(
        "keyboard fits the deck aperture",
        KBD_W + 2 * WALL <= BODY_W and KBD_D <= DECK_D,
        f"{KBD_W:.1f} x {KBD_D:.1f} in {BODY_W - 2 * WALL:.1f} x {DECK_D:.1f}",
    )
    add(
        "boards fit the rear bay, side by side",
        PI_W + SUGAR_W + CELL_W + 4 * 3 <= BODY_W - 2 * WALL,
        f"{PI_W + SUGAR_W + CELL_W + 12:.0f} across {BODY_W - 2 * WALL:.0f}",
    )
    add(
        "deepest board fits the rear bay",
        max(PI_D, SUGAR_D, CELL_D) <= REAR_D - 2 * 3,
        f"deepest {max(PI_D, SUGAR_D, CELL_D):.1f} in {REAR_D - 6:.1f}",
    )
    add(
        "board stack clears the rear bay ceiling",
        max(SUGAR_T, CELL_T, PI_T) + WALL + WALL_TOP <= BASE_H,
        f"{max(SUGAR_T, CELL_T, PI_T) + WALL + WALL_TOP:.1f} of {BASE_H:.1f}",
    )
    add(
        "barrel clears the rear bay ceiling",
        WALL + max(SUGAR_T, CELL_T, PI_T) <= BASE_H - BARREL_R,
        f"barrel underside {BASE_H - BARREL_R:.1f} over stack "
        f"{WALL + max(SUGAR_T, CELL_T, PI_T):.1f}",
    )
    add(
        "barrel leaves a void for the ribbon",
        BARREL_VOID_W >= RIBBON_W + 4,
        f"void {BARREL_VOID_W:.1f} for a {RIBBON_W:.1f} ribbon",
    )
    add(
        "axle spans its knuckle pair",
        AXLE_LEN >= 2 * KNUCKLE_W,
        f"M3 x {AXLE_LEN:.0f} over {2 * KNUCKLE_W:.0f}",
    )
    add(
        "barrel is narrower than the shell",
        BARREL_W < BODY_W - 4 * CORNER_R,
        f"barrel {BARREL_W:.0f} vs {BODY_W - 4 * CORNER_R:.0f}",
    )
    add(
        "corner radius fits the body",
        min(BODY_W, BODY_D) >= 2 * CORNER_R,
        f"2r {2 * CORNER_R:.0f} vs {min(BODY_W, BODY_D):.0f}",
    )
    add(
        "walls are printable at this nozzle",
        WALL >= 2 * NOZZLE,
        f"wall {WALL:.1f} at {NOZZLE:.1f} nozzle",
    )
    add(
        "knuckle bore is printable",
        AXLE_BORE >= 2 * NOZZLE,
        f"bore {AXLE_BORE:.1f} at {NOZZLE:.1f} nozzle",
    )
    return out


def estimated() -> list[str]:
    """Names still resting on a guess. Spec section 9 is the measuring list."""
    return sorted(n for n, s in PROVENANCE.items() if s == ESTIMATED)


def report() -> str:
    """Human-readable audit of the parameter set."""
    lines = ["Writer Deck case parameters", ""]

    lines.append(
        f"  body     {BODY_W:.0f} x {BODY_D:.0f}, r{CORNER_R:.0f}"
        f"   ({OVERALL_D:.0f} deep over the barrel)"
    )
    lines.append(f"  closed   {CLOSED_H:.0f} tall  (base {BASE_H:.0f} + lid {LID_H:.0f})")
    lines.append(f"  window   {WINDOW_W:.1f} x {WINDOW_D:.1f}")
    lines.append(
        f"  deck     {DECK_D:.0f} deep at {DECK_SLOPE:.0f} deg, "
        f"caps {CAP_FRONT_H:.1f} front to {CAP_APEX_H:.1f} rear"
    )
    lines.append(f"  rear bay {REAR_D:.1f} deep x {BODY_W - 2 * WALL:.1f} wide")
    lines.append(f"  barrel   {BARREL_W:.0f} wide, {BARREL_VOID_W:.0f} clear void")
    lines.append(f"  split    {'yes' if SPLIT_BASE else 'no'}   nozzle {NOZZLE}")
    lines.append("")

    failed = [c for c in checks() if not c.ok]
    for c in checks():
        lines.append(f"  [{'ok' if c.ok else 'XX'}] {c.name:<38} {c.detail}")
    lines.append("")

    est = estimated()
    lines.append(f"  {len(est)} values still ESTIMATED -- measure before printing:")
    for name in est:
        lines.append(f"      {name}")
    lines.append("")
    lines.append(f"  {len(failed)} failing check(s)." if failed else "  All checks pass.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
