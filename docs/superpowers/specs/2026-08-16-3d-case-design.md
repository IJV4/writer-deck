# Writer Deck — 3D-Printed Case Design

**Date:** 2026-08-16
**Status:** Modelled in `hardware/case/`; pending physical measurements
**Last revised:** 2026-09-02 — three decisions below changed during modelling,
each because a check failed. They are marked **[revised]**.
**Supersedes:** the "3D Case" checklist in `NEXT-STEPS.md`

---

## 1. Purpose

A clamshell enclosure for the Writer Deck: Raspberry Pi Zero 2 W, PiSugar 3 Plus,
Waveshare 7.5" V2 e-Paper panel + Driver HAT, and a bare KPrepublic BM43A keyboard PCB.

Aesthetic direction: a **"Polly Pocket" clamshell** — heavy corner radii, chunky soft
volumes, and a hinge barrel visibly narrower than the shells. This is a deliberate
styling choice, not an incidental one, and several engineering decisions below exist
specifically to make it structurally viable.

## 2. Decisions and rationale

| Decision | Choice | Why |
|---|---|---|
| Modelling tool | **build123d** (Python) | Repo is already Python 3.12; real fillets/chamfers; exports STL + STEP; renders dimensioned SVG headlessly on WSL |
| Form factor | **Clamshell** | Portable, protects the panel in transit |
| Material | **PETG, FDM** | ~$10 of filament per case against $120–200 for MJF. Revisions are cheap, which matters because most dimensions here are unverified |
| Production | **Borrowed / library / makerspace printer** | Iteration cost dominates material quality on a first case |
| Bed size | **Unknown — design splittable** | `SPLIT_BASE` parameter emits either a one-piece base or two dovetailed halves with M3 captive nuts. May also be forced by a **per-job time cap** — see §7.1; `base_tray` exceeds a typical 8h library limit even at 0.6mm |
| Proportions | **245 × 160mm both halves, flush** *[revised]* | Lid depth matches base depth. The extra depth goes *behind* the keyboard, not in front — see §2.3 |
| Silhouette | **Compact pill** — r28 corners, single 110mm centre barrel | Chosen from four candidates. Heavy radii also absorb the wide 37.5mm side bezel visually |
| Electronics split | **Pi + PiSugar + cell in base; panel + HAT in lid** | See §3 |
| Hinge crossing | **One 10-way flat ribbon carrying SPI** | See §3 |
| Hinge mechanism | **Two M3 stub axles, O-ring friction, clear centre void** | See §5 |
| Hinge placement | **Axis on the rear face plane; barrel external** *[revised]* | The only placement the lid can actually swing from — see §2.4 |
| Panel retention | **VHB bond to a 1.5mm perimeter ledge** | The bonded panel closes the shell's section and acts as structure |

### 2.1 Why the SPI link crosses the hinge, not the panel FPC

The display chain is `panel → FPC → small connector board → Driver HAT → 9 wires → Pi`.
These two links are not equivalent:

- The **panel-side FPC** carries native source/gate driver signals and is engineered
  for its exact short length. Extending it risks ghosting or dead lines.
- The **HAT→Pi link** is 3.3V SPI at a few MHz and tolerates 300mm without concern.

So the HAT stays in the lid with the panel, and the 9 individual wires are replaced by a
single 10-way flat ribbon crossing the hinge. One flexible cable instead of nine
hand-soldered joints, with the fragile link left untouched.

The HAT's 40-pin GPIO header is **desoldered** — the build never stacked it anyway
(see `USER_GUIDE.md` "Wiring Reference"). Without the header the board is ~3mm and sits
behind the panel inside the lid's 11mm depth.

### 2.2 Why a level rim rather than an external wedge

An early sketch tapered the whole base 32mm → 22mm front-to-back. A flat lid cannot
seat on a rim whose height changes. The base therefore has a **level rim** with the
keyboard deck sloped *inside* it, plus a cosmetic chamfer on the front-bottom edge to
preserve the wedge look.

### 2.3 Why there is no palm rest *[revised]*

The keycaps are ~18mm tall. The rear key row has to sit under the closed lid, so
with any deck slope at all the **front** row lands ~8mm below rim height. A palm
rest at rim height would therefore put an 8mm cliff between the wrists and the
front row — worse than no palm rest at all.

Clamshells with tall keycaps all resolve this the same way: the keyboard runs to
the front edge and there is no palm rest (Penkesu, Beepy). The 45mm that was
going to be a palm rest becomes depth **behind** the keyboard instead, which is
also where the user originally proposed putting the electronics.

The front rim still stands ~8mm proud of the front key row, because the rim has
to reach lid height all the way round. That is ordinary for a high-profile
keyboard case; its inner top edge is chamfered so the hand does not meet a
square corner.

