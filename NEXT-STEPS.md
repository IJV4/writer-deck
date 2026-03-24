# Writer Deck — Next Steps

## Immediate: Get running on WSL (Ubuntu)

### 1. Clone/copy the project
```bash
# If using git:
git clone <your-repo-url> ~/projects/writer-deck
cd ~/projects/writer-deck

# Or just copy the folder from the Mac
```

### 2. Install dependencies
```bash
sudo apt update
sudo apt install python3-dev python3-venv libfreetype6-dev libjpeg-dev libopenjp2-7-dev fonts-hack-ttf
python3 -m venv venv
source venv/bin/activate
pip install Pillow PyYAML pytest
# evdev, spidev, pisugar are Pi-only — skip on WSL dev machine
```

### 3. Run tests
```bash
python -m pytest tests/ -v
```

### 4. Verify NullDriver rendering
```bash
python main.py
# Press Ctrl+C after a moment — check /tmp/writer-deck/ for PNG frames
# (keyboard input won't work without evdev, but initial render should save)
```

### 5. Bundle a font
```bash
# Download Hack or JetBrains Mono .ttf into assets/fonts/
wget -O assets/fonts/Hack-Regular.ttf \
  https://github.com/source-foundry/Hack/releases/download/v3.003/Hack-v3.003-ttf.zip
# (or just: sudo apt install fonts-hack-ttf — already in step 2)
```

---

## On the Pi Zero 2 W

### 6. Run setup.sh
```bash
chmod +x setup.sh
./setup.sh
# This handles: system packages, SPI/I2C, lgpio, Waveshare driver clone,
# venv, pisugar daemon, systemd service, user groups
# Reboot after for SPI/I2C/BT changes to take effect
```

### 7. First hardware test
```bash
# Find your keyboard:
evtest
# Note the /dev/input/event* path, put it in config.yaml:
echo "keyboard_device: /dev/input/by-id/YOUR-KEYBOARD-ID" > config.yaml

# Run it:
source venv/bin/activate
python main.py
# Text should appear on the e-ink display
```

### 8. Tune refresh behavior
Edit `config.yaml`:
```yaml
partial_refresh_max_streak: 20   # lower = more full refreshes (cleaner but slower)
render_interval_ms: 500          # how often the display updates
font_size: 14                    # smaller = more text visible, slower to render
display_sleep_minutes: 5         # 0 to disable idle sleep
```

---

## Hardware Assembly

### 9. Connect PiSugar 3
- Attach PiSugar 3 to the back of Pi Zero via POGO pins (no GPIO conflict with e-ink HAT)
- Install daemon (setup.sh does this)
- Test: `python -c "from writerdeck.utils.power import Power; p = Power(); p._update(); print(p.battery_level)"`

### 10. Apply power optimizations
Already in setup.sh, but verify:
- HDMI disabled: `tvservice -o` in `/etc/rc.local`
- Bluetooth disabled: `dtoverlay=disable-bt` in `/boot/config.txt`
- CPU governor: `echo powersave | sudo tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor`

---

## 3D Case

### 11. Measure your assembled stack
- [ ] Waveshare 7.5" HAT PCB exact dimensions (expect ~170mm × 111mm)
- [ ] Pi Zero + PiSugar stacked height
- [ ] SPI ribbon/connector clearance
- [ ] USB connector type on your keyboard (for port cutout)

### 12. Design enclosure
- Tool: FreeCAD or Fusion 360
- Two-part friction-fit or M2.5 screwed enclosure
- Front shell: display window cutout (163mm × 98mm + 0.2mm tolerance)
- Back shell: component compartments, port cutouts (USB-C charge, USB keyboard, micro-SD)
- Material: PETG, 2-3mm walls
- Total footprint estimate: ~175mm × 115mm × 20-25mm

### 13. Order print
- Upload STL to JLC3DP, Craftcloud, or Treatstock
- Add 0.2mm clearance on component seats, 0.3mm on port cutouts

---

## Polish (after end-to-end works)

### 14. File picker UI
- Currently Ctrl+O just cycles documents — add a simple list selector rendered on the e-ink display

### 15. Low battery warning banner
- Add overlay rendering in `renderer.py` when `power.is_low` is True
- Show at <20% in distraction-free and typewriter modes (dashboard always shows battery)

### 16. Stress-test battery life
- Time a full writing session on PiSugar 3 (expect 4-5 hours)
- Tweak `display_sleep_minutes` for optimal balance

### 17. Enable autostart
```bash
sudo systemctl enable writer-deck.service
sudo systemctl start writer-deck.service
# Pi boots directly into Writer Deck — no desktop, no distractions
```
