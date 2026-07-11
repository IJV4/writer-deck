# Writer Deck — Improvements

> **2026-07-10 improvements round (27 tasks across 5 phases), merged from a parallel
> `writer-deck-master/` clone: see [`CHANGELOG-IMPROVEMENTS.md`](CHANGELOG-IMPROVEMENTS.md)** for
> that clone's full execution trace, [`IMPROVEMENTS-PLAN.md`](IMPROVEMENTS-PLAN.md) for per-task
> detail (all boxes now `[x]`, LONG-4 `[~]` skipped), and the **"2026-07-10 merge" section at the
> bottom of this file** for what changed, what was adapted for conflicts with this repo's own
> independent fixes, and what remains hardware-verify-pending. The sections below document the
> earlier display-refresh overhaul and dev tooling.

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

### 4. 4-Gray Grayscale Rendering — REVERTED (2026-04-20)

**What:** Anti-aliased text using 4-gray (2-bit) e-ink mode. Text edges look smooth instead of jagged.

**How it worked:** When `use_4gray: true`, full refreshes called `display_full_4gray()` with a PIL `"L"` mode image. The renderer produced `"L"` mode when called with `grayscale=True`. After a 4-gray refresh, `_last_buf` was cleared (`None`) so the next partial fell back to fast-full to reload 1-bit controller RAM before bounding-box partials resumed.

**Why it was removed:** dead code on this device and a source of stray grey pixels on the display — see commit `fix: remove 4-gray/grayscale rendering capability`. `use_4gray`, `display_full_4gray()`, and the `grayscale=True` renderer path no longer exist anywhere in the codebase. The 2026-07-10 improvement round (below) independently re-hardened this same feature (PERF-5) without knowledge of the removal; that part of the merge was dropped to honor this decision — see the "2026-07-10 merge" section below.

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

## 5. rsync Deploy Script — DONE (superseded by OPS-1, see below)

**What:** One-command deployment to the Raspberry Pi over SSH. Originally a simple `rsync --delete`
+ restart; the 2026-07-10 merge (OPS-1, below) replaced this with an atomic, revertible
release/rollback model. This section is kept for history; see OPS-1 for current behavior.

**Usage (current):**
- `./deploy.sh` — defaults to `pi@writer-deck.local`
- `./deploy.sh 192.168.1.50` — custom host
- `./deploy.sh 192.168.1.50 myuser` — custom host and user
- `./deploy.sh --rollback` — revert to the previous release
- `./deploy.sh --list` — list releases and the active one

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

---

## 2026-07-10 merge: writer-deck-master improvement round

A parallel clone (`writer-deck-master/`) independently ran a 27-task improvement round against
this same codebase (see [`CHANGELOG-IMPROVEMENTS.md`](CHANGELOG-IMPROVEMENTS.md) and
[`IMPROVEMENTS-PLAN.md`](IMPROVEMENTS-PLAN.md), both imported unmodified from that clone as the
historical record of that work). This section documents how that work was merged into this repo's
`qa/bugfixes` line, since the two trees had diverged (this repo had gone on to add notebook
pagination, remove 4-gray, switch boot/wake to `init_fast`, and other independent fixes).

**Method:** a real 3-way git merge from the shared ancestor commit (`71eacd2`), not a manual file
copy — git auto-resolved everything neither side touched, and the ~11 true conflicts were resolved
by hand, file by file.

**Merged in as-is:** LONG-1 (panel deep-sleep after idle), LONG-2 (`partial_refresh_max_streak`
20→5 + wall-clock full-refresh backstop), LONG-3 (screensaver blank before long idle sleep),
FAULT-3 (idempotent `sleep()`/`close()` + atexit), FAULT-5/6/7 (display-op bounded retry,
`DisplayError`, headless degraded mode), FAULT-2 (`tools/epd_sleep.py` + `ExecStopPost`), PERF-1/2/3
(multi-band dirty-region diffing + X-window + in-place bytearray splicing), PERF-4 (idle-full timer
measured from last keypress), BUG-1/4/5/6/7/8/9/10/11, OPS-1 (atomic release/rollback deploy),
OPS-2 (single-template systemd unit). New test files (`test_keyboard_reader.py`, `test_main.py`,
`test_pygame_reader.py`, `test_mode_scroll_selection.py`) and bundled `assets/fonts/Hack-*.ttf`
(font-rendering portability) came in too.