### 2.4 Why the hinge axis sits on the rear face *[revised]*

All lid material lies at `y <= axis` and `z >= axis`, i.e. in the 90–180° quadrant
measured about the axis. Opening by 105° maps that arc to −15–75°. Every point
that ends up *below* the seating plane also ends up at `cos > 0` — behind the rear
face, in free air. Nothing sweeps into the base.

Move the axis even one barrel radius forward and that invariant breaks: lid
material then rotates down through the base's rear wall, and relieving for it
would cut an 11mm gap across the full 245mm width. The first model did exactly
this and `hinge.swing_interference()` caught it — clean to 20°, colliding from
30° on, 2030mm³ of overlap at full open.

The barrel therefore stands **8mm proud of the rear face**: 245 × 160mm body,
168mm overall depth. This is a gain, not a cost — an external barrel narrower
than the shells is precisely the compact-pill silhouette that was chosen.

## 3. Physical architecture

```
  LID  11mm
  +-------------------------------------------+
  |  panel 170x111  (window 163.6 x 98.3)     |
  |  bezels 40.7 side / 28.8 front / 32.8 rear|
  |  Driver HAT centred behind panel          |
  +-------------------------------------------+
        || 10-way ribbon, on-axis through barrel
  === HINGE — 110mm barrel, ON the rear face ==   <- stands 8mm proud
  +-------------------------------------------+
  |  rear bay 76.4mm   Pi + PiSugar + cell    |
  |                    side by side, 30mm high|
  |-------------------------------------------|
  |  keyboard  76mm    BM43A bare PCB, 5 deg  |
  |  front lip  4mm                           |
  +-------------------------------------------+
  BASE  34mm rim        caps 25.7 front -> 32.3 rear
```

Weight distribution: lid ~195g (shells 195 + panel 90 + HAT 20), base ~440g
(shells 244 + keyboard 200). Bottom-heavy, and at full open the lid's centre of
mass is only ~20mm behind the rear face against a base ten times its moment —
it will not tip.

**What mounts where.** `base_bottom` is the structural floor and carries
everything that bolts down: the Pi *and* the keyboard, which is bottom-mounted
because the deck aperture has to clear the whole PCB and so leaves no material
above the mounting points. `base_tray` is walls, deck skirt and ceiling only.
Removing the floor plate takes the electronics out as a unit and leaves no post
standing on a surface that just went away.

## 4. Part breakdown

| Part | Carries |
|---|---|
| `lid_front` | 163.4 × 98.4 window, r28 corners, 1.5mm panel ledge, full-width spine rail, 2 diagonal gussets, HAT pocket, 2 hinge knuckles |
| `lid_back` | Flat cover; access to panel and HAT |
| `base_tray` | Rim, sloped deck skirt + 231 × 77 aperture, rear bay ceiling, r28 corners, 2 hinge knuckles, port cutouts, front-rim chamfer |
| `base_bottom` | Floor plate, foot recesses, Pi standoffs, keyboard standoffs |
| `barrel_shroud` | Cosmetic half-tube over the 66mm ribbon void |
| `foot` × 4 | Recesses for adhesive rubber pads (modelled as recesses, not parts) |

Both shells split front/back so electronics are serviceable without disturbing the hinge.

### 4.1 Lid stiffening

Cutting a 163 × 98 window through the lid face removes most of the shell's torsional
stiffness — an open section is far weaker than a closed one — and a 110mm barrel leaves
67.5mm of lid cantilevered off each end. Three measures restore it:

1. **Rear spine rail** — 4 × 8mm, full 245mm width. Converts the barrel's point load into
   a distributed one. Largest single contribution.
2. **Diagonal gussets** — from the rail at each barrel end, forward into the side walls.
3. **Bonded panel** — VHB to a full-perimeter ledge re-closes the section.

Cost: ~12cm³ of PETG (~$0.30) and a local wall thickening to 4mm at the rear.

## 5. Hinge

```
   |<-- 22 -->|<------- 66mm clear void ------>|<-- 22 -->|
   [base|lid ]                                 [ lid|base]
     M3x25                                        M3x25
   O-ring friction                            O-ring friction
                     ribbon crosses on-axis
```

The axis lies **on the rear face plane** at seating height — see §2.4. Each end is
an 11mm base knuckle plus an 11mm lid knuckle sharing one M3 × 25 stub axle. The
middle 66mm belongs to neither shell and stays clear.

There is **no hard stop**: this is a free-stop friction hinge, so the lid holds
any angle. `hinge.swing_interference()` verifies zero lid-into-base overlap at
every 15° from 0 to 105.

**A single long rod is not usable** — it would occupy exactly the space the ribbon needs.
Two stubs are also easier to source than a 180mm rod, and let friction be tuned at each
end independently.

