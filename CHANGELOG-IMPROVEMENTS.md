# Writer Deck — Improvements Changelog & Execution Trace

> **Provenance note (added during 2026-07-10 merge into `qa/bugfixes`):** this document is imported unmodified from the `writer-deck-master/` clone where this work was done. It describes that clone's environment (macOS, its own venv) and includes the 4-gray/PERF-5 work, which was **excluded** when merging into this repo (4-gray had already been deliberately removed here as a bugfix). See `IMPROVEMENTS.md`'s "2026-07-10 merge" section for what actually landed here and what was adapted.

> **What this is.** A complete, exportable record of the improvements implemented against
> `IMPROVEMENTS-PLAN.md`, executed on **2026-07-10** by a team of subagent developers with a
> dedicated Principal-level code reviewer gating every phase. Every phase passed adversarial review
> before the next began. This document is the audit trail: what changed, why, where, how it was
> verified, and what still needs hardware verification.

---

## 1. Executive summary

- **27 tasks implemented**, 1 intentionally skipped (LONG-4 — no cheap temperature source).
- **5 phases**, each gated by a Principal-engineer review that verified correctness, test quality,
  and preservation of the plan's "Do NOT touch (by-design)" hardware invariants.
- **Tests:** 548 → **661 passing** (+113 new), stable across randomized orderings.
- **Lint/type:** `ruff` held at its **77** pre-existing-error baseline, `mypy` at **23** — no new
  errors introduced by any change.
- **No "Do NOT touch" invariant was violated** in any phase (verified at every gate + final sign-off).
- **Final verdict:** APPROVED — project ready. Four tasks carry a *hardware-verify-pending* flag
  (require the physical Pi/panel): FAULT-2, FAULT-4, OPS-1, OPS-2.

---

## 2. Environment setup (prerequisite work)

The repo had no working test environment on this macOS machine. Established a green baseline before
any task work:

1. Created `venv` and installed `requirements-dev.txt` (Pillow, pytest, pytest-cov, mypy, ruff,
   pygame) from the internal Apple pip mirror (`pypi.apple.com`) using the `apple_certifi` CA bundle.
2. **Font baseline:** tests render with the **Hack** font; on Linux `setup-dev.sh` installs it via
   `fonts-hack-ttf`, but macOS had neither Hack nor the `DejaVuSansMono.ttf` fallback, and there was
   no bundled `assets/fonts/`. This caused all 45 renderer/wrapper tests to fail with
   `OSError: cannot open resource`. Fixed by bundling the official **Hack v3.003** TTFs (Regular,
   Bold, Italic, BoldItalic) into `assets/fonts/` — the directory `fonts.py` already searches by
   design. Sourced from `raw.githubusercontent.com/source-foundry/Hack` (OFL/MIT licensed).
3. Confirmed baseline: **548 passed**, ruff 80, mypy 23.

**New files from setup:** `assets/fonts/Hack-{Regular,Bold,Italic,BoldItalic}.ttf`.

> Note: ruff baseline improved 80 → 77 during the work as touched test files were tidied; it never
> regressed above 80.

---

## 3. Phase-by-phase trace

Legend: 🔴 high · 🟠 medium · ⚪ low severity. **VERIFIED** = covered by desktop tests;
**HW-PENDING** = implemented + syntax/parse-checked, needs the physical Pi to fully verify.

### Phase 0 — Panel-safety quick wins  ·  Reviewer: APPROVED (no blocking findings)

| ID | Sev | What changed | Files | Status |
|----|-----|--------------|-------|--------|
| **LONG-1** | 🔴 | Deep-sleep the panel after `display_idle_sleep_seconds` (default **20s**) of no keystroke, wake on next key; sleep/wake stay strictly on the main thread (key thread only sets flags). Bounds the powered-idle window from ~5 min to ~20s. | `config_default.yaml`, `core/config.py`, `core/app.py` | VERIFIED |
| **LONG-2** | 🔴 | `partial_refresh_max_streak` 20 → **5** (vendor ghost-hygiene). Added `full_refresh_max_seconds` (default **300**) wall-clock backstop in `RefreshManager` — forces a full refresh at least every 5 min even during unbroken typing. | `config_default.yaml`, `core/config.py`, `display/refresh_manager.py`, `core/app.py` | VERIFIED |
| **FAULT-2** | 🔴 | New `tools/epd_sleep.py` standalone deep-sleep script (fully try/except-guarded, exits 0 on desktop). systemd unit gains `KillSignal=SIGTERM`, `TimeoutStopSec=15`, `ExecStopPost=…/epd_sleep.py` — runs even on crash/kill to guarantee the panel sleeps. | `tools/epd_sleep.py` (new), `writer-deck.service`, `setup.sh` | HW-PENDING |
| **FAULT-3** | 🟠 | `atexit.register(app._driver.close)` belt-and-suspenders; made `EPaperDriver.sleep()`/`close()` **idempotent** (`_slept` flag, guarded on `_epd is not None`) so signal-handler + atexit double-invocation is safe and `close()` never double-`Clear()`s. | `main.py`, `display/driver.py`, `display/pygame_driver.py` | VERIFIED |

