# Writer Deck — Improvements

---

## Display Refresh Overhaul — DONE

All 5 refresh improvements have been implemented and tested on Pi Zero 2 W hardware.

### 1. True Bounding-Box Partial Refresh — DONE

**What:** Per-keystroke updates now refresh only the changed rows on the display instead of doing a full-panel refresh.

**How it works:** `EPaperDriver.display_partial()` diffs the new buffer against `_last_buf` row-by-row. It finds the bounding box (`y_start`..`y_end`) of changed rows, extracts that slice, and calls `display_Partial(slice, 0, y_start, 800, y_end)`. The slice is pre-inverted (`b ^ 0xFF`) to compensate for the CDI polarity flip in the `display_Partial` waveform.

**Result:** ~0.3s keystroke latency vs ~1s previously. Only the changed region blinks.

### 2. Wake Without Clear — DONE

**What:** When the display wakes from sleep, it no longer flashes white before restoring the screen.

**How it works:** Added `EPaperDriver.wake()` which calls `epd.init()` without `epd.Clear()`. E-ink panels retain their image without power, so `_last_buf` stays valid and bounding-box partials resume immediately after wake.

### 3. Diff-Based Refresh Mode Selection — DONE

**What:** Large changes (paste, scroll, mode switch) automatically escalate from partial to fast-full.

**How it works:** `display_partial()` counts changed rows during the diff pass. If `changed_rows / HEIGHT > 0.3`, it escalates to `init_fast + display()` instead of bounding-box partial. This threshold avoids partial refreshes that would look worse or take longer than a clean fast-full.

### 4. 4-Gray Grayscale Rendering — DONE

**What:** Anti-aliased text using 4-gray (2-bit) e-ink mode. Text edges look smooth instead of jagged.

**How it works:** When `use_4gray: true`, full refreshes call `display_full_4gray()` with a PIL `"L"` mode image. The renderer produces `"L"` mode when called with `grayscale=True`. After a 4-gray refresh, `_last_buf` is cleared (`None`) so the next partial falls back to fast-full to reload 1-bit controller RAM before bounding-box partials resume.

**Enable:** Add `use_4gray: true` to `config.yaml`. Recommended for displays purchased after Oct 2023.

### 5. GC16 Deep Clean Moved to Idle — DONE

**What:** The slow GC16 full-clean waveform (~3-4s, 8 blink cycles) no longer runs during active typing. Regular full refreshes use `init_fast` (~1s, 2-3 blinks) instead.

**How it works:** `display_clean()` uses `init()` (GC16) for thorough ghost-clearing, but `App._render_and_refresh()` only calls it after `idle_deep_clean_seconds` of inactivity (default 300s). Regular full refreshes use `display_full()` which uses `init_fast`. The result is dramatically less blinking during a writing session.

**Config:** `idle_deep_clean_seconds: 300` in `config.yaml`. Set to `0` to disable.

---

## Developer Tooling — DONE

All 5 developer tooling improvements have been implemented.

---

## 1. Pygame Desktop Emulator — DONE

**What:** Live 800x480 window that emulates the e-ink display with interactive keyboard input.

**Files created:**
- `writerdeck/display/pygame_driver.py` — `PygameDriver` implementing `DisplayDriver` protocol
- `writerdeck/input/pygame_reader.py` — `PygameKeyboardReader` with `poll()` method and pygame-to-evdev keycode mapping

**Files modified:**
- `writerdeck/core/app.py` — pygame branch in `__init__`, `poll()` call in main loop, `close()` in shutdown
- `config_default.yaml` — documents `pygame` as a `keyboard_input` option

**Design:** Reuses `KeyMapper` entirely (pygame keycodes -> evdev scancodes). `poll()` runs on main thread (macOS compatible). Optional dependency — guarded import.

**Activate:** `keyboard_input: pygame` in config.yaml

---

## 2. pytest-cov — DONE

**What:** Coverage reporting for the 200+ existing tests.

**Configuration:** `pyproject.toml` — `[tool.pytest.ini_options]`, `[tool.coverage.*]` sections

**Usage:** Just run `pytest` — coverage runs automatically. Terminal shows missing lines, `htmlcov/index.html` has a browsable report.

---

## 3. mypy Static Type Checking — DONE

**What:** Catch type errors across the codebase. Leverages existing `from __future__ import annotations` and type hints.

**Configuration:** `pyproject.toml` — `[tool.mypy]` section. Ignores missing imports for hardware deps (evdev, spidev, pisugar, waveshare, pygame). Excludes `lib/`, `venv/`, `tests/`.

**Usage:** `mypy writerdeck/`

---

## 4. ruff Linter + Formatter — DONE

**What:** Fast linter and formatter. Replaces flake8, isort, black in a single tool.

**Configuration:** `pyproject.toml` — `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.format]` sections. Rules: E, F, W, I (isort), UP (pyupgrade), B (bugbear), SIM (simplify). Line length 99, Python 3.12.

**Usage:**
- `ruff check writerdeck/ tests/` — lint
- `ruff check --fix writerdeck/ tests/` — auto-fix
- `ruff format writerdeck/ tests/` — format

---

## 5. rsync Deploy Script — DONE

**What:** One-command deployment to the Raspberry Pi over SSH.

**File created:** `deploy.sh` — rsync + service restart + log tail

**Usage:**
- `./deploy.sh` — defaults to `pi@writerdeck.local`
- `./deploy.sh 192.168.1.50` — custom host
- `./deploy.sh 192.168.1.50 myuser` — custom host and user

---

## Dev Dependencies

All tools are in `requirements-dev.txt`:
```
-r requirements.txt
pygame>=2.5.0
pytest>=7.0.0
pytest-cov>=4.0.0
mypy>=1.8.0
ruff>=0.3.0
```

Install with: `pip install -r requirements-dev.txt`
