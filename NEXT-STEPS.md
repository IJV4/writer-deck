# Writer Deck — Next Steps

> **2026-07-13 audit fixes:** a batch of confirmed bug fixes landed — see
> [`AUDIT-FIXES-2026-07-13.md`](AUDIT-FIXES-2026-07-13.md). Some are verified by tests; several
> are **pending verification** and need deps installed and/or real hardware. Its "Testing notes"
> section lists exactly what to run before considering them done.

## Status

Hardware is fully operational on Pi Zero 2 W:
- E-ink display working with bounding-box partial refresh across three 1-bit waveform modes (partial / fast-full / GC16 deep clean) and optimized waveform selection
- USB keyboard reading via evdev
- Systemd service autostarts on boot
- Display sleep/wake without white flash

---

## Remaining Work

### UI Improvements

The visual design of the writer interface could be improved:

- **Margins and layout** — adjust text area padding, line height, and margins for a more comfortable reading/writing experience
- **Cursor visibility** — current cursor indicator could be more prominent on the e-ink display
- **Title bar** — consider a more subtle separator between title and content area
- **Dashboard sidebar** — review stat labels and spacing for clarity

### Keyboard Usability (60% keyboard)

The device uses a 60% keyboard (no function row, no dedicated navigation keys). Improve the mapping for missing keys:

- **Page Up / Page Down** — currently mapped, but verify the 60% layout sends the right codes
- ~~**Home / End** — verify these are accessible without a function layer~~ **DONE (2026-07-15):**
  no physical Home/End key exists, so they're mapped to Ctrl+Shift+Up/Ctrl+Shift+Down instead —
  verified live. `SELECT_HOME`/`SELECT_END` (Shift+Home/End) are still only reachable via a
  physical Home key and remain unmapped; still open.
- **Function key alternatives** — consider Fn+layer combos for missing keys
- Review `writerdeck/input/keymapper.py` for any gaps in the current keymap
- ~~**`keyboard_input: auto` startup race**~~ **DONE (2026-07-15):** found live 2026-07-12; fixed by
  extending the by-id resolve retry to 20 attempts × 1s (udev can take ~13s to recreate device
  nodes after a USB replug) and periodically re-checking for the real keyboard while running on a
  guessed fallback device, so a wrong initial guess self-corrects instead of sticking until a
  service restart. Verified live: disconnect → 20 retries → guessed fallback (logged as such) →
  upgraded to the real keyboard 3s later. See `writerdeck/input/keyboard.py`.

### File Management Improvements

- **Document naming** — new documents are auto-named from a timestamp (`YYYY-MM-DD_HH-MM`), which is unambiguous but not descriptive; consider prompting for a name on first save, or auto-titling from the first line of content
- **File picker** — currently lists files by modification time; consider showing file size or word count in the picker
- **Export/backup** — USB export works; consider adding a timestamp or organizing exports into dated folders

---

## Hardware Assembly (if not done)

### 3D Case

Actual build does **not** stack the e-Paper HAT or PiSugar 3 Plus on the Pi's GPIO header — see
`USER_GUIDE.md`'s "Wiring Reference" for the real layout (individual wires, no stacking):
PiSugar 3 Plus PCB + Pi Zero 2 W sit side-by-side behind the keyboard; the e-Paper driver HAT + panel are
mounted separately (e.g. in the clamshell lid) and wired back with 9 individual wires.

- [ ] Measure the side-by-side PiSugar 3 Plus + Pi Zero 2 W footprint for the keyboard compartment
- [ ] Measure the separately-mounted e-Paper HAT PCB (~170mm × 111mm) for the lid compartment
- [ ] Plan wire routing/slack between the two compartments (13 wires total: 4 PiSugar + 9 HAT) —
      the hinge/fold point if it's a clamshell needs enough slack not to strain solder joints
- [ ] USB connector type on your keyboard (for port cutout)
- [ ] Design a two-part friction-fit or M2.5 screwed enclosure (FreeCAD or Fusion 360)
  - Lid: display window cutout (163mm × 98mm + 0.2mm tolerance) over the e-Paper panel
  - Base: PiSugar 3 Plus + Pi Zero + keyboard compartment, port cutouts (USB-C charge, USB keyboard,
    micro-SD)
  - Material: PETG, 2-3mm walls

### Battery Life Testing

- Time a full writing session on PiSugar 3 Plus (expect 4-5 hours)
- Tweak `display_idle_sleep_seconds` (and the `sleep_tiers`) for optimal balance

---

## Dev Setup Reference

If setting up a new dev machine:

```bash
# WSL/Ubuntu
chmod +x setup-dev.sh
./setup-dev.sh
source venv/bin/activate
python main.py

# Deploy to Pi
./deploy.sh 192.168.1.21      # or your Pi's IP
```
