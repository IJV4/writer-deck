# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Notes

- This is a **pure Python 3.12+ project** (no node/npm). Always activate the venv before running commands: `source venv/bin/activate`.
- Cross-platform: `setup-dev.sh` targets WSL/Ubuntu (apt-based); development also happens on macOS. `setup.sh` is Pi-only.
- GUI apps (the `pygame` driver) cannot open in a headless/WSL session — instruct the user to run `python main.py` in their own terminal instead.

## Configuration

Config is **YAML**, not `.env`. `config_default.yaml` is the base; a user-created `config.yaml` deep-merges on top (see the Configuration section under Architecture). There is no `dotenv`. The only environment variable read is `NOTIFY_SOCKET` (systemd watchdog, in `app.py`).

## Safety

Never use `rm -rf` on project directories. When excluding folders from `deploy.sh`/scp/rsync, use `--exclude` flags rather than deleting. Confirm destructive file operations with the user first.

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
    → App._render_and_refresh() selects the right DisplayDriver method
    → EPaperDriver / NullDriver / PygameDriver
```

`DisplayDriver` is a structural `Protocol` (`writerdeck/display/driver.py`). Three implementations:
- `EPaperDriver` — real Waveshare hardware (Pi only, requires `waveshare_epd` in `lib/`)
- `NullDriver` — saves PNG frames to `/tmp/writer-deck/` (dev/desktop)
- `PygameDriver` — renders to a pygame window (set `keyboard_input: pygame`)

#### Display methods and waveform modes

`EPaperDriver` exposes three display methods, each using a different e-ink waveform:

| Method | Waveform | Speed | Use |
|--------|----------|-------|-----|
| `display_partial(img)` | init_part (CDI 0xA9) | ~0.3s, minimal blink | Per-keystroke updates (bounding-box diff) |
| `display_full(img)` | init_fast | ~1s, 2-3 blinks | Regular streak/idle full refreshes |
| `display_clean(img)` | init (GC16) | ~3-4s, 8 blinks | Deep ghost-clearing after long idle |

`EPaperDriver` tracks waveform state in `_mode` (`"full"` / `"fast"` / `"part"` / `None`) to skip redundant ~100ms re-inits when consecutive calls use the same waveform. Every hardware display op is wrapped in a bounded retry (`DISPLAY_OP_ATTEMPTS = 3`, re-initialising the current waveform between tries); persistent failure raises `DisplayError`, which `App` catches to degrade to a headless mode (input/autosave keep running, the panel is retried on an interval) rather than crash — see `_enter_headless()` / `_maybe_retry_panel()` in `app.py`.

4-gray/grayscale rendering was evaluated and removed (not present in this codebase) — it was a source of stray grey pixels on this hardware. `display()` calls are never passed a `prev_image`/DTM1 delta either, for the same ghost-prevention reason; the vendored driver's optional `prev_image` parameter is unused by design.

#### Bounding-box partial refresh

`display_partial()` does a row-level diff between the new buffer and `_last_buf`, split into *multiple disjoint dirty rectangles* rather than one merged bounding box:
1. `compute_dirty_bands(old, new, height, row_bytes, gap)` (a pure, unit-testable function) scans rows once and returns a list of half-open changed row-bands `[(y_start, y_end), ...]` plus the total `changed_rows` count. Runs of changed rows separated by `<= gap` (default `BAND_MERGE_GAP = 32`) unchanged rows merge into one band; larger gaps split — so a cursor-line edit and a footer edit become two small windows, not one ~79%-tall box.
2. If `changed_rows / HEIGHT > 0.3` (escalation threshold — counts only differing rows, not merged spans), falls back to `init_fast + display()`.
3. Otherwise, for each band it computes the horizontal changed-column window with `compute_x_window(...)` (also pure/testable), snaps to 8-px byte boundaries, slices the buffer to that row **and** column range, and calls `init_part + display_Partial(slice, x_start, y_start, x_end, y_end)`.
4. The per-band slice is pre-inverted (`b ^ 0xFF`) because `display_Partial` uses CDI register `0xA9` which flips pixel polarity vs CDI `0x10` used in full/fast modes. The XOR still applies to the X/Y-windowed slice.
5. `_last_buf` is a `bytearray`; changed rows are spliced in place after each band (no full-buffer reallocation per keystroke), or the whole buffer is replaced after escalation.

Volatile stats (the `Words` footer, dashboard timer/sidebar) are decoupled from the per-keystroke path: `App` snapshots `frame.stats` on each full refresh and freezes the frame's stats to that snapshot on partials, so the stats region renders identical bytes and never drags its rows into the dirty diff. Live stats land on the next full/streak/idle refresh.

`_last_buf` is preserved through `sleep()` — e-ink retains its image without power, so the diff remains valid after wake.

`wake()` calls `epd.init_fast()` without `epd.Clear()` (no white flash) — chosen over the slower GC16 `init()` to also minimize the wake-flash itself. `init()` (the boot-time entry point) uses the same `init_fast()` (no `Clear()`), for the same reason; the one-time `Clear()` still happens in `close()` on shutdown.

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

### Deploy & the systemd unit (OPS-1 / OPS-2)

**Single source of truth for the unit.** `writer-deck.service` is a **template**, not a valid unit as checked in — it carries `__USER__` / `__WORKDIR__` / `__VENV__` placeholders. `setup.sh` `sed`-substitutes them and installs the result to `/etc/systemd/system/writer-deck.service`. Do NOT re-introduce a second copy of the unit (e.g. a here-doc in `setup.sh`); add or change directives **only in the template**. All prior directives live here (`KillSignal`, `TimeoutStopSec`, `ExecStopPost` from FAULT-2; `WatchdogSec` from FAULT-4; `Restart`, `OOMScoreAdjust`, etc.).

**Atomic, revertible deploy.** `deploy.sh` never mutates the live tree. Remote layout under `~/writer-deck/`: `releases/<ts>/` (each deploy), a shared `venv/` (created by `setup.sh`, symlinked into each release, survives rollbacks), and a `current -> releases/<ts>` symlink. The unit's `WorkingDirectory`/`ExecStart`/`ExecStopPost`/`PYTHONPATH` all resolve through `current`, so a deploy is: rsync into a fresh `releases/<ts>/` (no `--delete`), atomically swap `current` (`ln -sfn … .tmp && mv -Tf .tmp current`), restart the service, then prune to the newest 5 releases. `deploy.sh --rollback` repoints `current` at the previous release and restarts; `deploy.sh --list` shows releases + current. Pruning only ever removes dirs directly under `releases/`, never the active release, never data dirs; `rm -rf` is not used. Data (`config.yaml`, `~/Documents/writer-deck`, `~/.config/writer-deck`) lives outside the release tree and is never touched — the `--exclude` list in both scripts must stay intact.

## Key Constraints

- Display is always 800×480, always 1-bit (black/white) — there is no grayscale rendering path.
- The Waveshare 7.5" V2 stock Python driver's `display_Partial` sets CDI register `0xA9`, which inverts pixel polarity vs full/fast modes. The slice passed to it must be pre-inverted (`b ^ 0xFF`).
- `waveshare_epd` is not a pip package; it lives in `lib/waveshare_epd/` (vendored — `setup.sh` copies it from the Waveshare GitHub repo). `mypy` and coverage are configured to ignore this path.
- Tests run on desktop without any Pi hardware; hardware-dependent code must be guarded by `is_pi` checks or caught exceptions.
