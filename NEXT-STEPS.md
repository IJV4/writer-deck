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

### File Management Improvements

- **Document naming** — the `untitled-N.txt` scheme is functional but not descriptive; consider prompting for a name on first save, or auto-titling from the first line of content
- **File picker** — currently lists files by modification time; consider showing file size or word count in the picker
- **Export/backup** — USB export works; consider adding a timestamp or organizing exports into dated folders

---

## Hardware Assembly (if not done)

### 3D Case

- [ ] Measure assembled stack: Waveshare HAT PCB (~170mm × 111mm), Pi Zero + PiSugar stacked height
- [ ] SPI ribbon/connector clearance
- [ ] USB connector type on your keyboard (for port cutout)
- [ ] Design two-part friction-fit or M2.5 screwed enclosure (FreeCAD or Fusion 360)
  - Front: display window cutout (163mm × 98mm + 0.2mm tolerance)
  - Back: component compartments, port cutouts (USB-C charge, USB keyboard, micro-SD)
  - Material: PETG, 2-3mm walls, ~175mm × 115mm × 20-25mm total

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
