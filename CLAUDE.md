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

## Architecture

### Configuration

`config_default.yaml` in the project root is the base config. Users can create `config.yaml` alongside it; it is deep-merged on top. `writerdeck/core/config.py` loads both into a singleton `Config` with typed property accessors. The `keyboard_input` key (`auto | stdin | evdev | pygame`) controls which input backend is selected at startup.

### Display pipeline

`DisplayDriver` is a structural `Protocol` (`writerdeck/display/driver.py`). Three implementations:
- `EPaperDriver` — real Waveshare hardware (Pi only, requires `waveshare_epd` in `lib/`)
- `NullDriver` — saves PNG frames to `/tmp/writer-deck/` (dev/desktop)
- `PygameDriver` — renders to a pygame window (set `keyboard_input: pygame`)

See `writerdeck/display/CLAUDE.md` for the glyph cache, display waveform methods, bounding-box partial refresh, and deep-clean gotchas.

### Input pipeline

`KeyMapper` (`writerdeck/input/keymapper.py`) converts raw evdev scancodes + modifier state into `KeyAction` enum values.

### Modes and overlays

Three writing modes: `DistractionFreeMode`, `DashboardMode` (sidebar stats), `TypewriterMode` (centered scroll). Mode cycling: Ctrl+Tab / Ctrl+Shift+Tab.

Overlays (`FilePickerOverlay`, `FontPickerOverlay`, `FindOverlay`) intercept all input while active, returning a result dict when dismissed. `App._handle_overlay_result()` acts on the result.

See `writerdeck/utils/CLAUDE.md` for text wrapping, perf instrumentation, and platform/power gotchas.

### Deploy & the systemd unit (OPS-1 / OPS-2)

**Single source of truth for the unit.** `writer-deck.service` is a **template**, not a valid unit as checked in — it carries `__USER__` / `__WORKDIR__` / `__VENV__` placeholders. `setup.sh` `sed`-substitutes them and installs the result to `/etc/systemd/system/writer-deck.service`. Do NOT re-introduce a second copy of the unit (e.g. a here-doc in `setup.sh`); add or change directives **only in the template**. All prior directives live here (`KillSignal`, `TimeoutStopSec`, `ExecStopPost` from FAULT-2; `WatchdogSec` from FAULT-4; `Restart`, `OOMScoreAdjust`, etc.).

**Atomic, revertible deploy.** `deploy.sh` never mutates the live tree. Remote layout under `~/writer-deck/`: `releases/<ts>/` (each deploy), a shared `venv/` (created by `setup.sh`, symlinked into each release, survives rollbacks), and a `current -> releases/<ts>` symlink. The unit's `WorkingDirectory`/`ExecStart`/`ExecStopPost`/`PYTHONPATH` all resolve through `current`, so a deploy is: rsync into a fresh `releases/<ts>/` (no `--delete`), atomically swap `current` (`ln -sfn … .tmp && mv -Tf .tmp current`), restart the service, then prune to the newest 5 releases. `deploy.sh --rollback` repoints `current` at the previous release and restarts; `deploy.sh --list` shows releases + current. Pruning only ever removes dirs directly under `releases/`, never the active release, never data dirs; `rm -rf` is not used. Data (`config.yaml`, `~/Documents/writer-deck`, `~/.config/writer-deck`) lives outside the release tree and is never touched — the `--exclude` list in both scripts must stay intact. `config.yaml` is additionally symlinked into each new release (`setup.sh` and `deploy.sh` both do this, mirroring the `venv` symlink) because `config.py` resolves `config.yaml` relative to its own file inside the release — without the symlink a release can never see the persistent config.

## Key Constraints

- Display is always 800×480, always 1-bit (black/white) — there is no grayscale rendering path.
- The Waveshare 7.5" V2 stock Python driver's `display_Partial` sets CDI register `0xA9`, which inverts pixel polarity vs full/fast modes. The slice passed to it must be pre-inverted (`b ^ 0xFF`).
- `waveshare_epd` is not a pip package; it lives in `lib/waveshare_epd/` (vendored — `setup.sh` copies it from the Waveshare GitHub repo). `mypy` and coverage are configured to ignore this path.
- Tests run on desktop without any Pi hardware; hardware-dependent code must be guarded by `is_pi` checks or caught exceptions.
