# Writer Deck — Improvements Plan

> **Provenance note (added during 2026-07-10 merge into `qa/bugfixes`):** imported unmodified from the `writer-deck-master/` clone as the historical plan document. PERF-5 (4-gray gating) was excluded from the merge — see `IMPROVEMENTS.md`'s "2026-07-10 merge" section.

> Compiled 2026-07-10 from a code review + three e-paper research sweeps (Good Display / Waveshare
> vendor docs and comparable GitHub projects). This document is written to be **executed by a future
> Claude Code instance** working in another environment.

## How to use this document (read first)

- Work **top-to-bottom within each phase**; phases are ordered by dependency and risk.
- Each task has a **stable ID** (`BUG-1`, `PERF-2`, …) and a **status box** (`[ ]` todo → `[~]` in
  progress → `[x]` done). Update the box as you go so progress survives across sessions.
- **Anchors are symbol names + a short code quote**, not just line numbers. This repo is **not under
  git** and you are implementing elsewhere, so line numbers drift — `grep` for the quoted code.
- Do the **Verify** step for every task before marking it `[x]`. Run `pytest` after each task; run
  `ruff check .` and `mypy writerdeck/` before finishing a phase.
- Read **§ Do NOT touch (by-design)** at the bottom before editing display/driver code. Several
  things that look like bugs are deliberate; do not "simplify" them.

**Legend** — Severity: 🔴 high · 🟠 medium · ⚪ low. Effort: `S` (<30 min) · `M` (hours) · `L` (day+).

## Baked-in decisions (from planning)

- **Panel power policy: aggressive idle-sleep.** Deep-sleep the panel after **20 s** of no keystroke
  (new config key `display_idle_sleep_seconds`), wake on the next key. Bounds the "powered-and-idle"
  window to ~20 s instead of 5 min.
- **Wake refresh is always full.** `wake()`/`init()` resets controller RAM, so the first
  post-wake frame must be a full refresh (the code already forces this via `request_full()`).

## Phase order (suggested)

1. **Phase 0 — Panel-safety quick wins** (config + a few lines): `LONG-1`, `FAULT-2`, `FAULT-3`.
   Highest safety-per-effort; do these first even if nothing else gets done.
2. **Phase 1 — Correctness bugs**: all `BUG-*`. Independent, low-risk, well covered by tests.
3. **Phase 2 — Rendering performance**: `PERF-*`. Do `PERF-1` (dirty-region split) before
   `PERF-2` (X-window); they touch the same diff code.
4. **Phase 3 — Fault tolerance + longevity remainder**: `FAULT-*`, `LONG-*` not in Phase 0.
5. **Phase 4 — Ops/deploy**: `OPS-*`.

---

# Group A — Correctness bugs

Independent fixes; each should get/keep a unit test.

## [x] BUG-1 🔴 `S` — Find & Replace never locates the match (replace is broken)

- **Files:** `writerdeck/core/app.py` (`_handle_overlay_result`, the `elif "find" in result:` branch);
  `writerdeck/core/document.py` (`replace_at`).
- **Anchor:** in `app.py`, `self._doc.replace_at(self._doc.cursor_line, self._doc.cursor_col, query, replace)`;
  in `document.py`, `def replace_at(self, line, col, old, new)` with guard `if text[col : col + len(old)] == old:`.
- **Problem:** on Enter in the replace field the app calls `replace_at` at the **current cursor**, but
  nothing has moved the cursor onto an occurrence of `query`. `replace_at` only edits when the text at
  the cursor already equals `old`, so it is a **silent no-op** unless the cursor happens to sit exactly
  on a match — yet it still pushes an undo snapshot and shows `"Replaced"`.
- **Fix:** in the replace branch, first locate the match with `find_next(query, cursor_line, cursor_col)`
  (wrap-around already handled); if found, move the cursor there, then `replace_at`, move the cursor
  past the inserted text, and show `"Replaced"`. If not found, show `"Not found"` and do nothing.
  Make `replace_at` only push undo / set `dirty` when it actually edits (move `_push_undo` inside the
  `if` guard, or return a bool and have the caller decide).
- **Why:** replace is a core feature and is currently non-functional for the normal case; it also
  corrupts the undo stack with inert entries.
- **Verify:** add a test: doc `"the cat sat"`, cursor at (0,0), find `cat` replace `dog` → text becomes
  `"the dog sat"`, one undo entry, `Ctrl+Z` restores. A no-match replace leaves text and undo stack
  unchanged and shows "Not found".

## [x] BUG-2 🟠 `M` — Selection highlight uses document coords as wrapped/scroll coords

