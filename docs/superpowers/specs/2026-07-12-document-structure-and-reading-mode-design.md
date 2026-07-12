# Document structure, reading mode, and info overlay

Status: approved (design), not yet planned/implemented.

## Context

WriterDeck currently has three writing modes (`distraction_free`, `dashboard`, `typewriter`) and
one flat text buffer per document (`writerdeck/core/document.py`), saved as a single `.txt`/`.md`
file (`writerdeck/utils/file_manager.py`). In practice only `distraction_free` gets used for actual
writing — `dashboard`'s sidebar and `typewriter`'s locked-line scroll aren't earning their keep as
separate modes. Separately, a document intended to grow into something book-length (chapters,
sections) has no internal structure once it's more than a page or two — just an undifferentiated
wall of text with no way to see or jump between sections.

This spec covers three related changes that came out of that discussion:

1. Lightweight document structure (markdown headings + an outline overlay to navigate them).
2. A read-only reading mode that replaces `dashboard` and `typewriter`.
3. An info overlay (replacing `dashboard`'s stats sidebar) reachable from either mode.

PERF-1 (deferring volatile stats like word count/battery to full-refresh cadence) was raised in the
same conversation but is already implemented in `writerdeck/core/app.py` (`_render_and_refresh`) —
no work needed there.

## 1. Document structure (headings + outline)

**Markup:** a line whose first non-space characters are `#` or `##` (standard markdown ATX heading,
levels 1-2 only — no need for `###`+ at this document length) marks a chapter or section title.
Stored as plain text in the `.txt`/`.md` file, so it stays readable/greppable/portable outside the
device.

**Rendering (`writerdeck/display/renderer.py`):** when a wrapped line is a heading line, the
renderer:
- strips the leading `#`/`##` and following space before drawing it,
- draws it in a larger font — base size `+6pt` for `#`, `+3pt` for `##`,
- ensures a blank line's worth of vertical space precedes it (skip if it's the first line).

This only affects *display*; the underlying `Document` text still stores the raw `# ...` line, and
`text_wrapper.wrap_lines` wraps the heading text at the *heading* font's width, not the body font's
(a heading line is treated as its own single line, not reflowed into the body paragraph).

**Outline overlay (`writerdeck/modes/outline_overlay.py`, new):** a new `Overlay` subclass following
the existing `FontPickerOverlay`/`FilePickerOverlay` pattern:
- Built from a scan of `doc._lines` for heading lines (done once when the overlay opens, not
  incrementally maintained — documents at this scale make a full scan on overlay-open cheap).
- Renders a navigable list: `#` headings at the left margin, `##` headings indented, current
  selection marked with `>`.
- `Arrow Up`/`Arrow Down` move selection, `Enter` sets `doc.cursor_line` to the selected heading's
  line and closes the overlay (forcing a full refresh, like other overlay-close transitions
  already do via `force_full_refresh`), `Escape` cancels with no cursor change.
- If the document has no headings, show a single "(no headings)" entry; `Enter`/`Escape` both just
  close it.
- Bound to `Ctrl+H` in `writerdeck/input/keymapper.py` (free combination — not currently bound).

**Testing:** unit tests for heading detection/stripping in the renderer (given a wrapped line
starting with `#`/`##`, correct font size and text are used), and for `OutlineOverlay` (heading
extraction, navigation, jump-on-enter, empty-document case) following the existing
`FontPickerOverlay` test style.

## 2. Reading mode

Replaces `dashboard` and `typewriter` as the second mode. New file
`writerdeck/modes/reading.py`, `ReadingMode(BaseMode)`, `name = "reading"`.

- **Read-only:** `handle_input` ignores all text-editing actions (character input, backspace,
  delete, enter-as-newline, undo/redo). It still handles `PAGE_PREV`/`PAGE_NEXT`, arrow-key
  scrolling, `FIND` (reuses the existing find overlay to locate text), and the new outline overlay.
- **Layout:** larger font than the writing modes (default body font size `+4pt`, configurable the
  same way `font_size` already is), full canvas width (no sidebar), no footer stats bar, no cursor
  drawn (`show_cursor=False` always).
- **Page turns:** `PAGE_PREV`/`PAGE_NEXT` move a full visible-lines page and set
  `force_full_refresh=True` on the resulting `RenderFrame` — a deliberate full-refresh "page flip"
  rather than the partial-refresh path used while typing, since there's no keystroke cadence to
  protect here and a crisp flip matters more than speed.
- **Entering the mode:** switching into `reading` (via `Tab`/`Ctrl+Shift+Tab`) forces a full refresh
  and opens on the page containing the document's current cursor position (read from `Document`,
  not reset to the top), so review picks up near where you were writing.

**Mode cycling:** `writerdeck/core/app.py`'s `_build_modes()` now returns
`[DistractionFreeMode, ReadingMode]` instead of three modes; `SWITCH_MODE_NEXT`/`SWITCH_MODE_PREV`
simply toggle between the two (existing cycling logic needs no change beyond the mode list).

**Removed:** `writerdeck/modes/dashboard.py`, `writerdeck/modes/typewriter.py`, and their dedicated
test files. Any dashboard-specific logic elsewhere (e.g. the `if self._mode.name == "dashboard":`
battery/remaining-time branch in `app.py::_render_and_refresh`) is deleted, not ported — dashboard's
useful info (battery, words, session, goal) moves into the info overlay instead (below).

**Testing:** render tests for `ReadingMode` (read-only input is rejected, page turns paginate and
set `force_full_refresh`, layout has no cursor/stats), plus updating `app.py` tests that reference
`dashboard`/`typewriter` mode names or the 3-mode cycle.

## 3. Info overlay

New `writerdeck/modes/info_overlay.py`, `InfoOverlay(Overlay)`, replacing dashboard's stats sidebar
as the way to see Words/Page/Session/Written/Goal/Battery.

- Built from the same `stats` dict data the modes already produce (`Words`, `Page`, `Session`,
  `Written`, `Goal`) plus battery (`Power.battery_bar()`, when `enable_battery_monitor` is on) and
  the current mode name.
- Read-only: any key (or `Escape`) closes it; no navigation state.
- `render()` draws a simple centered/list layout (`--- Info (any key to close) ---` header, like
  `FontPickerOverlay`'s header line style), `force_full_refresh=True` on open and on close.
- Bound to `Ctrl+I`, available from both `distraction_free` and `reading` modes (opened the same way
  `FIND`/`FONT_MENU` overlays already are in `app.py`'s input-handling branch — check
  `self._overlay is None` before opening, matching the existing overlay-open pattern).

**Testing:** unit tests for `InfoOverlay` construction (stats formatting, battery line
present/absent based on `enable_battery_monitor`) and close-on-any-key behavior.

## Out of scope (explicitly deferred)

- Cross-document "book" structure (grouping multiple chapter files under one project with a
  combined table of contents) — the file-picker's existing folder support already covers splitting
  a book into per-chapter files; this spec only addresses structure *within* one document.
- `###`+ heading levels, custom heading styling beyond font size, or configurable heading fonts.
- Any reading-mode annotation/highlighting features (pure read + navigate only).
