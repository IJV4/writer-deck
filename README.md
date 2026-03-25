# Writer Deck

A distraction-free writing device built on Raspberry Pi Zero 2 W with a Waveshare 7.5" e-ink display.

No notifications. No browser. Just writing.

---

## Hardware

| Component | Model |
|-----------|-------|
| Computer | Raspberry Pi Zero 2 W |
| Display | Waveshare 7.5" e-Paper HAT V2 (800×480, B&W) |
| Battery | PiSugar 3 (5000 mAh) |
| Input | Any USB HID keyboard |

The Pi runs headlessly as a systemd service. The e-ink display retains its image with the power off, making it ideal for a low-power writing appliance.

---

## Features

- **Three writing modes** — Distraction-Free, Dashboard (with stats sidebar), and Typewriter (auto-scrolling)
- **Optimized e-ink refresh** — bounding-box partial refresh (~0.3s per keystroke), automatic escalation to fast-full for large changes, 4-gray grayscale anti-aliasing
- **Smart sleep** — display sleeps after idle, wakes without a white flash (e-ink retains image)
- **Progressive power saving** — display off → CPU powersave → system suspend, all reversed on keypress
- **Document management** — autosave, atomic writes, crash recovery, file picker overlay
- **Find / Replace** — search and replace within the current document
- **Font picker** — switch system fonts at runtime
- **USB export** — Ctrl+E copies all documents to a plugged-in USB drive
- **Battery monitoring** — PiSugar 3 level and estimated remaining time in the Dashboard

---

## Quick Start

### On Raspberry Pi

```bash
# 1. Clone the repo onto the Pi (or deploy with deploy.sh from a dev machine)
git clone https://github.com/youruser/writer-deck ~/writer-deck
cd ~/writer-deck

# 2. Run setup (handles SPI/I2C, deps, venv, systemd service, PiSugar)
chmod +x setup.sh
./setup.sh
sudo reboot
```

After reboot, configure your keyboard (one-time):

```bash
ls /dev/input/by-id/        # find the path ending in "event-kbd"
cat > ~/writer-deck/config.yaml <<EOF
keyboard_input: evdev
keyboard_device: /dev/input/by-id/usb-YOUR_KEYBOARD-event-kbd
EOF
sudo systemctl restart writer-deck
```

### On a Dev Machine (WSL / Ubuntu / macOS)

```bash
chmod +x setup-dev.sh && ./setup-dev.sh
source venv/bin/activate
python main.py              # NullDriver — saves PNG frames to /tmp/writer-deck/
```

### Pygame Emulator (desktop, interactive)

```yaml
# config.yaml
keyboard_input: pygame
```

```bash
python main.py              # opens a live 800×480 window
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+S | Save |
| Ctrl+N | New document |
| Ctrl+O | Open document (file picker) |
| Ctrl+Q | Quit |
| Ctrl+Tab / Ctrl+Shift+Tab | Next / previous mode |
| Ctrl+Z / Ctrl+Y | Undo / Redo |
| Ctrl+F | Find / Replace |
| Ctrl+Shift+F | Font picker |
| Ctrl+E | Export to USB |

---

## Configuration

Copy `config_default.yaml` as a reference. Create `config.yaml` with only the values you want to override — it deep-merges on top of the defaults.

Key options:

```yaml
# Display quality
use_4gray: true                     # Anti-aliased text (screens bought after Oct 2023)
idle_deep_clean_seconds: 300        # GC16 ghost-clear after 5 min idle (0 = disabled)
partial_refresh_max_streak: 20      # Partial refreshes before a forced full

# Power
sleep_tiers:
  display_off_minutes: 5
  cpu_powersave_minutes: 15
  system_suspend_minutes: 30

# Writing
daily_goal_words: 500
font_family: Hack
font_size: 14
```

---

## Display Refresh

Writer Deck uses four e-ink waveform modes, selected automatically:

| Mode | Speed | When |
|------|-------|------|
| Bounding-box partial | ~0.3s | Per-keystroke (< 30% of rows changed) |
| Fast-full | ~1s | Large changes or periodic full refresh |
| 4-gray grayscale | ~1.5s | Full refresh when `use_4gray: true` |
| GC16 deep clean | ~3-4s | After long idle (ghost removal) |

This keeps the display smooth during active typing while running a proper ghost-clearing cycle when you step away.

---

## Development

```bash
pip install -r requirements-dev.txt

pytest                      # run tests with coverage
mypy writerdeck/            # type check
ruff check .                # lint
ruff format .               # format

./deploy.sh 192.168.1.21    # deploy to Pi over SSH
```

Tests run entirely on desktop — no Pi hardware required.

---

## Project Structure

```
writer-deck/
├── main.py                     # Entry point
├── config_default.yaml         # Default configuration
├── setup.sh                    # Pi one-shot setup
├── deploy.sh                   # rsync deploy to Pi
├── writerdeck/
│   ├── core/
│   │   ├── app.py              # Main event loop + orchestrator
│   │   ├── document.py         # Text buffer, cursor, undo/redo
│   │   ├── session.py          # Word tracking + daily goal
│   │   └── config.py           # Config loader
│   ├── display/
│   │   ├── driver.py           # EPaperDriver, NullDriver (+ Protocol)
│   │   ├── pygame_driver.py    # Desktop emulator driver
│   │   ├── renderer.py         # RenderFrame → PIL Image
│   │   └── refresh_manager.py  # Full/partial streak logic
│   ├── input/
│   │   ├── keymapper.py        # Scancodes → KeyAction
│   │   ├── keyboard.py         # evdev reader
│   │   └── stdin_reader.py     # Terminal fallback
│   ├── modes/
│   │   ├── distraction_free.py
│   │   ├── dashboard.py
│   │   ├── typewriter.py
│   │   └── find_overlay.py     # Find / Replace
│   └── utils/
│       ├── platform.py         # Pi vs desktop detection
│       ├── power.py            # PiSugar battery
│       └── file_manager.py     # Save, load, autosave
├── tests/                      # 200+ pytest tests
└── lib/waveshare_epd/          # Waveshare driver (vendored)
```

---

## License

MIT
