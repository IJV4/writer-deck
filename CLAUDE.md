# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

This workspace includes multiple projects: a writer-deck (Python/Pygame e-paper device for Raspberry Pi), an SWE study dashboard (TypeScript), and seed enrichment tooling. Always check the current working directory and project structure before making changes.

## Environment Notes

- Primary dev environment is WSL. Do NOT assume npm/node are installed — check first with `which node` and `which npm`.
- For Python projects, always check for and activate the venv before running commands.
- GUI apps (pygame, browser) cannot open directly in WSL headless — instruct user to run in their terminal instead.

## Configuration

### .env and Config Loading

When configuring .env files, always verify: 1) the file is in the correct directory relative to the entry point, 2) dotenv is loaded BEFORE any module that reads env vars, 3) confirm the values are actually picked up by printing/logging them.

## Safety

### Dangerous Operations

Never use `rm -rf` on project directories. When excluding folders from scp or copy operations, use `--exclude` flags rather than deleting. Always confirm destructive file operations with the user first.

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
    → writerdeck/display/renderer.py::render() → PIL Image (800×480, 1-bit or "L")
    → RefreshManager decides full vs partial
    → App._render_and_refresh() selects the right DisplayDriver method
    → EPaperDriver / NullDriver / PygameDriver
```

`DisplayDriver` is a structural `Protocol` (`writerdeck/display/driver.py`). Three implementations:
- `EPaperDriver` — real Waveshare hardware (Pi only, requires `waveshare_epd` in `lib/`)
- `NullDriver` — saves PNG frames to `/tmp/writer-deck/` (dev/desktop)
- `PygameDriver` — renders to a pygame window (set `keyboard_input: pygame`)

#### Display methods and waveform modes

`EPaperDriver` exposes four display methods, each using a different e-ink waveform:

| Method | Waveform | Speed | Use |
|--------|----------|-------|-----|
| `display_partial(img)` | init_part (CDI 0xA9) | ~0.3s, minimal blink | Per-keystroke updates (bounding-box diff) |
| `display_full(img)` | init_fast | ~1s, 2-3 blinks | Regular streak/idle full refreshes |
| `display_full_4gray(img)` | init_4Gray | ~1.5s | Anti-aliased grayscale rendering |
| `display_clean(img)` | init (GC16) | ~3-4s, 8 blinks | Deep ghost-clearing after long idle |

`EPaperDriver` tracks waveform state in `_mode` (`"full"` / `"fast"` / `"part"` / `"4gray"` / `None`) to skip redundant ~100ms re-inits when consecutive calls use the same waveform.

#### Bounding-box partial refresh

`display_partial()` does a row-level diff between the new buffer and `_last_buf`:
1. Single scan finds the bounding box (`y_start`..`y_end`) and counts changed rows.
2. If `changed_rows / HEIGHT > 0.3` (escalation threshold), falls back to `init_fast + display()`.
3. Otherwise calls `init_part + display_Partial(slice, 0, y_start, WIDTH, y_end)`.
4. The slice is pre-inverted (`b ^ 0xFF`) because `display_Partial` uses CDI register `0xA9` which flips pixel polarity vs CDI `0x10` used in full/fast modes.
5. `_last_buf` is updated with the changed rows after each partial, or replaced in full after escalation.

`_last_buf` is preserved through `sleep()` — e-ink retains its image without power, so the diff remains valid after wake.

`wake()` calls `epd.init()` without `epd.Clear()` (no white flash). This is distinct from `init()` which calls `Clear()` on first boot.

#### 4-gray mode

When `use_4gray: true`, full refreshes call `display_full_4gray()` with a PIL `"L"` mode image (renderer renders with `grayscale=True`). After a 4-gray refresh, `_last_buf` is set to `None` because controller RAM is in 4-gray format — the next `display_partial()` falls back to fast-full to reload 1-bit DTM buffers before bounding-box partials can resume.

#### Deep clean (GC16)

`display_clean()` uses `init()` (GC16 waveform) for thorough ghost-clearing. `App._render_and_refresh()` calls it only when `idle_secs >= idle_deep_clean_seconds` (default 300s). Regular full refreshes use the faster `init_fast` waveform via `display_full()`.

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

- Display is always 800×480. Default rendering is 1-bit (black/white). Pass `grayscale=True` to `renderer.render()` to get a PIL `"L"` mode image for 4-gray mode.
- The Waveshare 7.5" V2 stock Python driver's `display_Partial` sets CDI register `0xA9`, which inverts pixel polarity vs full/fast modes. The slice passed to it must be pre-inverted (`b ^ 0xFF`).
- `waveshare_epd` is not a pip package; it lives in `lib/waveshare_epd/` (vendored — `setup.sh` copies it from the Waveshare GitHub repo). `mypy` and coverage are configured to ignore this path.
- Tests run on desktop without any Pi hardware; hardware-dependent code must be guarded by `is_pi` checks or caught exceptions.
