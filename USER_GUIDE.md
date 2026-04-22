# Writer Deck User Guide

A portable, distraction-free writing device built on Raspberry Pi Zero 2 W with a 7.5" e-ink display.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Writing Modes](#writing-modes)
3. [Keyboard Shortcuts](#keyboard-shortcuts)
4. [Document Management](#document-management)
5. [Overlays](#overlays)
6. [Power Management](#power-management)
7. [Configuration](#configuration)
8. [Hardware Setup](#hardware-setup)
9. [Desktop Development](#desktop-development)
10. [Deployment](#deployment)
11. [Troubleshooting](#troubleshooting)
12. [Project Structure](#project-structure)

---

## Quick Start

### On Raspberry Pi Zero 2 W

```bash
chmod +x setup.sh
./setup.sh
sudo reboot
# Writer Deck auto-starts via systemd after reboot
```

After reboot, configure your keyboard device (one-time):

```bash
# Find the stable by-id path for your keyboard
ls /dev/input/by-id/
# Use the symlink ending in "event-kbd" — avoid "System Control" / "Consumer Control"

cat > ~/writer-deck/config.yaml <<EOF
keyboard_input: evdev
keyboard_device: /dev/input/by-id/usb-YOUR_KEYBOARD-event-kbd
EOF

sudo systemctl restart writer-deck
```

### On a Dev Machine (WSL/Ubuntu)

```bash
chmod +x setup-dev.sh
./setup-dev.sh
source venv/bin/activate
python main.py
```

### With the Pygame Emulator

Add to `config.yaml`:

```yaml
keyboard_input: pygame
```

Then `python main.py` opens a live 800x480 window.

---

## Writing Modes

Cycle between modes with **Ctrl+Tab** (forward) or **Ctrl+Shift+Tab** (backward).

### Distraction-Free

Full-screen text canvas with a minimal word count at the bottom. Maximum focus on writing.

### Dashboard

Text on the left (564px), stats sidebar on the right (220px):

- **Words** — current document word count
- **Session** — elapsed time (e.g. "1h 23m")
- **Written** — words added this session
- **Goal** — visual progress bar toward daily target
- **Battery** — level + estimated remaining (when enabled)

### Typewriter

The active line stays fixed at ~40% from the top. Text scrolls upward as you type, like a typewriter carriage. Forces a full display refresh on each newline for tactile feedback.

---

## Keyboard Shortcuts

### Editing

| Shortcut | Action |
|----------|--------|
| Backspace | Delete character before cursor |
| Delete | Delete character at cursor |
| Enter | Insert new line |
| Ctrl+Z | Undo |
| Ctrl+Y / Ctrl+Shift+Z | Redo |
| Ctrl+Backspace | Delete word before cursor |

### Navigation

| Shortcut | Action |
|----------|--------|
| Arrow keys | Move cursor |
| Home / End | Jump to line start / end |
| Ctrl+Left / Ctrl+Right | Jump by word |
| Page Up / Page Down | Scroll page |

### Selection

| Shortcut | Action |
|----------|--------|
| Shift+Arrows | Select character by character |
| Shift+Home / Shift+End | Select to line start / end |
| Ctrl+Shift+Left / Right | Select by word |
| Ctrl+A | Select all |

### Files and Modes

| Shortcut | Action |
|----------|--------|
| Ctrl+S | Save |
| Ctrl+N | New document |
| Ctrl+O | Open document (file picker) |
| Ctrl+Q | Quit |
| Ctrl+Tab | Next writing mode |
| Ctrl+Shift+Tab | Previous writing mode |

### Features

| Shortcut | Action |
|----------|--------|
| Ctrl+F | Find / Replace |
| Ctrl+Shift+F | Font picker |
| Ctrl+E | Export to USB |
| Escape | Close any overlay |

---

## Document Management

### Storage

Documents are stored as plain text files in `~/Documents/writer-deck/` (configurable). Both `.txt` and `.md` files are recognized.

### Autosave

Every 90 seconds (configurable), if the document has unsaved changes, a `.autosave` copy is written alongside the main file. On the next load, if the autosave is newer than the main file, it is automatically recovered.

### Atomic Writes

All saves use a temp file + fsync + rename pattern. If the system crashes mid-write, neither the main file nor the autosave is corrupted.

### New Documents

Ctrl+N creates a new file named `untitled-1.txt`, `untitled-2.txt`, etc. The previous document is autosaved first.

### Undo / Redo

The undo stack holds up to 100 snapshots. Fast consecutive keystrokes (within 1 second) are coalesced into a single undo group, so undoing a burst of typing reverses it all at once.

---

## Overlays

Overlays appear on top of the current text and capture all keyboard input until dismissed.

### File Picker (Ctrl+O)

Lists all documents in the documents directory. Navigate with Up/Down arrows, press Enter to open, Escape to cancel.

### Font Picker (Ctrl+Shift+F)

Lists all available system fonts. Navigate with Up/Down arrows, press Enter to apply the selected font, Escape to cancel. The change takes effect immediately.

### Find / Replace (Ctrl+F)

Two fields: Find and Replace. Type your search term, then:

- **Enter** — find next occurrence from cursor position
- **Tab** — switch between Find and Replace fields
- **Enter** (with Replace filled) — replace at cursor position
- **Escape** — close

The status bar shows "Found at line N" or "Not found".

---

## Power Management

Requires a PiSugar 3 battery board. Enable in config with `enable_battery_monitor: true`.

### Battery Monitoring

- Polls battery level every 60 seconds via Unix socket
- Shows battery bar in Dashboard sidebar: `[■■■□□] 38%`
- Estimates remaining hours based on drain rate history
- Shows battery in other modes when level drops below `battery_warning_percent` (default 15%)
- Auto-shuts down at `battery_shutdown_percent` (default 3%)

### Sleep Tiers

Three progressive power-saving stages during idle periods:

| Tier | Default | Action | Wake |
|------|---------|--------|------|
| 1 | 5 min idle | Display off | Any keypress |
| 2 | 15 min idle | CPU governor set to powersave | Any keypress |
| 3 | 30 min idle | Full system suspend | Any keypress (GPIO) |

All tiers reverse instantly on keypress.

---

## Configuration

Writer Deck uses two YAML files:

- `config_default.yaml` — shipped defaults (do not edit)
- `config.yaml` — your overrides (gitignored, created manually)

User values are deep-merged on top of defaults. Only include keys you want to change.

### All Options

```yaml
# Display
display_model: epd7in5_V2          # Waveshare e-Paper model
font_family: Hack                   # System font name
font_size: 14                       # Font size in points
render_interval_ms: 500             # Display update frequency (ms)
partial_refresh_max_streak: 20      # Partial refreshes before a full one
idle_full_refresh_seconds: 10       # Full refresh after N seconds idle
show_title_bar: true                # Show doc name at top
use_4gray: false                    # 4-gray grayscale (recommended for screens bought after Oct 2023)
idle_deep_clean_seconds: 300        # GC16 ghost-clear after N idle seconds (0 = disabled)

# Writing
daily_goal_words: 500               # Daily word count target
default_format: txt                 # File extension for new docs

# Modes
mode_order:
  - distraction_free
  - dashboard
  - typewriter

# Files
documents_dir: ~/Documents/writer-deck
autosave_interval_seconds: 90

# Input
keyboard_device: auto               # evdev device path or "auto"
keyboard_input: auto                # auto | stdin | evdev | pygame

# Power
display_sleep_minutes: 5
sleep_tiers:
  display_off_minutes: 5
  cpu_powersave_minutes: 15
  system_suspend_minutes: 30
enable_battery_monitor: true
battery_warning_percent: 15
battery_shutdown_percent: 3
pisugar_socket: /tmp/pisugar-server.sock

# Logging
log_dir: ~/.config/writer-deck/logs
```

### Example config.yaml

```yaml
keyboard_input: evdev
keyboard_device: /dev/input/by-id/usb-qmkbuilder_keyboard-event-kbd
font_family: Hack
font_size: 14
daily_goal_words: 500
sleep_tiers:
  display_off_minutes: 10
```

---

## Hardware Setup

### Required Components

- Raspberry Pi Zero 2 W (512 MB RAM)
- Waveshare 7.5" e-Paper HAT V2 (800x480, 1-bit B&W, SPI)
- PiSugar 3 (5000 mAh, POGO pin connection)
- Any USB HID keyboard
- 16 GB+ microSD with Raspberry Pi OS Bookworm Lite

### setup.sh

The one-shot setup script handles:

1. System packages (python3-dev, fonts-hack-ttf, image libs, evtest, avahi-daemon)
2. Hostname set to `writer-deck` + Avahi enabled (advertises `writer-deck.local` on the LAN)
3. SPI and I2C enabled in boot config
4. Bluetooth disabled, HDMI disabled (power savings)
5. lgpio compiled and installed (Bookworm requirement)
6. PiSugar daemon installed
7. Waveshare e-Paper driver vendored to `lib/waveshare_epd/`
8. Python venv created with dependencies (evdev, spidev, gpiozero, lgpio)
9. Data directories created
10. Systemd service generated and enabled with the correct user and paths

### Systemd Service

```bash
sudo systemctl enable writer-deck    # Start on boot
sudo systemctl start writer-deck     # Start now
sudo systemctl status writer-deck    # Check status
journalctl -u writer-deck -f         # Follow logs
```

The service includes a 120-second watchdog. If the app hangs, systemd restarts it automatically.

---

## Desktop Development

### Display Drivers

| Driver | When | Output |
|--------|------|--------|
| EPaperDriver | On Raspberry Pi | Real e-ink display |
| NullDriver | Non-Pi, default | PNGs saved to `/tmp/writer-deck/` |
| PygameDriver | `keyboard_input: pygame` | Live 800x480 SDL window |

`EPaperDriver` uses four waveform modes: bounding-box partial (~0.3s), fast-full (~1s), 4-gray grayscale (~1.5s), and GC16 deep clean (~3-4s). The app selects the right one automatically based on how much changed and how long the user has been idle.

### Input Backends

| Reader | When | Source |
|--------|------|--------|
| KeyboardReader | Pi (evdev) | `/dev/input/event*` |
| StdinReader | Desktop default | Raw terminal input |
| PygameKeyboardReader | `keyboard_input: pygame` | SDL key events |

### Dev Tools

Install everything with `pip install -r requirements-dev.txt`, then:

```bash
pytest                              # Run tests with coverage
mypy writerdeck/                    # Type check
ruff check writerdeck/ tests/       # Lint
ruff check --fix writerdeck/        # Auto-fix lint issues
ruff format writerdeck/ tests/      # Format code
```

Coverage reports are generated at `htmlcov/index.html`.

---

## Deployment

### First-time SSH setup

```bash
# Generate a key if you don't have one yet
ssh-keygen -t ed25519 -C "writerdeck-dev" -f ~/.ssh/id_ed25519

# Copy it to the Pi (enter Pi password once)
ssh-copy-id pi@<PI_IP>
```

### Deploy to Pi

```bash
./deploy.sh                         # Defaults to pi@writer-deck.local
./deploy.sh 192.168.1.50            # Custom host (IP)
./deploy.sh 192.168.1.50 myuser     # Custom host and user
```

> **WSL users:** WSL does not resolve `.local` mDNS by default. Either install
> `avahi-daemon libnss-mdns` on WSL, or add a static entry to `/etc/hosts`:
> ```
> 192.168.1.101  writer-deck.local
> ```

The script rsyncs only the files needed to run the app (excludes `venv`, `tests/`, `config.yaml`, dev tools, and docs). If the systemd service is already installed it restarts automatically; otherwise it prints a reminder to run `setup.sh` first.

### Stopping the app

If the app is unresponsive to Ctrl+C, kill it from another SSH session:

```bash
ssh pi@<PI_IP> "pkill -f main.py"
```

### USB Export

Press **Ctrl+E** to export all documents to a mounted USB drive. The app searches `/media/` and `/mnt/` for mounted drives and copies all `.txt` and `.md` files to a `writer-deck/` folder on the drive. Autosave files are skipped.

---

## Troubleshooting

### Keyboard not responding

QMK and other multi-interface keyboards expose several event devices (System Control, Consumer Control, mouse). Only the main HID keyboard interface responds to typing. Use the stable by-id path ending in `event-kbd`:

```bash
ls /dev/input/by-id/
# e.g. usb-qmkbuilder_keyboard-event-kbd
```

Avoid using `/dev/input/event*` paths directly — device numbers can shift after a reboot.

### Display shows NullDriver warning

If you see `EPaperDriver unavailable, falling back to NullDriver`, check:

1. SPI is enabled — `ls /dev/spidev*` should show `spidev0.0` and `spidev0.1`. If not, reboot (SPI requires a reboot after `setup.sh`).
2. Waveshare driver is present — `ls ~/writer-deck/lib/waveshare_epd/epd7in5_V2.py`. If missing, run `setup.sh` again.
3. Pi-only Python deps are installed — `~/writer-deck/venv/bin/pip show spidev gpiozero lgpio`

### Service keeps restarting

Check logs for the cause:

```bash
journalctl -u writer-deck -n 50 --no-pager
```

Common causes:
- Wrong keyboard device path — update `config.yaml` and restart
- Missing Python dep — install it into the venv and restart
- Watchdog timeout — the app must run without crashing for 120 seconds

### App is unresponsive / won't quit

Kill it from another SSH session:

```bash
ssh pi@<PI_IP> "pkill -f main.py"
```

---

## Project Structure

```
writer-deck/
├── main.py                         # Entry point
├── config_default.yaml             # Default configuration
├── setup.sh                        # Pi setup script (one-time)
├── setup-dev.sh                    # Dev machine setup script
├── deploy.sh                       # Remote deployment
├── writer-deck.service             # Systemd unit
├── requirements.txt                # Runtime dependencies
├── requirements-dev.txt            # Dev dependencies
├── pyproject.toml                  # pytest, mypy, ruff config
├── writerdeck/
│   ├── core/
│   │   ├── app.py                  # Event loop + orchestrator
│   │   ├── document.py             # Text buffer, cursor, undo/redo
│   │   ├── session.py              # Word tracking + daily ledger
│   │   └── config.py               # Config loader + validation
│   ├── display/
│   │   ├── driver.py               # EPaperDriver + NullDriver
│   │   ├── pygame_driver.py        # Pygame emulator driver
│   │   ├── renderer.py             # RenderFrame to PIL Image
│   │   ├── refresh_manager.py      # Full/partial refresh logic
│   │   ├── fonts.py                # Font loading + discovery
│   │   ├── status_bar.py           # Timed status messages
│   │   └── splash.py               # Startup splash screen
│   ├── input/
│   │   ├── keymapper.py            # Scancode to KeyAction mapping
│   │   ├── keyboard.py             # evdev keyboard reader
│   │   ├── stdin_reader.py         # Terminal fallback reader
│   │   └── pygame_reader.py        # Pygame emulator reader
│   ├── modes/
│   │   ├── base_mode.py            # BaseMode + RenderFrame
│   │   ├── distraction_free.py     # Full-canvas mode
│   │   ├── dashboard.py            # Text + stats sidebar
│   │   ├── typewriter.py           # Auto-scrolling mode
│   │   ├── overlay.py              # Overlay ABC
│   │   ├── font_picker.py          # Font selection
│   │   ├── file_picker.py          # Document selection
│   │   └── find_overlay.py         # Find / Replace
│   └── utils/
│       ├── platform.py             # Pi vs desktop detection
│       ├── power.py                # PiSugar battery management
│       ├── file_manager.py         # Save, load, autosave
│       ├── usb_export.py           # USB export utility
│       ├── markdown.py             # Markdown line parsing
│       └── text_wrapper.py         # Pixel-aware line wrapping
├── tests/                          # 200+ pytest tests
└── lib/waveshare_epd/              # Waveshare driver (setup.sh)
```