### Phase 1 — Correctness bugs  ·  Reviewer: APPROVED (no blocking findings)

| ID | Sev | What changed | Files | Status |
|----|-----|--------------|-------|--------|
| **BUG-1** | 🔴 | Find & Replace now locates the match via `find_next` before replacing (was a silent no-op unless the cursor already sat on a match). `replace_at` returns bool and only pushes undo / sets dirty on a real edit — no more inert undo entries. | `core/app.py`, `core/document.py` | VERIFIED |
| **BUG-2** | 🟠 | Selection highlight maps document coords → wrapped-row coords through `row_map` and subtracts `_scroll_offset`, via a shared `base_mode` helper used by all three modes (stub removed). Fixes wrong highlight on wrapped/scrolled text. | `modes/base_mode.py`, `distraction_free.py`, `dashboard.py`, `typewriter.py` | VERIFIED |
| **BUG-3** | 🟠 | PAGE_DOWN `_scroll_offset` is now clamped to `max(0, len(wrapped)-1)` — can no longer scroll into a permanently blank screen. | `modes/base_mode.py` | VERIFIED |
| **BUG-4** | 🟠 | Daily word count uses a down-ratcheting baseline so words re-typed after deleting below the session baseline are counted (was clamped to `max(0, …)` and lost). | `core/session.py` | VERIFIED |
| **BUG-5** | 🟠 | Session totals key on a captured `_baseline_date`, not `date.today()` at call time — words are attributed to the day they were written; `goal_progress` no longer double-mixes days across midnight. | `core/session.py` | VERIFIED |
| **BUG-6** | 🟠 | USB export uses `rglob` + preserves relative subpath (`export_dir / src.relative_to(docs_dir)`) — no longer silently skips subfolders or collides on same-named files. | `utils/usb_export.py` | VERIFIED |
| **BUG-7** | 🟠 | Critical-battery shutdown now requires **3 consecutive** sub-threshold samples (debounce); any healthy/charging reading resets the counter. A single glitchy PiSugar sample no longer triggers poweroff. | `utils/power.py` | VERIFIED |
| **BUG-8** | 🟠 | `find_usb_mount` guards `iterdir()` with `try/except (PermissionError, OSError): continue` — an unreadable mount dir (e.g. `0700 /media/root`) is skipped, not crashed on. | `utils/usb_export.py` | VERIFIED |
| **BUG-9** | ⚪ | `Power._query` uses `with socket.socket(...)` so the socket is closed on the error path too. | `utils/power.py` | VERIFIED |
| **BUG-10** | ⚪ | Font change calls `on_exit()` on the outgoing mode, preserves the mode index, and restores scroll offset (was silently dropping in-mode state). | `core/app.py` | VERIFIED |
| **BUG-11** | 🟠 | Stuck-modifier fixes: added `KeyMapper.reset()`; called on evdev reconnect and on pygame focus loss (`WINDOWFOCUSLOST`/`ACTIVEEVENT`); stdin unrecognized-escape byte is re-emitted as CHAR instead of dropped. | `input/keymapper.py`, `keyboard.py`, `pygame_reader.py`, `stdin_reader.py` | VERIFIED |

### Phase 2 — Rendering performance  ·  Reviewer: APPROVED (hard invariants provably intact)

