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
| Ctrl+Shift+Up / Ctrl+Shift+Down | Jump to line start / end |
| Ctrl+Left / Ctrl+Right | Jump by word |
| Page Up / Page Down | Scroll page |

This keyboard has no physical Home/End key. Ctrl+Up/Down are already Page Prev/Next
and Ctrl+A/E are already Select-All/Export, so Home/End were mapped to the otherwise-unused
Ctrl+Shift+Up/Down instead (`writerdeck/input/keymapper.py`).

### Selection

| Shortcut | Action |
|----------|--------|
| Shift+Arrows | Select character by character |
| Ctrl+Shift+Left / Right | Select by word |
| Ctrl+A | Select all |

> Select-to-line-start/end (`SELECT_HOME`/`SELECT_END`) is only reachable via a physical
> Shift+Home/End key, which this keyboard doesn't have — not yet remapped to an alternate
> combo. Tracked as future work alongside the rest of the 60%-keyboard key mapping.

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

Ctrl+N creates a new file auto-named from the current timestamp, `YYYY-MM-DD_HH-MM` (e.g. `2026-07-13_14-30`), using the extension set by `default_format` (`.txt` by default, or `.md`). If two documents are created within the same minute, a `-2`, `-3`, ... suffix is appended. The previous document is autosaved first.

### Undo / Redo

The undo stack holds up to 100 snapshots. Fast consecutive keystrokes (within 1 second) are coalesced into a single undo group, so undoing a burst of typing reverses it all at once.

---

## Overlays

Overlays appear on top of the current text and capture all keyboard input until dismissed.

### File Picker (Ctrl+O)

Lists all documents in the documents directory. Navigate with Up/Down arrows, press Enter to open, Escape to cancel.

### Font Picker (Ctrl+Shift+F)