- **Files:** `writerdeck/modes/distraction_free.py` (`_map_selection` — a stub),
  `writerdeck/modes/dashboard.py` and `writerdeck/modes/typewriter.py` (`selection = doc.selection.ordered()`),
  consumed in `writerdeck/display/renderer.py` (`_draw_selection_line` / `_draw_selected_text`).
- **Anchor:** `_map_selection` returns `doc.selection.ordered()` with the comment
  `"stub — returns None for now"` / `"A full implementation would map through the wrap mapping"`.
- **Problem:** `RenderFrame.selection` is consumed as **wrapped-row** coordinates (the renderer indexes
  it by the visual row `i`), but the modes pass **document line/col**, and never subtract
  `_scroll_offset` (the cursor is adjusted, selection is not). So any wrapped line or scrolled view
  highlights the wrong rows/columns.
- **Fix:** map selection endpoints through the same `row_map` the modes already compute in
  `wrap_lines(...)` (used for the cursor), and subtract `_scroll_offset`, exactly as the cursor line
  is adjusted. Implement this once (e.g. a shared helper in `base_mode.py`) and call it from all three
  modes; remove the stub.
- **Why:** selection/highlight is visibly wrong whenever text wraps or the user has paged.
- **Verify:** test that a selection on a wrapped long line produces wrapped-space `(sl,sc,el,ec)` that
  the renderer highlights on the correct visual rows; test with `_scroll_offset > 0`.

## [x] BUG-3 🟠 `S` — PAGE_DOWN scrolls into a permanently blank screen

- **Files:** `writerdeck/modes/base_mode.py` (`_apply_common_input`, PAGE_DOWN branch);
  `writerdeck/modes/distraction_free.py` and `dashboard.py` (`render` slicing `wrapped[self._scroll_offset:]`).
- **Anchor:** `elif action == KeyAction.PAGE_DOWN: self._scroll_offset += 20` (no upper bound);
  render does `visible = wrapped[self._scroll_offset:]`.
- **Problem:** `_scroll_offset` is incremented with no clamp; once it exceeds the wrapped-line count
  the slice is empty → blank screen, `show_cursor` false. Recoverable only via PAGE_UP/editing.
  (Typewriter mode clamps correctly — copy that behavior.)
- **Fix:** clamp on PAGE_DOWN, e.g. `self._scroll_offset = min(self._scroll_offset + page, max(0, len(wrapped) - 1))`.
  Since `base_mode` may not know the wrapped length at input time, either store the last wrapped length
  on the mode (set in `render`) and clamp against it, or clamp inside each `render` before slicing.
- **Why:** trivial to trigger; looks like a crash to the user.
- **Verify:** test: 10-line doc, PAGE_DOWN ×5 → view still shows content and cursor is handled; not blank.

## [x] BUG-4 🟠 `S` — Daily word count undercounts after deleting below the session baseline

- **File:** `writerdeck/core/session.py` (`words_written`, `persist`).
- **Anchor:** `return max(0, current_word_count - self._start_word_count)` and, in `persist`,
  `words = self.words_written(...)` / `if words <= 0: return`.
- **Problem:** `words_written` clamps to `max(0, …)` and `persist` early-returns without advancing
  `_start_word_count` when the delta is ≤ 0. Words re-typed after the count dips below the baseline are
  never counted toward the daily ledger.
- **Fix:** track the high-water mark of `current_word_count` since `start()` and count against that, or
  advance `_start_word_count` even when the delta is ≤ 0 (so a dip resets the baseline downward). Pick
  one consistent model and unit-test it.
- **Why:** the daily-goal ledger silently loses words during normal edit-and-retype.
- **Verify:** test: baseline 100 → delete to 50 → type to 130; ledger reflects the words actually
  authored (not just `130-100`).

## [x] BUG-5 🟠 `S` — Session word totals mis-attributed across midnight

- **File:** `writerdeck/core/session.py` (`persist`, `goal_progress`, `_today_total`).
- **Anchor:** `key = str(date.today())` in `persist`; `today_words = self._today_total() + self.words_written(...)`.
- **Problem:** everything keys on `date.today()` at call time while `words_written` is a delta from a
  baseline captured at session start. A session open across midnight attributes pre-midnight words to
  the new day, and `goal_progress` double-mixes days.
- **Fix (low urgency):** capture the session's start date; on persist, if the date rolled over, split
  or attribute deterministically (simplest acceptable behavior: attribute to the day the words were
  written by persisting on rollover). Document the chosen semantics.
- **Why:** minor for a personal device, but the goal bar and ledger can disagree.
- **Verify:** unit test with a mocked date crossing midnight.

