# Writer Deck — Improvements

> **2026-07-10 improvements round (27 tasks across 5 phases), merged from a parallel
> `writer-deck-master/` clone: see [`CHANGELOG-IMPROVEMENTS.md`](CHANGELOG-IMPROVEMENTS.md)** for
> that clone's full execution trace, [`IMPROVEMENTS-PLAN.md`](IMPROVEMENTS-PLAN.md) for per-task
> detail (all boxes now `[x]`, LONG-4 `[~]` skipped), and the **"2026-07-10 merge" section at the
> bottom of this file** for what changed, what was adapted for conflicts with this repo's own
> independent fixes, and what remains hardware-verify-pending. The sections below document the
> earlier display-refresh overhaul and dev tooling.

> **2026-07-13 hardening round (6 bug fixes + 6 tech-debt items): see
> [`FIXES-2026-07-13.md`](FIXES-2026-07-13.md).** Fixes a `.md` data-loss bug, a `deploy.sh` prune
> bug, rename/`.last_open`, font-cache invalidation, a `get_font` crash path, two dead config knobs,
> plus tech debt (markdown lone-`*`, mode-input dedup, `stdin` keys, `subprocess` migration, etc.).
> Items whose tests need a real venv (Pillow/PyYAML) are flagged **`ENV-PENDING`** there and must be
> run before that work is considered closed.

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

**Hardware-verify-pending at merge time, since resolved** — carried over from the imported round's
own "hardware-verify-pending" list (see CHANGELOG-IMPROVEMENTS.md §8). All since confirmed on real
hardware; see the "2026-07-11" and "2026-07-12" sections below for how:
- **FAULT-2** — confirmed (2026-07-11 real deploy; re-verified via SIGKILL crash simulation
  2026-07-12): `ExecStopPost` deep-sleeps the panel even on crash/kill.
- **FAULT-4** — confirmed 2026-07-11: rebooted the Pi mid-session, hardware watchdog/service came
  back up cleanly.
- **OPS-1** — confirmed 2026-07-11 (first real deploy) and 2026-07-12 (rollback/list exercised
  live, which found and fixed a real release-selection bug — see below).
- **OPS-2** — confirmed 2026-07-11: templated systemd unit installed and running as `pi`.
- **LONG-4** — intentionally skipped in the original round (no cheap temperature source); still
  skipped, not a hardware-verify gap.

Additionally, **not otherwise re-verified on hardware** by this merge: the interaction between this
repo's `init_fast()` boot/wake behavior and the imported FAULT-6 retry/re-init logic
(`_reinit_current_waveform()` re-inits whatever `_mode` currently is, including `"fast"` on
first-time init) has only been checked with mocked `_epd` in tests, not on a real panel.

## 2026-07-11: perf/fixes merge + first real-hardware verification pass

A second branch, `perf/fixes` (per-line wrap caching, dirty-band diffing groundwork, `PerfMetrics`
instrumentation, word-count/stats caching, `Document.replace_at` undo/dirty-flag fix), was merged
into `qa/bugfixes` via the same real-3-way-merge method as the 2026-07-10 round (shared ancestor
`71eacd2`). Notable merge-time fix: `Document.replace_at`'s BUG-1 fix (only push undo/set dirty on
an actual match) was combined with perf/fixes' `_invalidate_word_count()` call, keeping the latter
inside the "did it actually match" guard. `enable_perf_metrics` was in `config_default.yaml` but
missing from `config.py`'s `_SCHEMA` (pre-existing gap in perf/fixes itself, not introduced by the
merge) — added.

The result was then deployed to a real Raspberry Pi Zero 2W (`pi@192.168.1.101`) for the **first
time this repo's OPS-1/OPS-2 machinery has run on real hardware** — this closes out the "hardware
verify-pending" list from the 2026-07-10 section above:
- **OPS-1** confirmed working: atomic release/rollback deploy via `deploy.sh`, `current` symlink
  swap, release pruning. User data (`~/Documents/writer-deck`, `~/.config/writer-deck`) migrated
  from a prior root-owned ad hoc install to the new `pi`-owned release layout under `~/writer-deck/`.