Lists installed system fonts (`.ttf` and `.otf`), one entry per family — weight/style
variants (e.g. Lato's 18 files) and icon fonts (e.g. Font Awesome) are collapsed out or
excluded so only genuinely distinct, readable typefaces show up. Each entry is rendered
in its own typeface, with a Serif/Sans/Monospace typology label, so you can see its shape
before selecting it. Navigate with Up/Down arrows (fast partial refresh — only opening and
closing the picker does a full refresh), press Enter to apply, Escape to cancel. The change
takes effect immediately.

The Pi currently has Courier Prime, DejaVu (Sans/Sans Mono/Serif), EB Garamond, Hack, Lato,
and Liberation (Mono/Sans/Serif) installed — all via `setup.sh`'s apt package list
(`fonts-hack-ttf`, `fonts-liberation`, `fonts-courier-prime`, `fonts-ebgaramond`, `fonts-lato`,
`fonts-dejavu-core`). None of these are guaranteed by the base Raspberry Pi OS image alone.

### Find / Replace (Ctrl+F)

Two fields: Find and Replace. Type your search term, then:

- **Enter** — find next occurrence from cursor position
- **Tab** — switch between Find and Replace fields
- **Enter** (with Replace filled) — replace at cursor position
- **Escape** — close

The status bar shows "Found at line N" or "Not found".

---

## Power Management

Requires a PiSugar 3 Plus battery board. Enable in config with `enable_battery_monitor: true`.

### Battery Monitoring

- Polls battery level every 60 seconds via Unix socket
- Shows battery bar in Dashboard sidebar: `[■■■□□] 38%`
- Estimates remaining hours based on drain rate history
- Shows battery in other modes when level drops below `battery_warning_percent` (default 15%)
- Auto-shuts down at `battery_shutdown_percent` (default 10%): autosaves, wipes the panel to
  white, and issues `systemctl poweroff` after 3 consecutive critical (non-charging) samples

### Startup Low-Battery Gate

On boot, if the battery reads below `battery_shutdown_percent` and the device is **not**
charging, Writer Deck refuses to start the editor. It shows a "Battery low (N%) / Please
plug in the charger" message, waits 5 seconds, wipes the panel to white, and powers off. If
the device is charging, it boots normally regardless of level. This is skipped entirely if
`enable_battery_monitor` is off.

`battery_shutdown_percent` is the primary, graceful cutoff (it drives both this startup gate
and the runtime critical-shutdown path above). PiSugar's own firmware-level
`auto_shutdown_level` (set in `/etc/pisugar-server/config.json` on the Pi, outside this repo)
should stay **below** `battery_shutdown_percent` — it's a hardware backstop that only matters
if the app-level shutdown somehow doesn't fire in time.

### Sleep Tiers

Three progressive power-saving stages during idle periods, plus an independent screensaver:

| Trigger | Default | Action | Wake |
|------|---------|--------|------|
| Tier 1 | 20s idle (`display_idle_sleep_seconds`) | Display deep-sleep (bistable — image stays visible, panel just stops drawing power) | Any keypress |
| Screensaver | 5 min idle (`display_screensaver_seconds`) | Blank the panel to solid white (burn-in mitigation) | Any keypress |
| Tier 2 | 15 min idle (`sleep_tiers.cpu_powersave_minutes`) | CPU governor set to powersave | Any keypress |
| Tier 3 | 30 min idle (`sleep_tiers.system_suspend_minutes`) | Full system suspend | Any keypress (GPIO) |

The screensaver fires on total idle time independent of Tier 1 — it wakes the panel if
already asleep, paints a blank white frame, and re-sleeps it, so a long-idle static page
doesn't retain a ghost image. `sleep_tiers.display_off_minutes` is only a fallback for Tier 1
when `display_idle_sleep_seconds` is set to `0`. All tiers reverse instantly on keypress.

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
partial_refresh_max_streak: 5       # Partial refreshes before a full one
idle_full_refresh_seconds: 10       # Full refresh after N seconds idle
full_refresh_max_seconds: 300       # Wall-clock backstop: force a full refresh at least this often
display_idle_sleep_seconds: 20      # Deep-sleep the panel after N seconds of no keystroke
display_screensaver_seconds: 300    # Blank to a white "paused" frame after this much total idle time, independent of panel sleep (0 = disabled)
show_title_bar: true                # Show doc name at top
idle_deep_clean_seconds: 300        # GC16 ghost-clear after N idle seconds (0 = disabled)

# Writing
daily_goal_words: 500               # Daily word count target
default_format: txt                 # File extension for new documents (txt or md); existing docs keep their own extension

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
# Panel sleep is controlled by display_idle_sleep_seconds (under Display).
# The tiers below govern the CPU governor and system suspend after longer idle.
sleep_tiers:
  display_off_minutes: 5            # Fallback panel-off trigger when display_idle_sleep_seconds is 0
  cpu_powersave_minutes: 15
  system_suspend_minutes: 30
enable_battery_monitor: true
battery_warning_percent: 15
battery_shutdown_percent: 10        # runtime critical-shutdown AND the startup low-battery gate both use this; PiSugar's own auto_shutdown_level should be set lower as a backstop only
pisugar_socket: /tmp/pisugar-server.sock

# Logging & metrics
log_dir: ~/.config/writer-deck/logs
enable_perf_metrics: false          # Log p50/p95/max render timings every 30s
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
- PiSugar 3 Plus (5000 mAh, POGO pin connection)
- Any USB HID keyboard
- 16 GB+ microSD with Raspberry Pi OS Bookworm Lite

### Wiring Reference

This build does **not** stack the e-Paper HAT or PiSugar 3 Plus directly on the Pi's GPIO header.
PiSugar 3 Plus, its PCB, and the Pi Zero 2 W sit side-by-side (no stacking) behind the keyboard; the
e-Paper driver HAT + panel live separately (e.g. in the clamshell lid) and connect back to the Pi
over individual wires. 13 wires total (4 PiSugar + 9 e-Paper HAT).

**PiSugar 3 Plus PCB → Pi Zero 2 W (4 wires):**

| PiSugar 3 Plus Pad | Pi Zero Pin | GPIO       | Purpose               |
|---------------|-------------|------------|------------------------|
| 5V OUT        | Pin 4       | 5V         | Power delivery         |
| GND           | Pin 6       | GND        | Ground return           |
| SDAT          | Pin 3       | GPIO 2 (SDA) | Battery data (I2C)   |
| SSCL          | Pin 5       | GPIO 3 (SCL) | Battery clock (I2C)  |

**Do not connect MDAT/MSCL.** Per PiSugar's own docs, MDAT/MSCL is the "I2C main (master)
interface, no function at this time" — the pins that actually talk to the Pi are SDAT/SSCL ("I2C
slave interface, connected to Pi's I2C interface"). An earlier version of this table had these
swapped (MDAT/MSCL wired, SDAT/SSCL left disconnected), which left the I2C bus completely silent —
`i2cdetect` showed zero devices on either bus. Confirmed live on 2026-07-12: rewiring to SDAT→Pin
3/SSCL→Pin 5 immediately brought up both `0x57` and `0x68` on the bus and real battery data through
`pisugar-server`. If you accidentally wire both pairs (as also happened live — tying MDAT+SDAT to
the same Pi pin, MSCL+SSCL to the other), the bus stays silent too; only SDAT/SSCL should be
connected, MDAT/MSCL left floating.

**e-Paper Driver HAT Rev2.3 → Pi Zero 2 W (9 wires):**

| HAT Pin | Pi Zero Pin | GPIO          | Purpose                                                   |
|---------|-------------|---------------|------------------------------------------------------------|
| VCC     | Pin 1       | 3.3V          | HAT logic power                                             |
| GND     | Pin 9       | GND           | Ground                                                       |
| DIN     | Pin 19      | GPIO 10 (MOSI)| SPI data                                                     |
| CLK     | Pin 23      | GPIO 11 (SCLK)| SPI clock                                                    |
| CS      | Pin 24      | GPIO 8 (CE0)  | SPI chip select                                              |
| DC      | Pin 22      | GPIO 25       | Data/command select                                          |
| RST     | Pin 11      | GPIO 17       | Hardware reset                                                |
| BUSY    | Pin 18      | GPIO 24       | Display busy signal                                           |
| PWR     | Pin 12      | GPIO 18       | Display power enable — required, without it the panel has no power and BUSY times out silently |

HAT DIP switches: Display Config = **B** (0.47R, correct driving strength for the 7.5" V2 panel),
Interface Config = **0** (4-line SPI, required by the Waveshare Python driver).

No pin conflicts: PiSugar uses I2C (GPIO 2/3) + power; the e-Paper HAT uses SPI (GPIO 8/10/11) +
control lines (GPIO 17/18/24/25) — fully independent buses.

**Pi Zero 2 W USB ports:** the inner port (closer to center/HDMI) is data, used for the keyboard;
the outer port (at the edge) is power-only and unused here since PiSugar supplies power.

**Debugging notes:** persistent `ReadBusy timed out` errors on the e-Paper HAT were previously
caused by two separate issues found in sequence — a misplaced BUSY wire, and later a missing PWR
wire. Both are required for the display to respond.

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

`EPaperDriver` uses three waveform modes: bounding-box partial (~0.3s), fast-full (~1s), and GC16 deep clean (~3-4s). The app selects the right one automatically based on how much changed and how long the user has been idle. (A 4-gray grayscale mode was evaluated and removed — it produced stray grey pixels on this hardware.)

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