**On-axis routing is deliberate.** A bundle crossing on the hinge axis *twists* over its
length rather than *bending* at a point; torsion over ~66mm is survivable indefinitely,
whereas a fixed bend radius is what fatigues conductors.

**Friction: O-ring at each stub**, seated in an annular groove on the lid
knuckle's outboard face, so the ring is captured between the two knuckle faces
and the M3 sets its compression. Groove depth is 2/3 of the cord. Selected against the stated criteria — cheap,
long-lasting, and good to open. Nyloc backs off over months, so its feel degrades; an
O-ring holds constant and self-compensates as the PETG wears. Tuned by swapping durometer
(70A firm / 50A soft) with no reprint. Nyloc remains a drop-in fallback on identical
geometry.

## 6. Fits and tolerances

| Feature | Nominal | Note |
|---|---|---|
| Panel window | 163.6 × 98.3 | active area + 0.2/side; flared 1.2mm toward the viewer |
| Panel pocket | panel outer + 0.3/side | 1.5mm bonding ledge |
| Knuckle bore | 3.2mm | M3 clearance; FDM prints holes ~0.15mm undersize |
| Knuckle axial gap | 0.3mm per face | |
| Shell mating lip | 0.2mm | slip fit; a 2.5mm-wide ring, not a plate |
| Panel bonding ledge | 3.6mm per side | bezel overlap onto the panel — the actual VHB width |
| Wall | 1.8mm | 2.4mm at rail and knuckles; 2.5mm across the rear bay ceiling |
| Corner radius | 28mm | outer shell |
| Keyboard deck slope | 5° *[revised]* | 6° left 0.4mm of keycap clearance under the closed lid; 5° gives 1.5mm |

**FDM print orientation:** the hinge axis must lie parallel to the bed so layer lines run
along each barrel, never across it. This is a note that must reach whoever runs the
printer — it is the difference between a working hinge and one that splits at a layer.

## 7. Hardware BOM

| Item | Qty | Note |
|---|---|---|
| M3 × 25 screw | 2 | hinge stub axles |
| M3 × 8 screw | 10 | shell closures |
| M3 heat-set insert | 10 | ~$8/100; far better than printed threads in PETG |
| M2.5 × 6 screw + standoff | 4 | keyboard PCB — count pending measurement |
| O-ring assortment kit | 1 | ~$6 |
| VHB tape | — | panel bond |
| 10-way flat ribbon | 1 | ~$3 |
| PETG filament | ~500g | ~$10 |

**Cost:** ~$45–50 for the first build, since several items are bought as kits (heat-set
inserts $8/100, O-ring assortment $6, a full 1kg spool $20). A second case costs ~$13.

### 7.1 Print time

Material is now **measured off the model, not estimated**: 348cm³ / ~442g for the
five printed parts, plus 33cm³ / ~42g for the four coupons. Solid volume, so a
real slice comes in under it. Run `export.py` for the current per-part table.

| Part | Volume | Bed footprint |
|---|---|---|
| `base_tray` | 112.6 cm³ | 245 × 168 |
| `base_bottom` | 79.3 cm³ | 245 × 160 |
| `lid_back` | 79.0 cm³ | 245 × 160 |
| `lid_front` | 74.7 cm³ | 245 × 168 |
| `barrel_shroud` | 2.5 cm³ | 65 × 15 |

Time estimates below are slicer-free; take real figures from slicing the STLs.

| Machine class | 0.4mm nozzle, 0.2mm layers | 0.6mm nozzle, 0.3mm layers |
|---|---|---|
| Ender 3 / older FDM | 32 – 40 h | 16 – 20 h |
| Prusa MK4 / Bambu A1 | 14 – 20 h | 7 – 10 h |
| Bambu P1S / X1C | 10 – 14 h | 5 – 7 h |

Per part at 0.4mm on an Ender-class machine: `base_tray` ~110cm³ / 10–13h,
`base_bottom` ~85cm³ / 8–10h, `lid_back` ~78cm³ / 7–9h, `lid_front` ~75cm³ / 7–9h,
shroud and feet ~5cm³ / 30min.

**Print at 0.6mm nozzle, 0.3mm layers.** It roughly halves the time at no cost to this
design — the only tight features are the M3 knuckle bores and the 1.5mm panel ledge, and
both tolerate a 0.6mm nozzle. There is no fine detail anywhere on an r28 shell.

The three validation coupons in §10 total ~20cm³ — about 1.5h on an Ender-class machine,
25 minutes on a Bambu.

## 8. Ports and access

Keyboard USB is **internal** — Pi and keyboard now share the base, so it is a short
jumper with no cutout.