| ID | Sev | What changed | Files | Status |
|----|-----|--------------|-------|--------|
| **PERF-1** | 🔴 | `display_partial` now emits **multiple disjoint dirty row-bands** (pure `compute_dirty_bands`, merge gap ≤32 rows) instead of one giant merged bounding box; stats footer/timer decoupled from the keystroke path (frozen to a snapshot on partials, live only on full refreshes) so volatile stats no longer drag a full-height refresh. This is the single biggest typing-latency lever. | `display/driver.py`, `display/renderer.py`, `core/app.py` | VERIFIED |
| **PERF-2** | 🟠 | Partials are windowed in **X** as well as Y (pure `compute_x_window`, byte/8-px snapped) — a glyph change clocks ~a glyph over SPI, not a full 800px row. CDI `0xA9` pre-inversion still applied to the windowed slice. | `display/driver.py` | VERIFIED |
| **PERF-3** | 🟠 | `_last_buf` kept as a `bytearray` with in-place row splicing — no full 48KB re-allocation per keystroke. | `display/driver.py` | VERIFIED |
| **PERF-4** | 🟠 | The idle-full-refresh timer measures against the last **keypress**, not the last refresh — a brief pause-then-type no longer triggers a surprise full-refresh blink. Long-idle GC16 deep clean unchanged. | `display/refresh_manager.py`, `core/app.py` | VERIFIED |
| **PERF-5** | 🟠 | 4-gray (`display_4Gray`, 48000 single-byte SPI writes) is gated off the input-driven path via an `input_driven` flag — keystroke frames always use `display_full`/`display_partial`. 4-gray is idle/preview only. | `core/app.py` | VERIFIED |

### Phase 3 — Fault tolerance & panel longevity  ·  Reviewer: APPROVED (+ 1 recommended fix applied)

| ID | Sev | What changed | Files | Status |
|----|-----|--------------|-------|--------|
| **FAULT-4** | 🟠 | `setup.sh` enables the bcm2835 hardware watchdog: `dtparam=watchdog=on` in boot config + `RuntimeWatchdogSec=14` in `/etc/systemd/system.conf` (idempotent). A kernel hang forces a reboot → boot-time `init()+Clear()` restores the panel. | `setup.sh`, `README.md` | HW-PENDING |
| **FAULT-5** | 🟠 | On critical battery the emergency callback (`emergency_save` → `driver.sleep()`) completes **synchronously before** `poweroff`. Hardened so a raising callback can't skip poweroff (battery protection is the priority). Composes with the BUG-7 debounce. | `utils/power.py` | VERIFIED |
| **FAULT-6** | 🟠 | Every display op wrapped in bounded retry (`DISPLAY_OP_ATTEMPTS=3`, re-inits the current waveform between tries); busy-timeout is treated as a failure (no longer silently ignored); persistent failure raises `DisplayError` instead of crashing. | `display/driver.py` | VERIFIED |
| **FAULT-7** | 🟠 | On persistent `DisplayError` the app switches to a **headless degraded mode**: keeps draining input, autosaving, and persisting the session; retries the panel every 30s; a successful retry forces a full refresh. Losing the display never loses the user's text. | `core/app.py` | VERIFIED |
| **LONG-3** | 🟠 | Before long-idle deep sleep the panel blanks to a mostly-white "paused" frame (`splash.render_paused()`) — retention mitigation so a static high-contrast page doesn't sit for hours. New `display_screensaver_seconds` (default 1800, clamped to the sleep trigger; 0 disables). | `core/app.py`, `display/splash.py`, `config_default.yaml`, `core/config.py` | VERIFIED |
| **LONG-4** | ⚪ | **SKIPPED** — temperature gating needs a temperature source; out of scope per plan for indoor use. | — | SKIPPED |

### Phase 4 — Ops / deploy  ·  Reviewer: APPROVED (safe by construction) + final sign-off

| ID | Sev | What changed | Files | Status |
|----|-----|--------------|-------|--------|
| **OPS-1** | 🟠 | `deploy.sh` rewritten to an **atomic, revertible** model: rsync into a fresh `releases/<ts>/` (no `--delete`, old `current` stays live on failure), atomic `current` symlink swap (`ln -sfn` + `mv -T`), restart, conservative prune to newest 5 (only ever removes old dirs *under* `releases/`, never data dirs, never `rm -rf`). Adds `--rollback`, `--list`, `--help`. | `deploy.sh`, `README.md` | HW-PENDING |
| **OPS-2** | ⚪ | `writer-deck.service` is now the **single canonical template** (`__USER__`/`__WORKDIR__`/`__VENV__` placeholders); `setup.sh` renders + installs it via `sed` (here-doc duplicate removed). All prior directives (ExecStopPost, TimeoutStopSec, WatchdogSec, …) live in one place. | `writer-deck.service`, `setup.sh`, `CLAUDE.md` | HW-PENDING |

---

## 4. Reviewer-driven fixes (applied on top of worker output)

Quality items surfaced by the gating reviews and fixed directly:

- **Phase 2:** added escalation-boundary tests (144 rows → partial, 145 → escalate) to lock the
  `>30%` fast-full escalation semantics against regression. (`tests/test_driver.py`)
