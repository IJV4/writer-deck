# Writer Deck — Next Steps

## Status

Hardware is fully operational on Pi Zero 2 W:
- E-ink display working with bounding-box partial refresh, 4-gray grayscale, and optimized waveform selection
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
- **Home / End** — verify these are accessible without a function layer
- **Function key alternatives** — consider Fn+layer combos for missing keys
- Review `writerdeck/input/keymapper.py` for any gaps in the current keymap
- **`keyboard_input: auto` startup race** — found live 2026-07-12: device resolution runs once at
  startup via `/dev/input/by-id`; if the USB keyboard hasn't finished re-enumerating yet (e.g. right
  after a replug), it silently falls back to the first `/dev/input/event*` device instead of the
  real keyboard, with no error logged. Needs a retry/re-resolve window or a loud warning on
  fallback. See `writerdeck/input/keyboard.py::_resolve_device`.

### File Management Improvements

- **Document naming** — the `untitled-N.txt` scheme is functional but not descriptive; consider prompting for a name on first save, or auto-titling from the first line of content
- **File picker** — currently lists files by modification time; consider showing file size or word count in the picker
- **Export/backup** — USB export works; consider adding a timestamp or organizing exports into dated folders

---

## Hardware Assembly (if not done)

### 3D Case

Actual build does **not** stack the e-Paper HAT or PiSugar 3 on the Pi's GPIO header — see
`USER_GUIDE.md`'s "Wiring Reference" for the real layout (individual wires, no stacking):
PiSugar 3 PCB + Pi Zero 2 W sit side-by-side behind the keyboard; the e-Paper driver HAT + panel are
mounted separately (e.g. in the clamshell lid) and wired back with 9 individual wires.

- [ ] Measure the side-by-side PiSugar 3 + Pi Zero 2 W footprint for the keyboard compartment
- [ ] Measure the separately-mounted e-Paper HAT PCB (~170mm × 111mm) for the lid compartment
- [ ] Plan wire routing/slack between the two compartments (13 wires total: 4 PiSugar + 9 HAT) —
      the hinge/fold point if it's a clamshell needs enough slack not to strain solder joints
- [ ] USB connector type on your keyboard (for port cutout)
- [ ] Design a two-part friction-fit or M2.5 screwed enclosure (FreeCAD or Fusion 360)
  - Lid: display window cutout (163mm × 98mm + 0.2mm tolerance) over the e-Paper panel
  - Base: PiSugar 3 + Pi Zero + keyboard compartment, port cutouts (USB-C charge, USB keyboard,
    micro-SD)
  - Material: PETG, 2-3mm walls

### Battery Life Testing

- Time a full writing session on PiSugar 3 (expect 4-5 hours)
- Tweak `display_sleep_minutes` for optimal balance

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
