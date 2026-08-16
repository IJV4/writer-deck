# writerdeck/utils/

Guidance specific to the utility modules (text wrapping, perf instrumentation, platform/power).
Migrated out of the root `CLAUDE.md` (2026-08-15) so it only loads when working in this directory.

#### Text wrapping (`writerdeck/utils/text_wrapper.py`)

`wrap_lines()` caches each wrapped physical line's result in `_wrap_cache` (bounded to 2000 entries,
cleared on font change via `clear_wrap_cache()`). Within `_wrap_single_line`/`_break_word`,
`_text_width()` measures width by summing a memoized per-`(font, character)` cache rather than
calling `font.getlength()`/`getbbox()` on whole (sub)strings — both the character-break and
word-wrap loops used to grow a trial string and re-measure it from scratch on every character/word
(an O(n²) pattern), and even after fixing that, `getlength()`'s own real per-call cost on weak
hardware (Pi Zero 2W: ~2ms fixed + ~0.6-1.2ms/char) still mattered enough to need the memoization.
This assumes additive glyph advances (no cross-glyph kerning) — true for this monospace font, and the
same assumption `glyph_cache.py` (in `writerdeck/display/`) relies on.

#### Perf instrumentation (`writerdeck/utils/perf.py`)

Opt-in via `enable_perf_metrics: true` in `config.yaml` (must be set on the file the `current/`
release's `config.yaml` symlink actually resolves to — see the deploy note in the root `CLAUDE.md`,
it's easy to edit the wrong path). When enabled, `App` wraps `wrap_lines`, `render_frame`, `render_image`, and
`driver_display` in `perf.time(...)` and logs a `PerfMetrics summary` (p50/p95/max per stage) to the
log every 30s. This is how the four-layer performance investigation documented in `IMPROVEMENTS.md`
(2026-07-11 section) was actually diagnosed on real hardware rather than guessed at.

#### Platform and power (`writerdeck/utils/platform.py`, `writerdeck/utils/power.py`)

`detect_platform()` reads `/proc/device-tree/model` to distinguish Pi Zero 2 W, Pi 5, other Pi, and desktop. The result (`HardwareProfile`) determines default render interval and font size, and whether real hardware drivers are used.

`Power` polls a PiSugar battery over a Unix socket, triggers low-battery warnings via `StatusBar`, and calls an emergency shutdown callback at `battery_shutdown_percent` (default 10%) after `SHUTDOWN_DEBOUNCE_SAMPLES` consecutive critical, non-charging samples. `App.run()` also gates startup itself: if the battery reads below `battery_shutdown_percent` and isn't charging, it shows a charge-prompt message, waits 5s, wipes the panel (`EPaperDriver.close()`), and powers off instead of starting the editor (`App._startup_low_battery_shutdown()`). PiSugar's own firmware-level `auto_shutdown_level` (set directly on the Pi, outside this repo) should stay below `battery_shutdown_percent` — it's a hardware backstop only.

Three idle sleep tiers (configurable in `sleep_tiers`): display off → CPU powersave governor → systemd suspend. In practice Tier 1 is driven by `display_idle_sleep_seconds` (default 20s) rather than `sleep_tiers.display_off_minutes`, which is only a fallback when the former is `0`. A separate `display_screensaver_seconds` (LONG-3, default 300s) trigger blanks the panel to solid white on total idle time, independent of whether Tier 1 already put it to sleep — `App._show_screensaver()` wakes the panel if needed, paints, and re-sleeps it.

`FileManager` (`writerdeck/utils/file_manager.py`) — lists, loads, saves, and autosaves documents under `~/Documents/writer-deck/`.
