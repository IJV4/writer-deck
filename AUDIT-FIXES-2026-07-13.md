# Audit Fixes — 2026-07-13

Fixes applied following a whole-codebase audit. Every finding below was independently
confirmed before fixing, and the fixes were applied by file-disjoint agents (one owner per
file) so changes don't overlap. This document records **what changed and why**, and — most
importantly — **how to finish verifying it once the environment has the runtime deps and real
hardware** (see [Testing notes](#testing-notes-for-the-environment)).

> Separate from the earlier `FIXES-2026-07-13.md` (unrelated prior work). This file covers only
> the audit-driven fixes.

> **2026-07-13 (later) — closed out in a real venv.** Merged into `writer-deck`'s git history on
> the `import/audit-fixes-2026-07-13` branch (base `88ccc2d`, the same commit `feature/reading-mode`
> branched from — the two are reconciled by an ordinary merge, not a rebase). With `Pillow`/`PyYAML`/
> `pygame`/`ruff`/`mypy` actually installed, the full suite ran: **798 passed** (up from the
> PIL-free 438) after fixing 2 real bugs the sandboxed run couldn't see and 2 bugs in the new
> regression tests themselves:
> - **Startup render was unguarded.** `App.run()`'s one-time initial `_render_and_refresh(force_full=True)`
>   (before the main loop starts) lacked the `try/except Exception` DEFENSE-IN-DEPTH guard that H2/H3
>   added to the *in-loop* render call — so a fault surfacing from the very first render (e.g. a mode
>   reading corrupt on-disk state during `on_enter`) still crashed startup. Fixed in `app.py::run()`.
> - **`get_font`'s final fallback could still raise.** `ImageFont.load_default(size)` calls
>   `truetype()` internally on this Pillow version (it bundles a TTF), so it re-raises `OSError` when
>   every TrueType path is genuinely unavailable — the `except TypeError` guard (Pillow < 10) didn't
>   catch it. Now falls back to `ImageFont.load_default_imagefont()`, which never touches `truetype()`.
> - **Test bug:** `TestDeepCleanOnWake`'s two tests used `ticks=1`, but the `_run_loop` harness's
>   `on_tick` callback fires *after* that tick's queue-drain — so the queued key, and the deep-clean
>   code path it should trigger, was never processed. Both were vacuous (one failed once actually run,
>   its sibling passed only because nothing executed). Fixed by using `ticks=2`, matching the pattern
>   already used correctly elsewhere in the same file.
> - **Test bug:** `test_recovery_render_skips_loop_render` asserted `display_full.call_count == 1`,
>   but `run()` unconditionally calls `display_full` twice before the loop's headless-retry logic ever
>   runs (the splash screen, then the mandatory initial full render) — regardless of the `_headless`
>   flag the test pre-sets. Corrected the expected count to `3` (2 startup + 1 recovery), with the
>   real regression case (loop double-rendering) still caught as `4`.
>
> `ruff check .` also ran for real: 14 new style findings (import ordering, `try/except/pass` →
> `contextlib.suppress`, one unused import, nested-if/with), all in the same categories the codebase
> already carries ~24 pre-existing unfixed instances of. Auto-fixed what `ruff --fix` could; the
> remainder is left matching existing repo convention rather than a scope-creeping style pass.
> `mypy writerdeck/` found the same 23 errors as the pre-fix baseline — **zero new type errors**.
>
> Still genuinely unverified — needs real Pi hardware, not just a venv (see §5.3 below): M2 SPI-lock
> race, M10/M11 busy-pin/recovery, M12 boot-headless, H5 keyboard hot-replug, L1 GC16 deep-clean
> timing, L2 screensaver timing, M7 low-battery-while-idle, M8 Tier-3 suspend re-arm, L3 cursor/indent
> rendering, FIX-2/FIX-4/FIX-5 hardware checklist items in the sibling doc, and `shellcheck` (not
> installed in this environment either).

---

## 1. Verification status (read this first)

PyPI is firewalled on this machine, so `PIL`, `PyYAML`, `pygame`, `pytest-cov`, `ruff`, and
`mypy` are not installable here. Verification is therefore **partial** — see the split below.

| Gate | Result |
|------|--------|
| `python -m py_compile` on every changed `.py` | ✅ pass (all files) |
| `bash -n deploy.sh` | ✅ pass |
| Runnable pytest subset (PIL/yaml-free modules) | ✅ **438 passed, 0 real failures** |
| Full pytest (`app`, `driver`, `config`, `text_wrapper`, modes, overlays) | ⏳ **pending deps** — tests written, not yet run |
| `ruff check .` / `mypy writerdeck/` | ⏳ **pending deps** — not run |

**What "438 passed" covers:** the high-severity fixes all live in PIL-free modules and are
verified now — `document.py`, `session.py`, `power.py`, `keyboard.py`, `stdin_reader.py`,
`keymapper.py`, `file_manager.py`, `refresh_manager.py`, plus `markdown/platform/perf/usb_export/
epdconfig`. New regression tests for each of these fixes pass.

**What's staged (syntax-verified + tests written, not executed):** `app.py`, `main.py`,
`driver.py`, `config.py`, `text_wrapper.py`, `base_mode.py`/`distraction_free.py`/`dashboard.py`,
`find_overlay.py`. These import `PIL`/`yaml`/`pygame` transitively, so their test files can't be
collected until deps exist. Nothing here has been run beyond `py_compile`.

The only red in the current test run is `ModuleNotFoundError: No module named 'PIL'|'yaml'|
'pygame'` (13 collection errors + 2 `test_main` failures) — all environment, none caused by the
edits.

---

## 2. Fixes by severity

Fixes are cited by **symbol name** (stable across edits), not line number. "Verified" = covered
by a passing test now; "Staged" = test written but needs deps to run; "HW" = additionally needs
real hardware to fully confirm (see §5.3).

### 🔴 High severity

| # | Area / file | Fix | Status |
|---|-------------|-----|--------|
| H1 | `core/document.py::Document._push_undo` | Redo-stack data loss | ✅ Verified |
| H2 | `core/app.py::App.run` (autosave) | Autosave crash on disk-full | ⏳ Staged |
| H3 | `core/app.py::App._handle_action` (SAVE) + save_as path | Explicit-save crash | ⏳ Staged |
| H4 | `core/session.py::Session._load_ledger` | Corrupt `daily.json` crash | ✅ Verified |
| H5 | `input/keyboard.py::KeyboardReader._reconnect` | evdev replug → dead input | ✅ Verified |

**H1 — Redo stack not cleared on a coalesced post-undo edit.**
`_push_undo` returned early on the 1s coalesce path *before* `self._redo_stack.clear()`, so
`type → undo → keep typing within 1s` left a stale redo entry; a later redo silently discarded the
just-typed text. **Fix:** `_redo_stack.clear()` moved to the *start* of `_push_undo` — every edit
now invalidates redo, including the coalesce path.
*Tests:* `tests/test_document.py::test_edit_after_undo_invalidates_redo` (new); rewrote
`test_redo_stack_bounded` (previously vacuous — coalescing meant it never exercised the 100-entry
cap; now sets `_last_undo_time=0` per insert so the `deque(maxlen=100)` cap is real).

**H2 — Unguarded autosave in the main loop.**
`maybe_autosave` was outside every `try` in the loop; only `DisplayError` was caught. A disk-full /
read-only `OSError` propagated out of `run()` and killed the process — the exact failure the "words
are never lost" design promises to survive. **Fix:** wrapped in `try/except OSError` → logs, shows
`"Autosave failed — retrying"`, loop continues.

**H3 — Unguarded explicit save.**
`KeyAction.SAVE` (`save` + `session.persist`) and the `save_as` overlay path could raise `OSError`
out of `run()`. **Fix:** both wrapped → `"Save failed"` status + log, app stays alive. `doc.name`
still updates on save_as.

**H4 — Corrupt `daily.json` crashes Dashboard render.**
`_load_ledger` did `json.load` with no guard, reached every dashboard frame via
`goal_bar → _today_total`. A truncated ledger (plausible after unclean power-loss) crashed the app
on every render. **Fix:** wrapped in `try/except (JSONDecodeError, OSError, UnicodeDecodeError,
ValueError)` → logs a warning, returns `{}`. 30s cache behavior unchanged.
*Test:* `tests/test_session.py` corrupt-ledger case.

**H5 — evdev reconnect reused a stale device node.**
`_reconnect` reopened the once-resolved `/dev/input/eventN`; after a USB replug onto a different
node, input was dead until service restart. **Fix:** `_reconnect` now re-runs device resolution
(`_resolve_device_retrying`), retries the by-id resolve up to `_AUTO_RESOLVE_ATTEMPTS` (5) × 0.5s
before the fallback guess, and logs a **loud warning** naming the guessed device on fallback.
Latched-modifier reset (`_mapper.reset()`) preserved.
*Tests:* `tests/test_keyboard_reader.py` reconnect/re-resolve, failure path, loud fallback.

### 🟠 Medium severity

| # | Area / file | Fix | Status |
|---|-------------|-----|--------|
| M1 | `utils/power.py::Power._update` | Stale battery data → spurious poweroff | ✅ Verified |
| M2 | `display/driver.py::EPaperDriver` | Emergency SPI race (cross-thread) | ⏳ Staged / HW |
| M3 | `core/document.py` + `utils/file_manager.py` | `.md`→`.txt` silent wrong-file save | ✅ Verified |
| M4 | `utils/file_manager.py::FileManager._sanitize_name` | Path traversal via doc names | ✅ Verified |
| M5 | `utils/file_manager.py` + `core/app.py` | Dead `default_format` knob wired up | ✅ Verified |
| M6 | `core/config.py::load_config` | Malformed `config.yaml` fatal at startup | ⏳ Staged |
| M7 | `core/app.py` (battery) | Low-battery warning absent while idle | ⏳ Staged / HW |
| M8 | `core/app.py::App._enter_system_suspend` | Tier-3 suspend fails to re-arm | ⏳ Staged / HW |
| M9 | `main.py` | Cleanup skipped when `run()` raises (tty not restored) | ⏳ Staged |
| M10 | `display/driver.py::EPaperDriver._check_busy` | Reads BUSY pin without `0x71` | ⏳ Staged / HW |
| M11 | `display/driver.py::EPaperDriver.init` | Recovery re-init leaks failed controller | ⏳ Staged / HW |
| M12 | `display/driver.py::create_driver` | Silent boot-headless fallback | ⏳ Staged |

**M1 — Dead PiSugar socket let stale critical data trigger poweroff.**
`_available` was only ever set `True`; a failed `_query()` kept the last (possibly critical,
not-charging) reading, which could satisfy the `SHUTDOWN_DEBOUNCE_SAMPLES` streak from frozen data.
**Fix:** `_update` sets `_available` from whether *this* cycle got a fresh reading; a failed query
clears it, so stale cycles can't count toward shutdown (the critical check gates on `_available`).
A recovered socket restores availability. `stop()` now `join`s the monitor thread (2s timeout).
*Test:* `tests/test_power.py` stale-socket-no-shutdown (22 pass).

**M2 — Emergency shutdown touched non-thread-safe SPI from the Power thread.**
`emergency_save() → driver.sleep()` runs on the Power monitor thread while the main loop may be
mid-`display_partial`. **Fix:** added a reentrant `threading.RLock` to `EPaperDriver`, acquired
around `_run_with_retry` (covers all `display_*`), `init`, `wake`, `sleep`, `close`. This
serializes cross-thread SPI access and protects `_last_buf`/`_mode`/`_slept`. `RLock` (not `Lock`)
because public ops call `_run_with_retry`/`_reinit` while holding it. *(This is why `app.py`'s
`emergency_save` needed no change.)*

**M3 — Doc loaded from `name.md` saved back to `name.txt`.**
`_doc_path` unconditionally preferred `.txt` and `Document` never remembered its loaded suffix.
**Fix:** `Document.loaded_suffix` (default `.txt`), set by `FileManager.load` from the resolved
path; new `_doc_save_path` honors it so a `.md` doc saves back to `.md` even with a `.txt` sibling.
*Tests:* `tests/test_file_manager.py::TestFileManagerLoadedSuffix`.

**M4 — No path-traversal defense on document names.**
Typed `/` or `../` in a name escaped `~/Documents/writer-deck` for save/autosave/recovery.
**Fix:** `_sanitize_name` validates the resolved path stays within the docs root (subfolders still
allowed), raising `ValueError` on absolute/`..` paths; used by `_doc_path`, `_doc_save_path`,
`_autosave_path`.
*Tests:* `tests/test_file_manager.py::TestFileManagerPathTraversal`.
*Caveat:* `load_last_open` reads a name from the `.last_open` sidecar and now raises if that file
were hand-corrupted with a traversal path (app-controlled data, so left strict — see §5.6).

**M5 — `default_format` was documented + accessor-backed but never read.**
**Fix:** `FileManager.__init__(documents_dir, autosave_interval=90, default_format="txt")`
(extension without a dot); brand-new documents use it. `app.py` passes
`default_format=self._config.default_format`. Old callers keep working via the default.
*Tests:* `tests/test_file_manager.py::TestFileManagerDefaultFormat`.

**M6 — Malformed `config.yaml` crashed startup.**
**Fix:** `load_config` wraps both YAML loads in `try/except (yaml.YAMLError, OSError)`; a broken
*user* `config.yaml` logs a loud warning and falls back to defaults instead of a raw traceback. If
`config_default.yaml` itself fails, logs an error and falls back to `{}` (property-level defaults
take over). *(main.py no longer needs its own guard for this case.)*

**M7 — Low-battery warning effectively absent while idle.**
`is_low` was only surfaced inside the change-gated render path, so an idle user crossing the
threshold saw nothing before the panel slept. **Fix:** the main loop now detects the low-battery
transition (`_low_batt_warned`, reset when no longer low), shows a StatusBar warning, wakes the
panel if sleeping, and forces one render.

**M8 — Tier-3 suspend could fail to re-arm.**
`systemctl suspend` blocks until resume; if resume wasn't an evdev key event, `_tier3_active`
stayed True and the device never re-suspended. **Fix:** `_enter_system_suspend` resets
`_last_keypress` and clears `_tier3_active`/`_tier2_active` in a `finally` so the ladder re-arms
after resume regardless.

**M9 — Cleanup skipped when `run()` raises.**
`main()` caught to `emergency_save` but never ran `_do_shutdown`, leaving `StdinReader` raw-tty
mode unrestored. **Fix:** exception/KeyboardInterrupt paths call a guarded `_best_effort_cleanup`
(`app._do_shutdown()`, falling back to `keyboard.stop()`), after `emergency_save`.

**M10 — `_check_busy` sampled the BUSY pin without `0x71`.**
The panel latches busy state only in response to the `0x71` get-status command (its own `ReadBusy`
always sends it first). **Fix:** `_check_busy` best-effort sends `0x71` (guarded by
`getattr`/`callable`, swallowing errors) before reading the pin; no-op on mocks/desktop.

**M11 — Recovery re-init leaked the failed controller.**
`init()` constructed a fresh `EPD()` without releasing the old one. **Fix:** `init()` best-effort
tears down any existing controller (`sleep()` + `epdconfig.module_exit()`, each guarded) before
constructing a new one.

**M12 — Silent boot-headless fallback.**
`create_driver` fell back EPaper→Null on any init error with only a WARNING, so a Pi with a dead
panel ran "blind" looking healthy. **Fix:** logs at **ERROR** with `exc_info` and an explicit
"hardware init FAILED, running headless-from-boot, frames → /tmp" message.

### 🟡 Low severity

| # | Area / file | Fix | Status |
|---|-------------|-----|--------|
| L1 | `core/app.py` (deep-clean) | GC16 deep-clean unreachable under defaults | ⏳ Staged / HW |
| L2 | `core/app.py` (screensaver) | `display_screensaver_seconds` clamped ineffective | ⏳ Staged / HW |
| L3 | `utils/text_wrapper.py::_wrap_single_line` | Leading-whitespace wrap → negative cursor_col | ⏳ Staged |
| L4 | `input/stdin_reader.py::_read_escape_sequence` | Unknown ANSI escapes injected as text | ✅ Verified |
| L5 | `modes/base_mode.py` + paged modes | PageUp/PageDown dead in DistractionFree/Dashboard | ⏳ Staged |
| L6 | `modes/find_overlay.py` + `input/keymapper.py` | Find `Tab` switch broken on evdev/pygame | ✅ Verified (keymap) |
| L7 | `core/app.py::App.__init__` | EPaperDriver leaked when `keyboard_input: pygame` on Pi | ⏳ Staged |
| L8 | `core/app.py::App._maybe_retry_panel` | Panel-recovery double full-refresh | ⏳ Staged |
| L9 | `deploy.sh` | `--help` prints code; `--rollback` aborts silently | ✅ Verified (`bash -n` + live) |
| L10 | docs | Grayscale/waveform/hostname/naming drift | ✅ Verified (manual) |

- **L1 — GC16 deep-clean:** was unreachable because the panel sleeps at 20s and any wake resets
  `idle_secs`. **Fix:** track `_sleep_started_at` at Tier-1 sleep; on wake, if the *sleep duration*
  ≥ `idle_deep_clean_seconds`, force the next full refresh to `display_clean` (GC16). One-shot
  `_force_deep_clean` flag consumed by `_render_and_refresh`.
- **L2 — Screensaver:** `min(screensaver_secs, display_off_secs)` clamped any larger configured
  value down to the sleep trigger. **Fix:** fires at its configured time (when
  `screensaver_secs < effective display-off` and panel awake); if `≥` the sleep trigger it logs a
  one-time warning that it's disabled by the earlier sleep.
- **L3 — Leading-whitespace wrap:** `line.split(" ")` dropped leading spaces, giving a nonzero
  sub-line offset → `cursor_col - start` went negative → renderer drew the cursor at the wrong x.
  **Fix:** split off leading whitespace, wrap the remainder, re-attach the indent to sub-line 0 so
  its offset is 0 and the indent renders; plus a `max(0, cursor_col - start)` clamp in `wrap_lines`.
  *Caveat:* sub-line 0 can be slightly wider than `max_width_px` by the indent width (renderer
  clips, as with other overflow) — see §5.6.
- **L4 — ANSI escapes:** unmapped CSI (`ESC [`) / SS3 (`ESC O`) sequences leaked their payload
  (e.g. Insert → `[2~`) into the document. **Fix:** unmapped control sequences are consumed and
  dropped; `Alt+<letter>` and all mapped sequences unchanged. *Test:* `tests/test_stdin_reader.py`.
- **L5 — PageUp/PageDown:** mutated `_scroll_offset` (only Typewriter reads it) and always returned
  True → dead key + wasted refresh. **Fix:** in paged modes `PAGE_UP`/`PAGE_DOWN` alias to
  page-prev/page-next, clamped via a new `_last_page()`; return True only when the page actually
  changed. Typewriter's continuous scroll untouched.
- **L6 — Find `Tab`:** only worked on stdin. **Fix:** new `KeyAction.TAB`, emitted for plain
  (unmodified) Tab in `keymapper.py`; `FindOverlay` switches fields on `TAB` (and existing
  Ctrl+Tab). Modes ignore `TAB` (no tab inserted); Ctrl+Tab cycling unchanged. *Test:*
  `tests/test_keymapper.py` (verified); overlay side staged.
- **L7 — pygame driver leak:** `__init__` created+init'd an EPaper/Null driver, then overwrote it
  with `PygameDriver`. **Fix:** decide `keyboard_input` first, construct the driver once.
- **L8 — Recovery double render:** `_maybe_retry_panel` rendered on success and the loop rendered
  again. **Fix:** it returns whether it recovered-and-rendered; the loop sets `changed=False` to
  skip the redundant refresh that tick.
- **L9 — deploy.sh:** `--help` range fixed to `2,21p` (was leaking code from `2,30p`); `--rollback`
  with only one release now prints its intended "no previous release" message and exits 1 cleanly
  (`|| true` on the inner pipeline so `pipefail`/`errexit` don't abort before the guard).
- **L10 — docs:** removed the false "4-gray grayscale" claim (`NEXT-STEPS.md`), corrected waveform
  count "four"→"three" and deploy host `writerdeck.local`→`writer-deck.local` (`README.md`),
  replaced obsolete `untitled-N.txt` naming with the timestamp scheme, and clarified
  `default_format` now takes effect (`USER_GUIDE.md`).

---

## 3. Behavioral changes to be aware of

1. **Plain `Tab`** now emits `KeyAction.TAB` (was `UNKNOWN`). Modes ignore it (no tab char
   inserted); only Find-overlay consumes it. Ctrl+Tab mode-cycling unchanged.
2. **`PAGE_PREV`/`PAGE_NEXT` (Ctrl+Up/Down)** now return the real "changed" flag (False at
   first/last page) instead of always True — intentional, to avoid wasted e-ink refreshes.
3. **Indented wrapped lines** now render their leading indent; sub-line 0 may slightly exceed
   max width by the indent (clipped by renderer).
4. **New documents** now honor `default_format` (`txt`/`md`); existing docs keep their loaded
   extension.
5. **Auto keyboard fallback** now logs a loud warning; on a *persistent* disconnect it may re-emit
   every ~2s reconnect cycle (diagnostic, not an error).

---

## Testing notes for the environment

Everything below is what still needs running once the sandbox/network or a real Pi is available.

### 5.1 Environment setup

```bash
cd /Users/qa_desk_09/projects/writer-deck-master
source venv/bin/activate
pip install -r requirements-dev.txt   # needs PyPI reachable (pypi.org + files.pythonhosted.org)
```

If PyPI stays firewalled, ask to allowlist `pypi.org` and `files.pythonhosted.org` in
`~/.claude/apple/dangerous_allowed_domains.csv`, or install from a local wheelhouse.

### 5.2 Automated gate (run all three; must be clean)

```bash
pytest                 # full suite; coverage addopts require pytest-cov
ruff check .
mypy writerdeck/
```

Then re-run the **currently-staged** test files specifically — these could not execute here and are
the real proof for the staged fixes:

| Test file | Validates fixes |
|-----------|-----------------|
| `tests/test_app.py` | H2, H3, M7, M8, M9, L1, L2, L7, L8 |
| `tests/test_driver.py`, `tests/test_epd_driver.py` | M2, M10, M11, M12 |
| `tests/test_config.py` | M6 |
| `tests/test_text_wrapper.py` | L3 |
| `tests/test_pagination.py`, `tests/test_mode_scroll_selection.py` | L5 |
| `tests/test_overlays.py` | L6 (overlay side) |

Already verified here (re-run to confirm no drift after deps): `tests/test_document.py`,
`tests/test_file_manager.py`, `tests/test_session.py`, `tests/test_power.py`,
`tests/test_keyboard_reader.py`, `tests/test_stdin_reader.py`, `tests/test_keymapper.py`.

**Reproduce the current PIL-free run** (no deps needed, useful as a smoke test):

```bash
pytest -o addopts="" -p no:cacheprovider -q \
  tests/test_document.py tests/test_file_manager.py tests/test_session.py \
  tests/test_power.py tests/test_keyboard_reader.py tests/test_stdin_reader.py \
  tests/test_keymapper.py tests/test_markdown.py tests/test_platform.py \
  tests/test_perf.py tests/test_usb_export.py tests/test_refresh_manager.py \
  tests/test_epdconfig.py
# expect: 405 passed (438 across the full continue-on-error run)
```

### 5.3 Hardware-in-the-loop tests (real Pi Zero 2 W + Waveshare 7.5" panel + PiSugar + USB kbd)

These cannot be unit-tested even with deps — validate on the device:

- **M2 SPI lock (safety-critical):** while actively typing, trigger the critical-battery path (or
  simulate the shutdown callback) and confirm the panel enters deep sleep cleanly with **no
  corrupted/half-updated frame**, and the in-flight refresh doesn't error.
- **M10 `_check_busy` / M11 recovery:** exercise many partial refreshes and a forced fault; confirm
  no half-updated frames and that panel recovery re-inits without leaking SPI/GPIO (`lsof`/`gpio`
  sanity, no "device busy" on restart).
- **M12 boot-headless:** boot with the panel unplugged; confirm a loud **ERROR** log and frames
  landing in `/tmp/writer-deck/` (app stays up).
- **H5 keyboard replug:** unplug the USB keyboard mid-session and replug (ideally so it lands on a
  different `/dev/input/eventN`); confirm input **recovers automatically** and the fallback warning
  appears only if the real device isn't found.
- **L1 GC16 deep-clean:** leave idle past `idle_deep_clean_seconds` (default 300s) so the panel
  sleeps, then wake with a key; confirm the wake refresh is a **GC16 clean (~3-4s, many blinks)**
  that clears ghosting — not a plain fast full.
- **L2 screensaver:** set `display_screensaver_seconds` below `display_idle_sleep_seconds` and
  confirm the white "paused" frame paints at the configured time; set it above and confirm the
  one-time "disabled" warning logs.
- **M7 low-battery:** drain/simulate battery below `battery_warning_percent` **while idle**;
  confirm the warning appears without a keypress (panel wakes to show it).
- **M8 Tier-3 re-arm:** let the device `systemctl suspend`, resume via a non-key event (RTC/USB),
  leave it idle again, and confirm it re-suspends.
- **L3 cursor / indent:** type an indented paragraph long enough to wrap, move the cursor into the
  leading whitespace (Home), and confirm the cursor block sits at the correct x and the indent
  renders.

### 5.4 Data-safety validation (the flagship promise)

Confirm the app **degrades, never crashes**, on persistence faults:

- Fill the documents filesystem (or bind-mount it read-only), keep typing past an autosave
  interval, and press Ctrl+S. Expect: `"Autosave failed — retrying"` / `"Save failed"` status,
  app **still running**, no lost session; free space and confirm the next save succeeds. (H2, H3)
- Truncate/corrupt `~/.config/writer-deck/daily.json`, switch to Dashboard mode. Expect: renders
  fine (empty ledger), warning logged, **no crash**. (H4)
- Put a YAML syntax error in `config.yaml`, start the app. Expect: loud warning, boots on defaults,
  **no traceback**. (M6)
- Type a name containing `../` in the save-name overlay. Expect: rejected/sanitized, nothing
  written outside `~/Documents/writer-deck`. (M4)

### 5.5 Deploy/ops checks

```bash
./deploy.sh --help          # usage block only, no leaked shell code (L9)
./deploy.sh --rollback      # on a Pi with a single release: prints "no previous release…", exit 1
```

### 5.6 Known caveats & suggested follow-ups

- **M4 / `load_last_open`:** now strict — raises `ValueError` if the `.last_open` sidecar were
  hand-corrupted with a traversal path. It's app-controlled data so left strict; if you want
  belt-and-suspenders, wrap `load_last_open` to catch `ValueError` → return `None`.
- **L3 indent width:** sub-line 0 can exceed `max_width_px` by the indent width. If exact fit under
  indentation is ever needed, wrap the remainder against `(max_width_px - indent_width)` for the
  first line only (larger change, not done).
- **M2 concurrency test** is timing-based (real threads + a 50ms sleep); the ordering assertion is
  the load-bearing check — watch for flakiness under CI load.
- **Coverage gating:** `pyproject.toml` still sets `fail_under = 0` and omits `pygame_driver.py`
  from coverage. Left as-is (policy decision); consider a modest floor once the full suite runs
  green with deps.
- **H5 fallback log** may repeat every ~2s during a *persistent* disconnect — intentional and
  diagnosable, but if it's noisy in logs, throttle it.

---

*Provenance: findings from the 2026-07-13 whole-codebase audit (13 parallel readers + adversarial
verification); fixes applied by 13 file-disjoint agents; verified as recorded in §1.*