- **OPS-2** confirmed working: templated systemd unit installed and running as `pi`.
- **FAULT-4** confirmed: rebooted the Pi mid-session to clear suspected stale GPIO/watchdog state;
  service came back up cleanly under the hardware watchdog.
- Found and fixed live: `config.yaml` wasn't visible to the app under the new release layout, because
  `config.py` resolves it relative to its own file inside `releases/<ts>/`, and nothing symlinked the
  persistent `config.yaml` into each new release the way `venv` already was. Fixed by adding the same
  symlink pattern to both `setup.sh` and `deploy.sh`.

### The real bug: catastrophic per-keystroke latency (75s+), found and fixed in four layers

Manual typing on the device immediately exposed something the entire 2026-07-10 merge and its test
suite had never caught: every keystroke was taking tens of seconds to render. Desktop tests never
catch this because `NullDriver`/`PygameDriver` skip all the real hardware/font-rendering cost paths.
Root-caused via `dmesg` → `strace` → `py-spy dump` (which pinned the main thread inside
`text_wrapper._break_word`/`font.getbbox`) → direct Python benchmarking on the Pi, after first
ruling out (and confirming ruled-out, not just assumed) a PiSugar I2C fault and stale GPIO state via
a full reboot test. Fixed in four separate rounds as each fix exposed the next bottleneck underneath:

1. **`_break_word` O(n²) character-break loop.** Grew a trial string one character at a time,
   re-measuring the whole growing string from scratch each time. Rewrote as a binary search per
   segment. A pathological 700-char unbroken run: ~41s → a fraction of a second.
2. **`_wrap_single_line` O(n²) word-wrap loop.** Same anti-pattern one level up — re-measured the
   whole growing `current` sub-line via `_text_width(current + " " + word)` on every word. This is
   what a real ~900-1300-char paragraph *line* (not a single unbroken word) actually hits; #1 alone
   didn't fix it because that line has spaces. Fixed by tracking width incrementally instead of
   recomputing the full trial string each word.
3. **`font.getlength()`'s real per-call cost.** Even with both O(n²) patterns gone, a single
   ~1300-char real paragraph line still cost ~3.8s to wrap: `getlength()` itself costs ~2ms fixed
   overhead plus ~0.6-1.2ms/char on this Pi Zero 2W's CPU — genuine FreeType shaping time, not an
   algorithmic bug. Fixed by memoizing per-`(font, character)` width in `_text_width`, turning
   repeated characters/substrings into O(1) dict lookups: the same line dropped to ~27ms cold,
   ~10ms warm.
4. **`draw.text()`'s real per-call cost in the renderer.** With `wrap_lines` fixed, `PerfMetrics`
   (enabled via `enable_perf_metrics: true`) showed `render_image` still costing 2.6-3.5s per frame
   — and, critically, this reproduced on a **fresh, ordinary document**, not just the pathological
   long-line one, proving it wasn't specific to bad content. `ImageDraw.text()`/`font.getbbox()` pay
   real FreeType rasterization cost (~1-2ms/char) on every call; PIL does not cache rasterized glyph
   bitmaps across calls. Added `writerdeck/display/glyph_cache.py`: caches each distinct
   `(font, character)` glyph's rasterized mask + advance width once, then composites via
   `draw.bitmap()` for repeats — measured ~76x faster for a full page once characters are warm
   (2.6s → 0.034s). `renderer.py` now routes every text draw/measurement through
   `draw_text_cached()`/`text_width_cached()` instead of `draw.text()`/`font.getbbox()`.

**Regression introduced and caught by the same live-hardware testing, same session:** the glyph
cache's first version passed all 697 desktop tests but visibly broke real rendering — most glyph ink
was missing on the actual panel. Root cause: `ImageDraw.bitmap()` onto a `"1"`-mode (1-bit) target
applies a much stricter cutoff to an antialiased `"L"`-mode mask than `draw.text()` does internally
— measured directly: a single glyph's black-pixel count went from 25 (`draw.text()` reference) to 2
(raw `L`-mode mask composited via `draw.bitmap()`). This is invisible to desktop tests because they
don't do pixel-level comparison against real hardware output. Fixed by thresholding each glyph's mask
to `"1"` mode at the standard midpoint (128) before caching it — verified to within ~0.1% pixel
difference of `draw.text()`'s own output on a full line of prose, and confirmed visually correct on
the real panel afterward.

