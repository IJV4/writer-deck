# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Writer Deck is a distraction-free writing application for a Raspberry Pi + Waveshare 7.5" e-ink display (800×480). It runs headlessly as a systemd service, reading input from a USB keyboard via `evdev` and rendering 1-bit PIL images to the display. On non-Pi hardware it falls back to a `NullDriver` (saves PNG frames to `/tmp/writer-deck/`) and a `StdinReader`.

## Commands

```bash
# Install dev dependencies (includes pygame, pytest, mypy, ruff)
pip install -r requirements-dev.txt

# Run all tests with coverage
pytest

# Run a single test file
pytest tests/test_document.py

# Run a single test by name
pytest tests/test_document.py::test_insert_char

# Lint
ruff check .

# Format
ruff format .

# Type check
mypy writerdeck/

# Run on desktop (auto-detects non-Pi; uses NullDriver + StdinReader)
python main.py

# Raspberry Pi setup (one-shot)
./setup.sh

# Deploy to Pi over SSH
./deploy.sh
```

## Architecture

### Entry point and orchestration

`main.py` loads config, sets up logging, then creates and runs `writerdeck/core/app.py::App`. `App` owns all subsystems and runs the main event loop: drain input queue → autosave check → sleep-tier checks → render if changed → watchdog notify → sleep `render_interval_ms`.

### Configuration

`config_default.yaml` in the project root is the base config. Users can create `config.yaml` alongside it; it is deep-merged on top. `writerdeck/core/config.py` loads both into a singleton `Config` with typed property accessors. The `keyboard_input` key (`auto | stdin | evdev | pygame`) controls which input backend is selected at startup.

### Display pipeline

```
Mode.render(doc, session) → RenderFrame
    → writerdeck/display/renderer.py::render() → PIL Image (800×480, 1-bit)
    → RefreshManager decides full vs partial
    → DisplayDriver.display_full() or display_partial()
```

`DisplayDriver` is a structural `Protocol` (`writerdeck/display/driver.py`). Three implementations:
- `EPaperDriver` — real Waveshare hardware (Pi only, requires `waveshare_epd` in `lib/`)
- `NullDriver` — saves PNG frames to `/tmp/writer-deck/` (dev/desktop)
- `PygameDriver` — renders to a pygame window (set `keyboard_input: pygame`)

`RefreshManager` (`writerdeck/display/refresh_manager.py`) tracks a partial-refresh streak and forces a full refresh after `partial_refresh_max_streak` partials or after `idle_full_refresh_seconds` of no input.

### Input pipeline

```
KeyboardReader / StdinReader / PygameKeyboardReader
    → puts (KeyAction, char) onto a queue.Queue
    → App drains queue each loop tick
    → App._handle_action() routes to overlay or mode or global action
```

`KeyMapper` (`writerdeck/input/keymapper.py`) converts raw evdev scancodes + modifier state into `KeyAction` enum values.

### Modes and overlays

All modes extend `BaseMode` (`writerdeck/modes/base_mode.py`) and implement two methods:
- `handle_input(action, char, doc) -> bool` — mutates `Document`, returns True if view changed
- `render(doc, session) -> RenderFrame` — produces the frame dataclass

`RenderFrame` carries `text_lines`, cursor position, optional `stats` dict, selection range, title, and layout hints. The renderer in `display/renderer.py` consumes it.

Three writing modes: `DistractionFreeMode`, `DashboardMode` (sidebar stats), `TypewriterMode` (centered scroll). Mode cycling: Ctrl+Tab / Ctrl+Shift+Tab.

Overlays (`FilePickerOverlay`, `FontPickerOverlay`, `FindOverlay`) intercept all input while active, returning a result dict when dismissed. `App._handle_overlay_result()` acts on the result.

### Core data model

`Document` (`writerdeck/core/document.py`) — the in-memory text buffer with cursor, undo/redo stack, selection, and word-count.

`Session` (`writerdeck/core/session.py`) — tracks words written this session and persists daily totals to `~/.config/writer-deck/daily.json`.

`FileManager` (`writerdeck/utils/file_manager.py`) — lists, loads, saves, and autosaves documents under `~/Documents/writer-deck/`.

### Platform and power

`detect_platform()` (`writerdeck/utils/platform.py`) reads `/proc/device-tree/model` to distinguish Pi Zero 2 W, Pi 5, other Pi, and desktop. The result (`HardwareProfile`) determines default render interval and font size, and whether real hardware drivers are used.

`Power` (`writerdeck/utils/power.py`) polls a PiSugar battery over a Unix socket, triggers low-battery warnings via `StatusBar`, and calls an emergency shutdown callback at the critical threshold.

Three idle sleep tiers (configurable in `sleep_tiers`): display off → CPU powersave governor → systemd suspend.

## Key Constraints

- Display is always 800×480, 1-bit (black/white only). All rendering uses PIL with no greyscale.
- The Waveshare 7.5" V2 stock Python driver does not support true partial refresh — `display_partial` calls `display()` (full refresh) under the hood.
- `waveshare_epd` is not a pip package; it lives in `lib/waveshare_epd/` (copied by `setup.sh` from the Waveshare GitHub repo). `mypy` and coverage are configured to ignore this path.
- Tests run on desktop without any Pi hardware; hardware-dependent code must be guarded by `is_pi` checks or caught exceptions.
