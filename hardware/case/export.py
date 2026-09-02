"""Build every part to ``build/`` and report on it.

    python export.py            # everything, including the swing test
    python export.py --fast     # skip the swing test (it is the slow part)
    python export.py --only lid_front base_tray

Parts are modelled in the assembled pose; export drops each one onto z = 0.
No part needs re-orienting beyond that: the hinge axis already lies parallel to
the bed, which is the one print-orientation rule that matters here. Layer lines
run *along* each barrel rather than across it, so the hinge is not loaded on the
weak axis. Slicing a barrel upright would put every layer boundary in shear.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import base
import coupons
import hinge
import lid
import params as P
from build123d import Part, Pos, export_step, export_stl

BUILD = Path(__file__).parent / "build"

#: Everything that gets exported, in assembly order.
ALL_PARTS: dict[str, object] = {**base.PARTS, **lid.PARTS, **hinge.PARTS, **coupons.PARTS}

#: PETG, near enough, for a solid part. Real prints come in under this.
DENSITY_G_CM3 = 1.27


def _on_bed(part: Part) -> Part:
    """Drop a part so its lowest point sits on z = 0."""
    return Pos(0, 0, -part.bounding_box().min.Z) * part


def build(names: list[str], fast: bool) -> int:
    """Export the named parts. Returns a process exit code."""
    BUILD.mkdir(exist_ok=True)
    failures: list[str] = []

    print(P.report())
    print()

    if any(not c.ok for c in P.checks()):
        failures.append("parameter checks")

    print(f"{'part':22s} {'volume':>10s} {'mass':>8s}  {'bed footprint':>16s}  solids")
    total = 0.0
    for name in names:
        part = _on_bed(ALL_PARTS[name]())
        bb = part.bounding_box()
        total += part.volume
        n_solids = len(part.solids())

        export_stl(part, str(BUILD / f"{name}.stl"))
        export_step(part, str(BUILD / f"{name}.step"))

        note = "" if n_solids == 1 else "  <-- NOT ONE SOLID"
        if n_solids != 1:
            failures.append(f"{name} is {n_solids} disconnected solids")
        print(
            f"{name:22s} {part.volume / 1000:8.1f} cm3 {part.volume / 1000 * DENSITY_G_CM3:6.0f} g"
            f"  {bb.size.X:6.1f} x {bb.size.Y:6.1f}  {n_solids:6d}{note}"
        )

    print(f"{'TOTAL':22s} {total / 1000:8.1f} cm3 {total / 1000 * DENSITY_G_CM3:6.0f} g")

    for name in names:
        part = ALL_PARTS[name]()
        if part.bounding_box().size.X > 250 or part.bounding_box().size.Y > 250:
            print(f"\n  note: {name} exceeds a 250mm bed -- see SPLIT_BASE in params.py")

    if not fast:
        print("\nswing test -- lid rotated into the base, by opening angle")
        for angle, overlap in hinge.swing_interference(step=15.0):
            ok = overlap < 1.0
            if not ok:
                failures.append(f"lid collides with base at {angle:.0f} deg")
            print(f"  {angle:5.0f} deg  {overlap:9.1f} mm3   {'ok' if ok else 'COLLISION'}")

    est = P.estimated()
    print(f"\n{len(est)} dimensions are still ESTIMATED. Do not print a full part on these.")

    if failures:
        print("\nFAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"\nWrote {2 * len(names)} files to {BUILD}/")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fast", action="store_true", help="skip the swing test")
    ap.add_argument("--only", nargs="+", metavar="PART", choices=sorted(ALL_PARTS))
    args = ap.parse_args()
    return build(args.only or list(ALL_PARTS), args.fast)


if __name__ == "__main__":
    sys.exit(main())