- **PiSugar USB-C charge** — cutout, base right side
- **PiSugar power button** — 4mm hole with a printed cap
- **micro-SD** — no cutout. `base_bottom` unscrews. It is a set-and-forget card and a
  slot there would weaken the wall

## 9. Measurements required before modelling

Every dimension in this document is estimated. These must be taken with calipers and
written into `params.py` before any part is exported.

`export.py` prints the outstanding list on every run — 16 values at the time of
writing. In priority order:

- [ ] **BM43A keycap top height above PCB** (assumed 18.4) — *highest risk, see §11*
- [ ] BM43A PCB outline and mounting-hole positions (assumed 230 × 76; holes unknown)
- [ ] PiSugar 3 Plus PCB outline — no longer critical, see §11
- [ ] PiSugar cell footprint and true thickness (assumed 10mm)
- [ ] Waveshare panel module outer dimensions
- [ ] Panel FPC exit edge and free ribbon length
- [ ] Driver HAT PCB outline with header removed (assumed 65 × 30 × 3)
- [ ] Pi Zero 2 W mounting-hole spacing (58 × 23mm nominal — verify)

## 10. Validation plan

Print three coupons before committing to full parts. ~20cm³ total, roughly an hour each.

1. **Hinge coupon** — one knuckle pair, stub, O-ring. Tests bore fit and friction feel.
   Print this first; the hinge is both the highest risk and the whole aesthetic.
2. **Window corner coupon** — one r28 corner with the panel ledge. Tests panel fit and
   how the radius reads at real scale.
3. **Keyboard aperture coupon** — a 3 × 3 patch of aperture plus standoffs. Tests deck
   height and slope.

## 11. Open risks

**~~PiSugar 3 Plus footprint~~ — resolved.** Dropping the palm rest (§2.3) turned the
rear strip into a 76.4 × 241.4 × 30mm bay. Even an 85 × 56mm board fits with room
beside it for the Pi and the cell. This was the top risk and is no longer one.

**Keycap height is now the binding measurement.** `KBD_CAP_H` sets the base
height, which sets the closed height, which sets the whole silhouette. At the
assumed 18.4mm the rear caps clear the closed lid by 1.5mm. Every extra
millimetre of keycap costs a millimetre of `BASE_H` or forces the slope down
further. Measure this before anything else.

**Deck and PCB angles are set by two different parts.** The deck skirt belongs to
`base_tray`, the keyboard standoffs to `base_bottom`. Both read `DECK_SLOPE`, so
they agree by construction, but the tolerance stack across the shell joint is
real. `coupon_keyboard_deck` spans both parts specifically to test it.

**The spine rail is notched.** The ribbon exits on the centreline, which cuts a
~15mm gap in the otherwise full-width 245mm rail. Acceptable, but it is the
rail's weakest point and it sits directly over the barrel.

**Ribbon length.** The on-axis loop needs slack for a full 105° swing without tension.
Length to be derived once the barrel geometry is modelled.

## 12. Code layout

```
hardware/case/
  params.py      every dimension, with provenance, plus geometric self-checks
  _common.py     footprint, knuckles, bosses, zone boundaries
  lid.py         lid_front, lid_back
  base.py        base_tray, base_bottom
  hinge.py       barrel_shroud, and the swing interference test
  coupons.py     the four validation coupons
  export.py      -> build/*.stl + build/*.step, and the full check run
  README.md      print settings, orientation, assembly order
  .venv/         build123d lives here, not in the app venv (OpenCascade is ~500MB)
```

Keeping all dimensions in `params.py` makes a caliper correction a one-line edit followed
by a re-export, which is the intended workflow given §9.

**Every dimension carries its provenance** — `MEASURED`, `DATASHEET`, `ESTIMATED`,
`DERIVED` or `CHOSEN` — and `params.py` prints which are still guesses. Fourteen
geometric invariants are asserted on every run (keycap clearance, board fit,
printability at the chosen nozzle, barrel void vs ribbon width). Three of the
revisions in this document came from one of those checks going red rather than
from re-reading the prose.

`export.py` exits non-zero if a check fails, if any part comes out as more than
one disconnected solid, or if the lid collides with the base anywhere in its
swing. Coupons are cut from the real parts with a boolean rather than modelled
separately, so they cannot drift from what they validate.

## 13. Deferred

- Bed size and whether `SPLIT_BASE` is enabled — depends which printer is found.
  `SPLIT_BASE` is declared in `params.py` but the split geometry is not modelled yet
- Final O-ring durometer — chosen by feel from the hinge coupon
- Keyboard mounting-hole positions — currently nominal insets, pending measurement
- Dimensioned SVG output — `export.py` writes STL and STEP only
- Surface finish and colour
- Whether the palm rest gets a texture or a bonded pad
