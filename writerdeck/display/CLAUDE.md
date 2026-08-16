# writerdeck/display/

Guidance specific to the display pipeline (renderer, glyph cache, EPaperDriver). Migrated out of the
root `CLAUDE.md` (2026-08-15) so it only loads when working in this directory — see the root file for
the overall display pipeline diagram and driver list.

#### Glyph cache (`writerdeck/display/glyph_cache.py`)

`renderer.py` draws all text via `draw_text_cached()`/`text_width_cached()`, never `draw.text()`/
`font.getbbox()` directly. `ImageDraw.text()` pays real FreeType rasterization cost per call
(measured ~1-2ms/char on a Pi Zero 2W) — PIL does not cache rasterized glyph bitmaps across calls, so
re-drawing the same characters every frame is not free. The glyph cache rasterizes each distinct
`(font, character)` once, thresholds the antialiased mask to `"1"` mode (see next paragraph), and
composites cached bitmaps via `draw.bitmap()` on subsequent draws — measured ~76x faster for a full
page of text once characters are warm.

**The threshold matters, don't drop it.** `ImageDraw.bitmap()` onto a `"1"`-mode (1-bit) target
applies a much stricter cutoff to an antialiased `"L"`-mode mask than `draw.text()` does internally —
without thresholding the mask to `"1"` mode first (`_THRESHOLD = 128` in `glyph_cache.py`), most
glyph ink is silently dropped (measured: a single glyph's black-pixel count went 25 → 2). This is
invisible in desktop tests (no pixel-level comparison against real hardware output) and only showed
up as visibly broken text on the real panel.

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