**Adapted, not merged as-is — real conflicts with this repo's own independent fixes:**
- **4-gray (PERF-5): dropped entirely.** This repo had already deliberately deleted 4-gray as a
  bugfix (stray grey pixels on this hardware — see item 4 above). The 2026-07-10 round re-hardened
  the same feature without knowing about that decision. Per user decision during the merge, the
  removal was honored; PERF-5 and all `use_4gray`/`display_full_4gray`/`grayscale=` code and tests
  were excluded.
- **BUG-2 (selection highlight on wrapped lines): kept this repo's own fix, dropped the duplicate.**
  This repo had already fixed the identical bug independently (`map_selection()` in
  `utils/text_wrapper.py`, used by all three modes) before this merge. The imported round added a
  second, differently-shaped fix for the same bug (`BaseMode._doc_to_visual`/`_map_selection`). Kept
  the original; the duplicate helpers were not added.
- **Boot/wake waveform (driver.py `init()`/`wake()`): kept this repo's `init_fast` fix.** This repo
  separately reduced startup/wake flash by switching from GC16 `init()`+`Clear()` to `init_fast()`
  (no `Clear()`). The imported round's driver rewrite (FAULT-6 retry, PERF-1/2/3 dirty bands) was
  layered on top of this repo's `init_fast()` behavior rather than reverting to GC16 boot.
- **DTM1/`prev_image` delta: stayed removed.** This repo tried, then explicitly reverted, passing
  `_last_buf` as `prev_image` to `epd.display()` (ghost-prevention — see `writerdeck.core.app.py`
  history). The imported driver rewrite never had this parameter, so no reconciliation was needed;
  `display()` is still always called with a single positional arg.
- **`deploy.sh`/`setup.sh` hostname: kept this repo's `writer-deck.local`.** The imported OPS-1
  rewrite defaulted to `writerdeck.local`; this repo's own `fix(deploy): correct default hostname`
  had already established `writer-deck.local` (matching the Avahi hostname `setup.sh` configures) as
  correct. The OPS-1 atomic-deploy/rollback machinery was kept; only the hostname default follows
  this repo.
- **`test_mode_scroll_selection.py`: three tests fixed post-merge.** The imported test file hardcoded
  wrap-point offsets (95/190/285 chars) and used the pre-pagination `_scroll_offset` field directly.
  Neither holds in this repo: actual Hack-font wrap points measured 90/180/270 here (font-rendering
  is environment-dependent), and `DistractionFreeMode`/`DashboardMode` scroll via page-based
  `_paginate()` now, not `_scroll_offset` (superseded by the notebook-pagination feature). Rewrote
  the three affected tests to derive wrap offsets from `wrap_lines()` directly and to drive scrolling
  through `PAGE_NEXT`, preserving the original tests' intent.

**Verification after merge:** `pytest -q` → 675 passed (was 672 immediately post-merge before the
three test fixes above). `ruff check .` → 80 errors (pre-merge baseline on this branch was 83 — no
new errors, net improvement). `mypy writerdeck/` → 23 errors (same as pre-merge baseline, no
change). Desktop smoke test (`python main.py`) starts and shuts down cleanly.

**Still hardware-verify-pending — not verified on this repo's actual Pi/panel, carried over from the
imported round's own "hardware-verify-pending" list (see CHANGELOG-IMPROVEMENTS.md §8):**
- **FAULT-2** — `systemctl stop writer-deck` should deep-sleep the panel via `ExecStopPost` even on
  crash/kill (`tools/epd_sleep.py`). Only syntax/import-checked on desktop.
- **FAULT-4** — `setup.sh`'s bcm2835 hardware watchdog (`dtparam=watchdog=on` +
  `RuntimeWatchdogSec=14`) should force a reboot on a kernel hang. Cannot be exercised off-Pi.
- **OPS-1** — the atomic release/rollback deploy (`releases/<ts>/`, `current` symlink swap, prune to
  5, `--rollback`/`--list`) has not been run against a real Pi over SSH.
- **OPS-2** — the templated systemd unit (`__USER__`/`__WORKDIR__`/`__VENV__` substitution via
  `setup.sh`) has not been installed and started on real hardware.
- **LONG-4** — intentionally skipped in the original round (no cheap temperature source); still
  skipped here.

Additionally, **not otherwise re-verified on hardware** by this merge: the interaction between this
repo's `init_fast()` boot/wake behavior and the imported FAULT-6 retry/re-init logic
(`_reinit_current_waveform()` re-inits whatever `_mode` currently is, including `"fast"` on
first-time init) has only been checked with mocked `_epd` in tests, not on a real panel.
