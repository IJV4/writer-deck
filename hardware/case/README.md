# Writer Deck — 3D-printed case

Parametric clamshell for the Raspberry Pi Zero 2 W, PiSugar 3 Plus, Waveshare
7.5" V2 e-Paper panel + Driver HAT, and a bare KPrepublic BM43A keyboard PCB.

Design rationale lives in
[`docs/superpowers/specs/2026-08-16-3d-case-design.md`](../../docs/superpowers/specs/2026-08-16-3d-case-design.md).
This file covers building, printing and assembling it.

## Status

**Not printable yet.** 16 dimensions are still guesses — `export.py` lists them
every run. Measure those, then print the coupons, then print a part.

## Building the models

`build123d` pulls in OpenCascade (~500MB), so it lives in its own venv rather
than the application one, which gets deployed to the Pi.

```sh
python3 -m venv .venv
.venv/bin/pip install build123d

.venv/bin/python params.py          # dimension audit, no geometry
.venv/bin/python export.py          # everything -> build/, with checks
.venv/bin/python export.py --fast   # skip the swing test
.venv/bin/python export.py --only coupon_hinge_base coupon_hinge_lid
```

`export.py` exits non-zero if a parameter check fails, if any part comes out as
more than one disconnected solid, or if the lid collides with the base anywhere
in its swing. Treat a non-zero exit as "do not send this to a printer".

## Layout

```
  hinge axis ON the rear face -- barrel stands proud
                    v
  +--------------------+ ---
  |  lid: panel + HAT  |  11mm
  +--------------------+ ---
  |  rear bay: Pi,     |
  |  PiSugar, cell     |  34mm
  |--------------------|
  |  keyboard, 5 deg   |
  +--------------------+ ---
  |<--- 160mm --->| + 8mm barrel
```

Three things about this layout are load-bearing, and each was forced by a check
that failed first:

**No palm rest.** 18mm keycaps mean the rear key row has to fit under the closed
lid, which puts the front row ~8mm below rim height. A palm rest at rim height
would put a cliff between the wrists and the front row, so the keyboard runs to
the front lip instead — as on the Penkesu and Beepy — and every board moves to
the bay behind it. The front rim still stands ~8mm proud of the front keys;
that is ordinary for a high-profile keyboard case, and its inner edge is
chamfered so it is not a square corner under the hand.

**The hinge axis is on the rear face plane, not inside the body.** All lid
material sits in the 90–180° quadrant about the axis. Opening 105° maps that to
−15–75°, and every point that ends up below the seating plane also ends up
behind the rear face — in free air. Move the axis forward and the lid sweeps
down through the base's rear wall; relieving for that would cut an 11mm gap
across the full 245mm width. `hinge.swing_interference()` fails loudly if this
is ever broken.

**Everything that bolts down mounts to `base_bottom`.** The Pi and the keyboard
both. `base_tray` is walls, deck skirt and ceiling only, so removing the floor
plate takes the electronics out as a unit and leaves no post floating.

## Printing

| Setting | Value | Why |
|---|---|---|
| Material | PETG | Tougher than PLA at the knuckles; no enclosure needed |
| Nozzle | **0.6mm** | Halves print time. Tightest features are the M3 bores and the 1.5mm ledge; both tolerate it |
| Layers | 0.3mm | |
| Walls | 3 | The shells are thin; strength is all perimeter |
| Infill | 20% gyroid | |
| Supports | Under the deck skirt and the knuckle bores only | |

**Orientation: print every part exactly as exported.** The hinge axis already
lies parallel to the bed, so layer lines run *along* each barrel instead of
across it. Standing a barrel upright puts every layer boundary in shear and is
the difference between a working hinge and one that splits on the first open.

Largest footprint is 245 × 168mm. On a smaller bed set `SPLIT_BASE = True` in
`params.py`. Check the per-job **time limit** as well as bed size if the printer
is a library or makerspace machine — `base_tray` is the long pole.

## Order of work

1. **Measure.** `export.py` prints the outstanding list. The PiSugar 3 Plus
   outline used to be the highest risk; the rear bay is now 76 × 241 × 30mm and
   swallows anything plausible, so the binding one is `KBD_CAP_H` — it sets the
   whole base height.
2. **Print the coupons** (~33cm³, about an hour). In order:
   - `coupon_hinge_base` + `coupon_hinge_lid` — bore fit, O-ring friction, and
     the feel of the open/close. Print these first; the hinge is both the
     highest risk and the whole aesthetic.
   - `coupon_window_corner` — panel drops into the pocket, and how r28 reads at
     real scale against a 40mm bezel.
   - `coupon_keyboard_deck` — deck height and slope at the tightest point.
3. **Tune the O-ring** by durometer (70A firm / 50A soft). No reprint needed.
4. Print the full parts.

## Assembly

1. Heat-set 10 M3 inserts into `base_tray`, 10 into `lid_front`.
2. Bond the panel into `lid_front`'s pocket with VHB on the 3.6mm ledge. This is
   semi-permanent, and the bonded panel is structure — it re-closes the section
   the window cut open.
3. Seat the HAT in its pocket behind the panel. Its 40-pin header must be
   desoldered first; the build never stacked it.
4. Route the 10-way ribbon along the lid channel and down through the barrel.
   It must cross **on the axis**, so it twists over its length rather than
   bending at a point. A fixed bend radius is what fatigues conductors.
5. Close the lid with `lid_back`.
6. Mount the Pi and the keyboard to `base_bottom`; stick the PiSugar and cell
   down on pads.
7. Interleave the knuckles, drop an O-ring into each groove, and run one
   M3 × 25 through each barrel end. Tighten until the lid holds its angle
   anywhere — it is a free-stop friction hinge with no hard stop.
8. Close the base with `base_bottom`.

## Files

| File | Holds |
|---|---|
| `params.py` | Every dimension, with provenance, plus the geometric self-checks |
| `_common.py` | Footprint, knuckles, bosses, zone boundaries |
| `lid.py` | `lid_front`, `lid_back` |
| `base.py` | `base_tray`, `base_bottom` |
| `hinge.py` | `barrel_shroud`, and the swing interference test |
| `coupons.py` | The four validation coupons, cut from the real parts |
| `export.py` | STL + STEP into `build/`, and the full check run |

Coupons are cut out of the real parts with a boolean rather than modelled
separately, so they cannot drift away from what they are meant to validate.