**Net result, measured on the real Pi Zero 2W, cold vs. after all four fixes:**

| Stage | Before | After |
|---|---|---|
| `wrap_lines` (real ~1300-char paragraph line) | 8.4s | 4.8-19ms |
| `render_image` (25 lines of ordinary prose) | 2.6-3.5s | 26-42ms |
| `total_frame` (typical keystroke) | 4.8-13s+ | ~0.5-1.7s, now dominated by `driver_display` — the
  physical e-ink panel write itself (~0.3s partial / ~1s full refresh), which is inherent hardware
  latency, not a software cost. |

**Also fixed per explicit request during this session:** the idle screensaver (`render_paused()` in
`splash.py`) previously drew a centered "Paused — press any key" hint before blanking; it now blanks
to pure white with no text at all.

**Not yet tested on hardware at the time this section was written — all since resolved in the
2026-07-12 QA round below:** physical typing-feel confirmation across all three modes (dashboard,
typewriter) beyond distraction_free; `deploy.sh --rollback`/`--list`; FAULT-2/6/7 (panel-sleep
backstop, display-op retry, headless degraded mode) exercised live rather than via mocks;
PiSugar/battery warning/shutdown thresholds against a real battery. The `Zone.Identifier`
glob-exclude cosmetic bug in `deploy.sh`/`setup.sh`'s rsync excludes (`*.Zone.Identifier` doesn't
match `foo.py:Zone.Identifier` — colon, not dot) was also fixed in that round.

## 2026-07-12: QA round on the deployed qa/bugfixes build

Systematic hardware QA of everything landed in the two merges above, working through the
"not yet tested" list.

**Typing-feel in dashboard/typewriter modes** — confirmed clean via `PerfMetrics`: dashboard
`total_frame` p50 ~580-800ms, typewriter p50 ~620-760ms, both matching `distraction_free`'s
already-verified profile. No visual regressions (sidebar, locked-line scroll, forced full-refresh
on newline all correct).

**`deploy.sh --rollback`/`--list` — found and fixed a real bug.** `--list` worked correctly, but
`--rollback` picked the *wrong* release: `ls -1 "$RELEASES" | sort | grep -vxF "$cur" | tail -n1`
lexically sorts release directory names to find "the newest that isn't current". Normal releases
are named `YYYYMMDD-HHMMSS` (sorts fine), but the one-time `setup.sh` release is named
`setup-<ts>` — lexically `s` > `2`, so it sorted *after* every timestamped release and looked
newest even though it's the oldest thing on disk. Reproduced live: a real rollback from
`20260711-234528` repointed `current` at `setup-20260711-115324` instead of the actual previous
release `20260711-233307`. A same-approach fix using directory mtime instead of name was tried and
also rejected — running the app writes `__pycache__` into the release directory, which bumps mtime
on every restart independent of the release's real age, so `setup-*` looked newest again after
being started once. Fixed by sorting on each name's trailing `YYYYMMDD-HHMMSS` timestamp
(`${d: -15}`) instead of the whole name or mtime — verified correct on a second live rollback
(`234528 -> 233307`), confirmed `--list` reflects reality, then rolled forward back to the correct
release. Committed alongside the `Zone.Identifier` exclude fix (`*.Zone.Identifier` →
`*:Zone.Identifier`, real files use a colon not a dot).

**FAULT-2/6/7 — all confirmed working, no bugs found.** Exercised live via a temporary
fault-injection patch applied directly to the *deployed* `driver.py` on the Pi (not committed to
the repo) — a file-backed counter (`/tmp/wd_fault_inject`) that forces `_run_with_retry`'s op to
raise for N remaining attempts, checked and decremented once per attempt, so it could be armed for
a transient fault (small N) or a persistent one (large N) without restarting the process to change
behavior.
- **FAULT-2**: `sudo systemctl kill -s SIGKILL writer-deck` (crash simulation) — `ExecStopPost`
  still ran `epd_sleep.py` and logged "panel deep-sleep OK"; systemd's `Restart=` policy brought
  the service back up cleanly afterward.