## [x] BUG-6 🟠 `S` — USB export skips subfolders and can collide on names

- **File:** `writerdeck/utils/usb_export.py` (`export_documents`).
- **Anchor:** `for pattern in ("*.txt", "*.md"): for src in docs_dir.glob(pattern):` and
  `dst = export_dir / src.name`.
- **Problem:** `FileManager` supports subfolders (it uses `rglob`, `create_folder`, `list_entries(subfolder=…)`),
  but export uses non-recursive `glob`, so documents in subfolders are silently omitted; and
  `dst = export_dir / src.name` flattens paths so same-named files across folders overwrite each other.
- **Fix:** use `docs_dir.rglob(pattern)` and preserve the relative subpath in `dst`
  (`dst = export_dir / src.relative_to(docs_dir)`, creating parent dirs).
- **Why:** silent, incomplete backups on the one action whose whole job is a complete backup.
- **Verify:** test: docs with a subfolder → all files present under matching relative paths on target;
  no collisions.

## [x] BUG-7 🟠 `S` — Critical-battery shutdown fires on a single low reading (no debounce)

- **File:** `writerdeck/utils/power.py` (`_monitor_loop`).
- **Anchor:** `if self._available and self.battery_level <= self._shutdown_pct and not self.is_charging:`
  → `os.system("sudo systemctl poweroff")`.
- **Problem:** one glitchy PiSugar sample at/under threshold triggers an immediate poweroff and loses
  the session. See also `FAULT-5` for the ordering fix (sleep panel before poweroff).
- **Fix:** require N consecutive sub-threshold samples (e.g. 3) before shutting down; reset the counter
  on any healthy/charging reading.
- **Why:** an unnecessary shutdown loses work; battery readings are noisy under load.
- **Verify:** test that a single low reading does not trigger the callback but N consecutive do.

## [x] BUG-8 🟠 `S` — `find_usb_mount` crashes on an unreadable mount dir

- **File:** `writerdeck/utils/usb_export.py` (`find_usb_mount`).
- **Anchor:** `for user_dir in base_path.iterdir():` and the nested `for sub in user_dir.iterdir():`.
- **Problem:** `iterdir()` is unguarded; a `0700` dir like `/media/root` raises `PermissionError` that
  propagates out of the Ctrl+E handler instead of reporting "no USB found".
- **Fix:** wrap both loops in `try/except (PermissionError, OSError): continue`.
- **Verify:** test that a permission error on one entry is skipped, not raised.

## [x] BUG-9 ⚪ `S` — `Power._query` leaks the socket on error