- **Phase 3:** hardened the FAULT-5 emergency path — wrapped the shutdown callback in `try/except`
  so a failure to sleep the panel can't prevent `poweroff`, and rewrote the mislabeled test to
  actually raise from the callback and assert poweroff still fires. (`utils/power.py`,
  `tests/test_power.py`)

---

## 5. New config keys (all in `config_default.yaml`, with typed accessors in `core/config.py`)

| Key | Default | Purpose |
|-----|---------|---------|
| `display_idle_sleep_seconds` | `20` | LONG-1: deep-sleep the panel after this idle time |
| `full_refresh_max_seconds` | `300` | LONG-2: wall-clock full-refresh backstop |
| `display_screensaver_seconds` | `1800` | LONG-3: blank-to-white before long-idle sleep (0 = off) |
| `partial_refresh_max_streak` | `5` (was `20`) | LONG-2: vendor ghost-hygiene cadence |

---

## 6. Complete file manifest

**New files:** `tools/epd_sleep.py`, `assets/fonts/Hack-{Regular,Bold,Italic,BoldItalic}.ttf`,
`tests/test_main.py`, `tests/test_mode_scroll_selection.py`, `tests/test_keyboard_reader.py`,
`tests/test_pygame_reader.py`.

**Modified source:** `main.py`, `config_default.yaml`, `writer-deck.service`, `setup.sh`,
`deploy.sh`, `writerdeck/core/{app,config,document,session}.py`,
`writerdeck/display/{driver,refresh_manager,splash,pygame_driver}.py`,
`writerdeck/input/{keymapper,keyboard,pygame_reader,stdin_reader}.py`,
`writerdeck/modes/{base_mode,distraction_free,dashboard,typewriter}.py`,
`writerdeck/utils/{power,usb_export}.py`.

**Modified tests:** `test_app.py`, `test_config.py`, `test_document.py`, `test_driver.py`,
`test_keymapper.py`, `test_power.py`, `test_refresh_manager.py`, `test_session.py`,
`test_splash.py`, `test_stdin_reader.py`, `test_usb_export.py`.

**Modified docs:** `README.md`, `CLAUDE.md`, `IMPROVEMENTS-PLAN.md` (status boxes → `[x]`/`[~]`).

---

## 7. "Do NOT touch (by-design)" invariants — preserved throughout

Verified intact at every phase gate and at final sign-off:

- CDI `0xA9` pre-inversion (`b ^ 0xFF`) applied to every windowed partial slice (incl. PERF-2 X-window).
- `wake()` = `init()` **without** `Clear()`; first post-wake frame forced full.
- `_last_buf` preserved through `sleep()`; correctly nulled only after 4-gray.
- `_mode` waveform-state caching (skips redundant re-inits).
- Long-idle GC16 deep clean (`idle_deep_clean_seconds`) retained.
- No custom LUT/waveform upload attempted (panel is OTP-locked).

---

## 8. Verification status

**Automated (desktop, green):**
- `pytest -q` → **661 passed**, stable across randomized orderings.
- `ruff check .` → 77 (pre-existing baseline, no new).
- `mypy writerdeck/` → 23 (pre-existing baseline, no new).
- Smoke test: `python main.py` starts on NullDriver + StdinReader, writes PNG frames to
  `/tmp/writer-deck/`, and shuts down cleanly (exit 0; double-sleep log confirms FAULT-3 idempotency).

**Hardware-verify-pending checklist (requires the physical Pi + Waveshare panel):**
- **FAULT-2:** `systemctl stop writer-deck` → panel deep-sleeps; journal shows `ExecStopPost` ran (incl. on crash/kill).
- **FAULT-4:** after `setup.sh` + reboot, `wdctl` shows the BCM2835 watchdog active (~14s); kernel hang → auto-reboot → panel restored.
- **OPS-1:** deploy creates `releases/<ts>/`, swaps `current` atomically, restarts; `--rollback` repoints to prior release and runs; 6+ deploys keep only newest 5; data dirs untouched.
- **OPS-2:** rendered unit installs with real paths and all directives; `setup.sh` idempotent.

---

## 9. How to reproduce / re-verify

```bash
cd /Users/qa_desk_09/projects/writer-deck-master
source venv/bin/activate
pytest -q                 # 661 passed
ruff check .              # 77 (baseline)
mypy writerdeck/          # 23 (baseline)
python main.py            # desktop: NullDriver, frames → /tmp/writer-deck/
```

Task-level detail, anchors, and per-task Verify steps live in `IMPROVEMENTS-PLAN.md` (all boxes now
`[x]`, LONG-4 `[~]`). Architecture/design notes for the changes are in `CLAUDE.md`; user-facing
deploy/rollback and watchdog docs are in `README.md`.