- **FAULT-6**: armed 2 forced failures (< `DISPLAY_OP_ATTEMPTS=3`) — journal showed
  `Display op 'display_full' failed (attempt 1/3)` / `(attempt 2/3)` then a silent recovery on
  attempt 3, transparent to the user at the keyboard.
- **FAULT-7**: armed 100 forced failures — app logged `Display failed repeatedly — entering
  headless mode`, screen froze (showing whatever was last painted, not corrupted — no update ever
  landed), input kept being accepted, `Headless: retrying display panel` fired every 30s (each
  retry itself burning 3 attempts and failing while the fault was armed), autosave file timestamp
  confirmed writes continued through the whole headless window. Cleared the fault
  (`echo 0 > /tmp/wd_fault_inject`); the very next 30s retry logged "Panel recovered — resuming
  rendering with a full refresh" and the screen came back.
- Patch fully reverted by redeploying clean code (`./deploy.sh`) — confirmed zero trace of the
  injection helper in the redeployed `driver.py`.

**PiSugar/battery thresholds — root cause found and fixed: a wiring documentation bug, not a
software bug.** `Power.available` requires a successful `get battery` response from
`pisugar-server`'s Unix socket; it was returning `"battery: I2C not connected"`, which
`Power._update()` can't parse, so `available` stayed `False` and the entire warning/shutdown/UI
path silently no-op'd regardless of configured thresholds. Traced to the I2C bus itself:
`i2cdetect -y 1`/`-y 2` came back completely empty on both buses, and `pisugar-server`'s journal
showed constant `Remote I/O error` / `Operation timed out` trying to reach `addr=87` (0x57) — a
wiring fault, not a software misconfiguration (the address itself was already correct). The
project's wiring reference (recovered from the user and first committed to `USER_GUIDE.md` this
session) had the PiSugar 3 pads backwards: it wired **MDAT/MSCL** to the Pi's I2C pins and left
**SDAT/SSCL** disconnected. Per PiSugar's own docs, MDAT/MSCL is the "I2C main (master) interface,
no function at this time" — SDAT/SSCL is the "I2C slave interface, connected to Pi's I2C interface"
i.e. the pair that actually needs to reach the Pi. (An intermediate attempt wired *both* pairs to
the same two Pi pins, which also left the bus silent — tying MDAT+SDAT together externally through
the Pi apparently conflicts with something on the PiSugar board itself.) Rewiring to
SDAT→Pin3(SDA)/SSCL→Pin5(SCL) only (MDAT/MSCL left floating) immediately brought up both `0x57` and
`0x68` on the bus and real battery data (88%, not charging) through `pisugar-server`. `USER_GUIDE.md`
corrected to match. With real battery data flowing, both thresholds were then verified live: set
`battery_warning_percent: 90` (above the real 88%) → `Battery: [****-] 88%` correctly appeared in
the footer stats; set `battery_shutdown_percent: 90` → after 3 consecutive critical samples (60s
apart, `SHUTDOWN_DEBOUNCE_SAMPLES`), the app logged `Battery critically low (86%) ... initiating
shutdown`, autosaved, slept the panel, then issued a real `systemctl poweroff` — the device
physically powered off and was manually powered back on to confirm clean recovery. Config restored
to real defaults (15%/3%) afterward.

**Bonus bug found during this test, unrelated to battery:** `keyboard_input: auto` resolves the
keyboard device once at process startup by scanning `/dev/input/by-id`; if the physical USB
keyboard is unplugged/replugged (as happened here mid-wiring-work) and hasn't finished
re-enumerating by the time the app starts, `by-id` has no keyboard entries yet and the resolver
silently falls back to the first `/dev/input/event*` device — observed picking `vc4-hdmi` (an HDMI
virtual input) instead, leaving the app completely unresponsive to real keystrokes with no error
logged. A subsequent restart (once USB had settled) picked the correct device. Not fixed this
session — tracked as a follow-up to add a retry/re-resolve window (or at least a loud warning) so a
slow USB re-enumeration doesn't silently strand the device.