- **File:** `writerdeck/utils/power.py` (`_query`).
- **Anchor:** `sock = socket.socket(...)` … `sock.close()` only on the success path; `except Exception: return None`.
- **Problem:** on any exception the socket is not closed (CPython GC usually reclaims it, so impact is
  low, but it's incorrect).
- **Fix:** use `with socket.socket(...) as sock:` or a `finally`.
- **Verify:** review only; existing power tests should still pass.

## [x] BUG-10 ⚪ `S` — Font change resets the active mode and skips `on_exit`

- **File:** `writerdeck/core/app.py` (`_handle_overlay_result`, `elif "font" in result:`).
- **Anchor:** `self._modes = self._build_modes(); self._mode = self._modes[self._mode_idx % len(self._modes)]; self._mode.on_enter()`.
- **Problem:** modes are rebuilt and the current mode is replaced with a fresh instance without calling
  `on_exit()` on the outgoing one, losing in-mode state (e.g. typewriter scroll).
- **Fix:** call `self._mode.on_exit()` before rebuilding; after rebuild, restore relevant state or at
  least keep the same index and call `on_enter()`.
- **Verify:** manual/behavioral; optionally assert `on_exit` is called on font change.

## [x] BUG-11 🟠 `M` — Input readers leave modifiers "stuck" (evdev disconnect, pygame focus loss, stdin Alt)

Three related, lower-confidence input defects. Fix together.

- **evdev disconnect:** `writerdeck/input/keyboard.py` — on reopen after `OSError`, the `KeyMapper`
  modifier state (`_ctrl_held`/`_shift_held`) is not reset, so a modifier held during unplug stays
  latched. **Fix:** reset the mapper (or call a `mapper.reset()`) on reconnect.
- **pygame focus loss:** `writerdeck/input/pygame_reader.py` (`poll`) handles `KEYDOWN`/`KEYUP`/`QUIT`
  but not focus loss; a modifier held during Alt/Cmd-Tab never gets its `KEYUP`. **Fix:** on
  `pygame.WINDOWFOCUSLOST` (or `ACTIVEEVENT` focus=0) call `self._mapper.reset()`.
- **stdin Alt+key:** `writerdeck/input/stdin_reader.py` — an unrecognized escape sequence consumes the
  following byte and emits a bare `ESCAPE`, dropping e.g. the `f` in Alt+F. **Fix:** re-emit the
  consumed byte as a CHAR, or don't consume it. (Dev-only path; lowest priority of the three.)
- **Verify:** unit tests where a modifier is held then a reset event occurs → modifier cleared.

---

# Group B — Rendering performance

Root cause: the per-keystroke refresh area is far larger than the change, so ordinary typing does
near-full-height partials (or escalates to full). The vendor rates this panel at **0.3 s, flicker-free**
partial refresh for a *small region* — the goal is to actually hit that. Do `PERF-1` before `PERF-2`
(same diff code). See § Do NOT touch before editing `driver.py`.

## [x] PERF-1 🔴 `L` — Decouple volatile stats from the text framebuffer; emit multiple dirty rectangles

- **Files:** `writerdeck/display/driver.py` (`EPaperDriver.display_partial` — the row-diff loop);
  `writerdeck/display/renderer.py` (`_draw_stats` footer at `y = HEIGHT - 18`; sidebar divider
  `draw.line([(x - 8, 0), (x - 8, HEIGHT)])`); modes' `render` (`stats={"Words": ...}` etc.).
- **Anchor:** in `display_partial`, `changed_rows` is the **count** of differing rows (gates the 30%
  escalation) while `y_start … y_end` is the **span** (gates the refreshed region). These diverge.
- **Problem:** the live `Words: N` footer sits at row ~462 and the dashboard timer/sidebar spans full
  height. When the cursor line (row ~100) and the footer/sidebar both change, `changed_rows` stays
  small (no escalation) but the bounding box spans ~100→480, so `display_Partial` refreshes ~79% of the
  panel on every word boundary (distraction-free) or nearly every keystroke (dashboard, because
  `session.elapsed_display` ticks). This is the primary cause of the "slow/glitchy typing".
- **Fix (two parts, either alone helps; do both):**
  1. **Multi-rectangle diff.** Change the diff to return a *list* of disjoint changed row-bands (merge
     bands closer than a small gap; split when the gap is large, e.g. > 32 rows), and issue one small
     windowed `display_Partial` per band instead of one giant merged box. Keep the total-changed-rows
     escalation as-is.
  2. **Decouple stats cadence.** Do not repaint the word count / timer on the per-keystroke path.
     Either update them only on full/streak refreshes, or throttle them to ~1 Hz in their own small
     window. A word counter/timer does not need per-keystroke fidelity.
- **Why:** shrinking the refreshed region is the single biggest lever available on this OTP-locked
  panel (the waveform itself cannot be sped up — see § Do NOT touch). Confirmed by vendor spec
  (Good Display product 396: partial 0.3 s "no flicker") and by a sibling project (etyper) whose
  whole-buffer partial is called out as the missed optimization.
- **Verify:** with the NullDriver you can't see timing, so add a unit test on the diff function: given
  two buffers differing only in a top band and a bottom band, it returns **two** small windows, not one
  full-height window. Behaviorally on hardware: typing a full line no longer sweeps the whole panel.

## [x] PERF-2 🟠 `M` — Window partials in X, not just Y

- **File:** `writerdeck/display/driver.py` (`display_partial` → `self._epd.display_Partial(partial_slice, 0, y_start, WIDTH, y_end)`).
- **Anchor:** the `0, y_start, WIDTH, y_end` args (X is hardcoded to full `WIDTH`).
- **Problem:** even a one-character change repaints the full 800px-wide row. `display_Partial` accepts
  `Xstart/Xend` and clocks only `Width*Height` bytes over SPI, so a horizontal window reduces both
  transfer and the refreshed/ghosted area.
- **Fix:** compute the horizontal changed-column bounding box per band (byte-column min/max over the
  changed rows), snap Xstart/Xend to 8-px boundaries (the driver already floors to bytes), slice the
  buffer per-row for that column range, and pass real `Xstart/Xend`. Note the CDI-`0xA9` pre-inversion
  (`b ^ 0xFF`) still applies to the windowed slice.
- **Why:** compounds `PERF-1`; typing a glyph should refresh ~a glyph, not a full row.
- **Verify:** unit test the X-bbox computation; ensure the slice length equals `Width*Height` for the
  chosen window.

## [x] PERF-3 🟠 `M` — Cut per-keystroke Python cost (full `getbuffer` + 480-row diff each key)

- **File:** `writerdeck/display/driver.py` (`display_partial` calls `self._epd.getbuffer(image)` then
  diffs all `HEIGHT` rows every call).
- **Problem:** on a Pi Zero 2 W, re-encoding the whole 800×480 image and diffing 480 rows on every
  keystroke adds latency before any SPI happens.
- **Fix:** keep the last buffer as a `bytearray`; where feasible limit the diff/encode to the region
  around the cursor line plus the stats band (post `PERF-1`). At minimum, avoid re-allocating on every
  key. Measure before/after with a simple timer log on hardware.
- **Why:** trims the non-hardware part of keystroke latency.
- **Verify:** logic unchanged (tests pass); optional micro-benchmark note in the PR/commit.

## [x] PERF-4 🟠 `S` — Don't full-refresh on the first keystroke after a short pause

- **File:** `writerdeck/display/refresh_manager.py` (`should_full_refresh`:
  `if time.monotonic() - self._last_refresh_time >= self._idle_full_seconds: return True`) and
  `writerdeck/core/app.py` (`_render_and_refresh` idle-timer handling; `_on_any_key` updates `_last_keypress`).
- **Problem:** `idle_full_refresh_seconds` (default 10) measures time since last *refresh*; typing
  slower than that, or pausing to think then resuming, forces a ~1 s full-refresh blink on the next
  keystroke — feels random. (This is distinct from the *intended* deep-clean after long idle — keep that.)
- **Fix:** reset/measure the idle-full timer against the last **keypress**, not the last refresh, so a
  brief pause-then-type does not blink. Keep the streak-based full (`LONG-2`) and the long-idle GC16
  deep clean.
- **Why:** removes a common surprise blink during normal thoughtful writing.
- **Verify:** unit test `RefreshManager` (or the app gate) so that a keypress after a short pause takes
  the partial path, while genuine long idle still forces a full/deep-clean.

## [x] PERF-5 🟠 `S` — Keep 4-gray strictly off the typing path

- **Files:** `writerdeck/core/app.py` (`_render_and_refresh`, the `elif self._config.use_4gray:` branch);
  `lib/waveshare_epd/epd7in5_V2.py` (`display_4Gray` uses per-byte `send_data()` ×48000).
- **Problem:** `display_4Gray` sends 48000 single-byte SPI writes plus Python bit-twiddling —
  seconds, not ms — and afterward forces the next keystroke into a fast-full. If `use_4gray: true`,
  every full refresh is brutal and interactive typing is unusable.
- **Fix:** never call `display_full_4gray` on an input-driven refresh; restrict 4-gray to explicit
  idle/preview only. If 4-gray is kept at all, batch its bytes into a single `send_data2()` bulk write.
- **Why:** protects the typing path from a pathological code path.
- **Verify:** confirm the render path selects `display_full`/`display_partial` for input-driven frames
  even when `use_4gray` is set; document that 4-gray is idle-only.

---

# Group C — Fault tolerance & panel longevity

Vendor-verified: leaving this panel **powered but not refreshing** keeps it at high voltage and per
Waveshare *"will damage the e-Paper and cannot be repaired"* (ESPHome issue #4739, quoting the manual).
Good Display: **full refresh after every 5 partials**; deep-sleep between updates; store white for long
idle; operating range **0–50 °C**.

## [x] LONG-1 🔴 `M` — Aggressive idle-sleep of the panel (bound the powered-idle window)

- **Files:** `writerdeck/core/app.py` (main loop sleep-tier block; `_on_any_key`; `_needs_display_wake`
  handling); `config_default.yaml` (add key).
- **Decision:** deep-sleep after **20 s** idle, wake on next keystroke; wake refresh is full.
- **Problem:** today the panel only sleeps at Tier-1 `display_off_minutes` (5 min), so it sits powered
  for minutes of idle plus the whole active session between refreshes — exactly the vendor-warned
  damage window.
- **Fix:** add `display_idle_sleep_seconds: 20` to `config_default.yaml`. In the main loop, when
  `idle_secs > display_idle_sleep_seconds` and not already sleeping, call `self._driver.sleep()` and
  set `_display_sleeping = True` (this already exists for the 5-min tier — lower the trigger to the new
  key). `_on_any_key` already sets `_needs_display_wake` + `request_full()`; keep that. Ensure the
  driver `sleep()`/`wake()` calls stay on the **main thread** (they already are — the key thread only
  sets a flag). Keep the existing Tier-2/Tier-3 (CPU/suspend) timers as-is.
- **Why:** shrinks the "powered & vulnerable" window from minutes to ~20 s; this is the single most
  effective mitigation for the crash-leaves-panel-on failure the user raised (Inkycal "sleep between
  updates" model).
- **Verify:** test that after `display_idle_sleep_seconds` with no key, `driver.sleep()` is called; a
  subsequent key triggers `wake()` + a full refresh. Confirm no SPI call happens from the key thread.

## [x] LONG-2 🔴 `S` — Lower `partial_refresh_max_streak` to 5 (+ wall-clock full backstop)

- **Files:** `config_default.yaml` (`partial_refresh_max_streak: 20`); `writerdeck/display/refresh_manager.py`.
- **Problem:** Good Display specifies a **full refresh after every 5 partials** for this panel; 20 lets
  ghosting accumulate. Also, a long steady-typing session that never idles and never hits the streak
  could go a long time between full refreshes.
- **Fix:** set `partial_refresh_max_streak: 5`. Add a wall-clock backstop in `RefreshManager`: force a
  full when `time.monotonic() - _last_full_time > full_refresh_max_seconds` (new config, e.g. 300 s),
  independent of streak/idle. (etyper enforces a 300 s floor.)
- **Why:** vendor-mandated ghost hygiene; cheap and high-value.
- **Verify:** unit test the streak (5 → full) and the wall-clock backstop.

## [x] FAULT-2 🔴 `M` — `systemd ExecStopPost` panel-sleep backstop + `TimeoutStopSec` (hardware-verify pending)

- **Files:** `writer-deck.service` and the generated unit in `setup.sh` (keep them in sync); add a small
  `tools/epd_sleep.py`.
- **Problem:** on `systemctl stop`, the app catches SIGTERM but only sets `_running = False`; if the
  loop is mid-refresh or slow, systemd waits the default 90 s then **SIGKILLs**, leaving the panel
  powered. `ExecStop=` does **not** run on crash; **`ExecStopPost=` runs even on crash/kill** (verified
  from systemd docs).
- **Fix:** add `tools/epd_sleep.py` — a standalone script that imports the Waveshare driver, does a
  minimal `EPD().init()` then `sleep()` (POWER_OFF + DEEP_SLEEP), guarded in try/except, exits 0.
  In the unit add:
  ```ini
  KillSignal=SIGTERM
  TimeoutStopSec=15
  ExecStopPost=/home/pi/projects/writer-deck/venv/bin/python /home/pi/projects/writer-deck/tools/epd_sleep.py
  ```
  Note: `ExecStopPost` is a **separate process** — it must re-init SPI from scratch and may briefly
  race the dying main process for the bus; the `TimeoutStopSec=15` gives the in-process handler time to
  win first (the deep-sleep path itself sleeps ~2 s).
- **Why:** guarantees a deep-sleep on the common non-violent exits (stop, timeout, most crashes).
- **Verify:** on hardware, `systemctl stop writer-deck` then confirm the panel is in deep sleep (no
  high-voltage draw); check journal shows `ExecStopPost` ran.

## [x] FAULT-3 🟠 `S` — `atexit` deep-sleep fallback (idempotent)

- **Files:** `main.py` and/or `writerdeck/core/app.py`; `writerdeck/display/driver.py`
  (`EPaperDriver.sleep`/`close`).
- **Problem:** cleanup runs via the signal handler → `_do_shutdown` → `driver.close()`, and `main.py`
  catches unhandled exceptions → `emergency_save()` → `driver.sleep()`. But a fault *during* cleanup,
  or an exit path that bypasses both, can skip sleep.
- **Fix:** `atexit.register(app._driver.close)` (or a module-level `_cleanup`). Make `sleep()`/`close()`
  **idempotent** (guard on `self._epd is not None` and a `_slept` flag) so double-invocation from
  signal + atexit is safe.
- **Why:** one-line belt-and-suspenders for any interpreter exit path.
- **Verify:** unit test that calling `close()` twice is safe; that `atexit` is registered.

## [x] FAULT-4 🟠 `S` — Hardware watchdog for kernel/hard hangs

- **Files:** `setup.sh` (boot config + `/etc/systemd/system.conf`); document in `README`/`CLAUDE.md`.
- **Problem:** the systemd `WatchdogSec` (sd_notify) catches an app-level hang, but a kernel freeze
  needs the SoC watchdog to force a reboot (after which boot-time `init()+Clear()` restores the panel).
- **Fix:** in `setup.sh`, enable `dtparam=watchdog=on` in the boot config and set
  `RuntimeWatchdogSec=14` (≤ ~15 s, the bcm2835 max) in `/etc/systemd/system.conf`.
- **Why:** turns a hard hang into a clean reboot + panel restore, instead of an indefinitely powered panel.
- **Verify:** after setup + reboot, `wdctl` shows the watchdog active; documented.

## [x] FAULT-5 🟠 `S` — Deep-sleep the panel **before** `poweroff` on critical battery

- **File:** `writerdeck/utils/power.py` (`_monitor_loop`); the callback wired in `app.py`
  (`_emergency_shutdown` → `emergency_save` → `driver.sleep()`).
- **Problem:** the monitor calls the shutdown callback then `os.system("sudo systemctl poweroff")`.
  Ensure the callback's `driver.sleep()` actually completes before power is cut (poweroff also stops the
  service, but don't rely on winning that race).
- **Fix:** make the emergency path deep-sleep the panel synchronously first (it already calls
  `emergency_save()` which calls `driver.sleep()`), and only then `poweroff`. Combine with `BUG-7`
  (debounce) so this only fires on a real critical battery.
- **Why:** the only mitigation that addresses true power loss is an *orderly* shutdown that sleeps the
  panel while the battery still holds.
- **Verify:** trace/log ordering: sleep completes → then poweroff issued.

## [x] FAULT-6 🟠 `M` — Guard display/SPI ops with bounded retry + graceful degradation

- **Files:** `writerdeck/display/driver.py` (`display_full`/`display_partial`/`display_clean`/`display_full_4gray`);
  optionally `app.py` `_render_and_refresh`.
- **Problem:** display ops are unguarded; a transient SPI/CRC/busy fault propagates to the top-level and
  takes down the app between watchdog cycles. The vendored `ReadBusy` returns after a 5 s timeout but
  the return value is ignored.
- **Fix:** wrap each display op in try/except with 1–2 bounded retries (re-`init` the current waveform
  between tries); on repeated failure, **log and skip the frame** (or degrade to a headless state —
  `FAULT-7`) rather than crash. Decide a single policy for a busy-timeout (treat as a failed op → retry
  path), don't silently ignore it.
- **Why:** an e-ink is a shared SPI peripheral; a glitch should not lose the app/session.
- **Verify:** unit test with a mock driver that raises once then succeeds → op retried, no exception
  escapes; raises repeatedly → frame skipped, app still running.

## [x] FAULT-7 🟠 `M` — Continue headless if the panel dies at runtime

- **Files:** `writerdeck/core/app.py` (render path); `writerdeck/display/driver.py`.
- **Problem:** you already fall back EPaperDriver→NullDriver at *startup*; there's no runtime fallback if
  the panel fails mid-session. Losing the display should not lose the user's text.
- **Fix:** on repeated display failures (from `FAULT-6`), switch to a headless/degraded mode that keeps
  accepting input and autosaving, surfaces a status, and periodically retries the panel. (RajveerRall
  zerowriter does this.)
- **Why:** protecting the words matters more than the screen.
- **Verify:** simulate a persistent display failure → app keeps saving keystrokes, no crash.

## [x] LONG-3 🟠 `S` — Blank-to-white before long-idle deep sleep (screensaver)

- **Files:** `writerdeck/core/app.py` (sleep-tier / idle handling); optionally a splash/white frame in
  `writerdeck/display/`.
- **Problem:** leaving a static high-contrast page on the panel for hours trends toward "inerasable"
  retention (Good Display /news/80). Aggressive idle-sleep (`LONG-1`) helps power, but the *image*
  remains on screen.
- **Fix:** before entering the long deep-sleep tier (or after a longer idle threshold, e.g. overnight),
  render a mostly-white "paused" frame (a small centered hint), then sleep. On wake, force a full
  refresh (already done).
- **Why:** vendor-recommended retention mitigation for a device that holds one page for long stretches.
- **Verify:** after the long-idle threshold, the last displayed frame is the white/paused frame.

## [~] LONG-4 (SKIPPED — no cheap temp source; out of scope) ⚪ `S` — Temperature gating (0–50 °C) — optional

- **File:** `writerdeck/core/app.py` render path; source a temperature (SoC temp or PiSugar if exposed).
- **Problem:** refreshing outside 0–50 °C ghosts badly and risks damage (vendor range).
- **Fix (optional, low priority indoors):** if a temperature source is available, skip/queue refreshes
  when out of range and show a status. Skip entirely if no cheap temperature source exists.
- **Verify:** N/A unless implemented.

---

# Group D — Ops / deploy

## [x] OPS-1 🟠 `M` — Atomic, revertible deploy (hardware-verify pending)

- **File:** `deploy.sh` (currently `rsync -avz --delete … --exclude …`).
- **Problem:** `rsync --delete` mutates the live tree in place; a mid-sync failure leaves partial code,
  and there's no rollback.
- **Fix:** deploy into a timestamped `releases/<ts>/` dir and swap a `current` symlink atomically
  (point the systemd `WorkingDirectory`/`ExecStart` at `current`), or use a git-checkout model
  (`git fetch` + `git reset --hard <rev>`) so a bad deploy is one command to revert. Keep the existing
  `--exclude` list (never delete data dirs). Restart the service after the swap.
- **Why:** makes deploys on a headless device reversible instead of "re-sync and hope".
- **Verify:** deploy, then roll back to the previous release/commit and confirm the service runs.

## [x] OPS-2 ⚪ `S` — Keep `writer-deck.service` and `setup.sh`'s generated unit in sync (hardware-verify pending)

- **Files:** `writer-deck.service` and the here-doc unit in `setup.sh` (§10).
- **Problem:** two copies of the unit; `FAULT-2`/`FAULT-4` changes must land in both.
- **Fix:** either have `setup.sh` install the checked-in `writer-deck.service` (single source of truth)
  or add a comment in both pointing at the other. Apply the `ExecStopPost`/`TimeoutStopSec`/watchdog
  changes to whichever becomes canonical.
- **Verify:** the installed unit matches the repo unit after `setup.sh`.

---

# Do NOT touch (by-design — do not "fix" these)

Re-derived from the code + vendor docs; changing these will introduce regressions.

- **CDI `0xA9` pre-inversion in `display_partial`** (`partial_slice = bytes(b ^ 0xFF …)`). The Waveshare
  `display_Partial` sets CDI `0x50 → 0xA9`, inverting pixel polarity vs full/fast (`0x10`). The XOR is
  required. Any X/Y windowing (`PERF-2`) must keep it.
- **`wake()` calls `epd.init()` without `Clear()`** and the first post-wake frame is forced full. This
  is deliberate (no white flash; controller RAM is reset so a partial would ghost). Keep the forced
  full on wake.
- **`_last_buf` is preserved through `sleep()`** — e-ink retains its image without power, so the diff
  reference stays valid after wake. Do not null it on sleep. (It *is* correctly nulled after 4-gray,
  because controller RAM is then in 4-gray format.)
- **The waveform cannot be made faster in software.** The vendored driver has **no LUT upload**; modes
  differ only by CDI and the `0xE5` selector — waveforms are OTP/factory-locked on this UC8179. Do not
  spend effort trying to load a custom A2/DU LUT before `PERF-1`/`PERF-2` are done; a ~2× waveform gain
  (unproven on this exact panel, and risky) is dwarfed by not refreshing 79% of the panel per word.
- **Long-idle GC16 deep clean** (`idle_deep_clean_seconds`) is intended ghost hygiene — keep it.
  `PERF-4` only changes the *short*-pause full-refresh trigger, not this.
- **`_mode` waveform-state caching** in `EPaperDriver` (skips ~140 ms re-inits when the waveform is
  unchanged) is a real optimization — preserve it when refactoring the partial path.

---

# Sources (for the "why"s above)

- Good Display 7.5" product page (UC8179; full 3 s / fast 1.5 s / partial 0.3 s "no flicker";
  "full refresh after every five consecutive operations"; 0–50 °C): https://www.good-display.com/product/396.html
- Good Display usage guidelines (deep-sleep between updates; store white to avoid inerasable retention;
  ≥180 s between update sets; refresh cadence): https://www.good-display.com/news/80.html
- Good Display waveform note (full refresh clears ghosting; OTP vs external-storage waveforms):
  https://www.good-display.com/news/205.html
- Waveshare "damage at high voltage / must sleep" warning, quoted verbatim + real user panel losses:
  https://github.com/esphome/issues/issues/4739
- Waveshare vendored driver `sleep()` = POWER_OFF (0x02) + DEEP_SLEEP (0x07/0xA5):
  `lib/waveshare_epd/epd7in5_V2.py` (and upstream waveshareteam/e-Paper)
- systemd `ExecStopPost` runs on crash/kill (vs `ExecStop`): systemd `man/systemd.service.xml`
- Comparable projects: Inkycal (sleep after each render), etyper (300 s full-refresh floor, fsync
  autosave, SIGINT/SIGTERM + finally), PaperTTY (line/block diff, `--fullevery`), ZeroWriter
  (finally-only sleep — the gap this plan closes), pwnagotchi (retry loops; PiSugar low-batt shutdown),
  RajveerRall/zerowriter (headless fallback; git reset --hard deploy).
