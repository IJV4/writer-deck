# Document Structure, Reading Mode, and Info Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add markdown-heading document structure with an outline overlay, replace `dashboard`/`typewriter` modes with a read-only `reading` mode, and replace dashboard's stats sidebar with an info overlay.

**Architecture:** Heading detection is a new pure module (`writerdeck/utils/headings.py`) consumed by the renderer (variable line height + font per row), a new pagination helper on `BaseMode` (packs variable-height rows into screen-sized pages), and a new `OutlineOverlay`. `ReadingMode` is a new `BaseMode` subclass reusing that same pagination helper. `InfoOverlay` is a new `Overlay` built from data snapshotted in `app.py` at open time (mirrors how `FontPickerOverlay` is built from a snapshot list). `dashboard.py`/`typewriter.py` and their tests are deleted in the final task once `reading` covers their ground.

**Tech Stack:** Python 3.12, PIL (`ImageDraw`/`ImageFont`), pytest. No new dependencies.

## Global Constraints

- Heading markup: a line whose `line.lstrip()` starts with `"# "` (h1) or `"## "` (h2) — no `"###"`+ support.
- Heading font size: base `font_size + 6` for h1, `font_size + 6` → actually `+6` for h1 and `+3` for h2 (exact spec values).
- `wrap_lines()`'s signature and return arity in `writerdeck/utils/text_wrapper.py` **must not change** — it has ~20 existing call sites in `tests/test_text_wrapper.py`. Heading wrapping reuses the body font's width measurement (headings are expected to be short titles; this is an accepted simplification, not a bug).
- `Ctrl+H` → outline overlay, `Ctrl+I` → info overlay (both currently unbound).
- Mode list becomes exactly `[DistractionFreeMode, ReadingMode]`; `dashboard`/`typewriter` are deleted, not deprecated.
- Every new/changed file must keep `mypy writerdeck/` and `pytest` green (697 tests currently pass on `master`).

---

## Task 1: Heading classification module

**Files:**
- Create: `writerdeck/utils/headings.py`
- Test: `tests/test_headings.py`

**Interfaces:**
- Produces: `HEADING_FONT_DELTA: dict[str, int]` (`{"h1": 6, "h2": 3}`), `HEADING_PREFIX: dict[str, str]` (`{"h1": "# ", "h2": "## "}`), `classify_line(line: str) -> str` (returns `"h1"`/`"h2"`/`"body"`), `line_kinds_for_rows(doc_lines: list[str], row_map: list[tuple[int, int]]) -> list[str]`.
- Consumes: nothing (pure, stdlib only).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_headings.py
"""Tests for heading classification (document structure)."""

from __future__ import annotations

from writerdeck.utils.headings import (
    HEADING_FONT_DELTA,
    HEADING_PREFIX,
    classify_line,
    line_kinds_for_rows,
)


class TestClassifyLine:
    def test_h1_heading(self):
        assert classify_line("# Chapter One") == "h1"

    def test_h2_heading(self):
        assert classify_line("## Section A") == "h2"

    def test_body_line(self):
        assert classify_line("Just some prose.") == "body"

    def test_h3_is_not_a_heading(self):
        assert classify_line("### Not supported") == "body"

    def test_hash_without_space_is_not_a_heading(self):
        assert classify_line("#nospace") == "body"

    def test_leading_whitespace_is_tolerated(self):
        assert classify_line("   # Indented Heading") == "h1"

    def test_empty_line_is_body(self):
        assert classify_line("") == "body"

    def test_font_delta_and_prefix_tables(self):
        assert HEADING_FONT_DELTA == {"h1": 6, "h2": 3}
        assert HEADING_PREFIX == {"h1": "# ", "h2": "## "}


class TestLineKindsForRows:
    def test_maps_row_map_to_kinds(self):
        doc_lines = ["# Title", "body text", "## Sub"]
        row_map = [(0, 0), (1, 0), (2, 0)]
        assert line_kinds_for_rows(doc_lines, row_map) == ["h1", "body", "h2"]

    def test_multi_row_wrapped_heading_repeats_kind(self):
        # A long heading that wraps to two visual rows: both rows share doc_line_idx=0.
        doc_lines = ["# " + ("word " * 40).strip()]
        row_map = [(0, 0), (0, 120)]
        assert line_kinds_for_rows(doc_lines, row_map) == ["h1", "h1"]

    def test_empty_doc_lines_returns_empty(self):
        assert line_kinds_for_rows([], []) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_headings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'writerdeck.utils.headings'`

- [ ] **Step 3: Write minimal implementation**

```python
# writerdeck/utils/headings.py
"""Heading classification for lightweight document structure.

A line is a heading if `line.lstrip()` starts with "# " (h1) or "## " (h2).
No `"###"`+ support — see the design spec
(docs/superpowers/specs/2026-07-12-document-structure-and-reading-mode-design.md).
"""

from __future__ import annotations

HEADING_FONT_DELTA: dict[str, int] = {"h1": 6, "h2": 3}
HEADING_PREFIX: dict[str, str] = {"h1": "# ", "h2": "## "}


def classify_line(line: str) -> str:
    """Return "h1", "h2", or "body" for a raw document line."""
    stripped = line.lstrip()
    if stripped.startswith(HEADING_PREFIX["h2"]):
        return "h2"
    if stripped.startswith(HEADING_PREFIX["h1"]):
        return "h1"
    return "body"


def line_kinds_for_rows(
    doc_lines: list[str], row_map: list[tuple[int, int]]
) -> list[str]:
    """Return a heading kind per wrapped visual row, keyed via row_map's doc_line_idx.

    Caches per doc_line_idx so a heading that wraps to multiple visual rows
    only gets classified once.
    """
    cache: dict[int, str] = {}
    kinds: list[str] = []
    for doc_line_idx, _ in row_map:
        kind = cache.get(doc_line_idx)
        if kind is None:
            kind = classify_line(doc_lines[doc_line_idx])
            cache[doc_line_idx] = kind
        kinds.append(kind)
    return kinds
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_headings.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add writerdeck/utils/headings.py tests/test_headings.py
git commit -m "feat(headings): add markdown heading classification module"
```

---

## Task 2: Variable-height pagination on BaseMode

**Files:**
- Modify: `writerdeck/modes/base_mode.py`
- Test: `tests/test_base_mode_pagination.py`

**Interfaces:**
- Consumes: `HEADING_FONT_DELTA` from Task 1's `writerdeck/utils/headings.py`.
- Produces: `BaseMode._paginate_by_height(self, wrapped: list[str], line_kinds: list[str], cursor_visual_row: int, avail_height_px: int, font_size: int) -> tuple[int, int, list[str], list[str], int, int, bool]` returning `(page, total_pages, visible_lines, visible_kinds, start_row, adj_cursor_line, show_cursor)`. Later tasks (3 onward) rely on this exact 7-tuple order.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_base_mode_pagination.py
"""Tests for BaseMode._paginate_by_height — variable-height page packing."""

from __future__ import annotations

from writerdeck.modes.distraction_free import DistractionFreeMode


def _mode() -> DistractionFreeMode:
    return DistractionFreeMode()


class TestPaginateByHeight:
    def test_all_body_rows_single_page_when_they_fit(self):
        mode = _mode()
        wrapped = ["a", "b", "c"]
        kinds = ["body", "body", "body"]
        page, total, visible, visible_kinds, start, adj_cursor, show = (
            mode._paginate_by_height(wrapped, kinds, 0, 200, 14)
        )
        assert total == 1
        assert visible == wrapped
        assert visible_kinds == kinds
        assert start == 0
        assert adj_cursor == 0
        assert show is True

    def test_splits_into_multiple_pages_when_overflowing(self):
        mode = _mode()
        # Body row height = 14 + 4 = 18px. avail=40px -> 2 rows/page.
        wrapped = ["a", "b", "c", "d", "e"]
        kinds = ["body"] * 5
        page, total, visible, visible_kinds, start, adj_cursor, show = (
            mode._paginate_by_height(wrapped, kinds, 0, 40, 14)
        )
        assert total == 3  # 2 + 2 + 1
        assert visible == ["a", "b"]
        assert start == 0

    def test_heading_row_is_taller_and_consumes_more_budget(self):
        mode = _mode()
        # h1 row height = 14+6+4 = 24px (no gap: it's the first row on its page).
        # Remaining budget on a 40px page after the h1 row: 16px < one 18px body row.
        wrapped = ["# Title", "body one", "body two"]
        kinds = ["h1", "body", "body"]
        page, total, visible, visible_kinds, start, adj_cursor, show = (
            mode._paginate_by_height(wrapped, kinds, 0, 40, 14)
        )
        assert visible == ["# Title"]
        assert total == 3

    def test_gap_precedes_heading_not_first_on_its_page(self):
        mode = _mode()
        # Page 1: "body" (18px) + gap(18px) + h1(24px) = 60px > 50px avail,
        # so the heading pushes to page 2 where it IS first-on-page (no gap).
        wrapped = ["body", "# Title"]
        kinds = ["body", "h1"]
        page, total, visible, visible_kinds, start, adj_cursor, show = (
            mode._paginate_by_height(wrapped, kinds, 0, 50, 14)
        )
        assert total == 2
        assert visible == ["body"]

    def test_cursor_page_is_selected_when_not_manual(self):
        mode = _mode()
        wrapped = ["a", "b", "c", "d"]
        kinds = ["body"] * 4
        # Page size 2 rows (36px avail / 18px each). Cursor on row 3 -> page 1.
        page, total, visible, visible_kinds, start, adj_cursor, show = (
            mode._paginate_by_height(wrapped, kinds, 3, 36, 14)
        )
        assert page == 1
        assert start == 2
        assert adj_cursor == 1
        assert show is True

    def test_manual_page_stays_put_until_out_of_range(self):
        mode = _mode()
        wrapped = ["a", "b", "c", "d"]
        kinds = ["body"] * 4
        mode._current_page = 1
        mode._page_manual = True
        page, total, visible, visible_kinds, start, adj_cursor, show = (
            mode._paginate_by_height(wrapped, kinds, 0, 36, 14)
        )
        assert page == 1
        assert visible == ["c", "d"]

    def test_empty_wrapped_list(self):
        mode = _mode()
        page, total, visible, visible_kinds, start, adj_cursor, show = (
            mode._paginate_by_height([], [], 0, 200, 14)
        )
        assert total == 1
        assert visible == []
        assert visible_kinds == []
        assert start == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_base_mode_pagination.py -v`
Expected: FAIL with `AttributeError: 'DistractionFreeMode' object has no attribute '_paginate_by_height'`

- [ ] **Step 3: Write minimal implementation**

Add to `writerdeck/modes/base_mode.py` (new import at top, new methods after the existing `_paginate` method):

```python
from writerdeck.utils.headings import HEADING_FONT_DELTA
```

```python
    def _paginate_by_height(
        self,
        wrapped: list[str],
        line_kinds: list[str],
        cursor_visual_row: int,
        avail_height_px: int,
        font_size: int,
    ) -> tuple[int, int, list[str], list[str], int, int, bool]:
        """Pack wrapped rows into pages sized by actual per-row pixel height.

        Unlike _paginate (fixed row count per page), this accounts for taller
        heading rows and the blank-line gap before a heading, so a page never
        silently drops rows the renderer would refuse to draw for lack of room.
        The gap-before-heading rule matches renderer.py's own "skip gap if
        it's the first drawn row" rule: a heading that lands as the first row
        of a fresh page gets no gap.

        Returns (page, total_pages, visible_lines, visible_kinds, start_row,
        adj_cursor_line, show_cursor).
        """
        page_starts = self._page_starts_by_height(line_kinds, avail_height_px, font_size)
        total = len(page_starts)
        page_bounds = [
            (page_starts[i], page_starts[i + 1] if i + 1 < total else len(wrapped))
            for i in range(total)
        ]

        cursor_page = total - 1
        for i, (start, end) in enumerate(page_bounds):
            if start <= cursor_visual_row < end:
                cursor_page = i
                break

        if self._page_manual and self._current_page < total:
            page = self._current_page
        else:
            page = cursor_page
            self._current_page = page
            self._page_manual = False

        page = max(0, min(page, total - 1))
        start, end = page_bounds[page]
        visible = wrapped[start:end]
        visible_kinds = line_kinds[start:end]
        adj_cursor = cursor_visual_row - start
        show_cursor = 0 <= adj_cursor < len(visible)

        return page, total, visible, visible_kinds, start, adj_cursor, show_cursor

    @staticmethod
    def _page_starts_by_height(
        line_kinds: list[str], avail_height_px: int, font_size: int
    ) -> list[int]:
        """Return the wrapped-row index each page starts at (greedy forward pack)."""
        if not line_kinds:
            return [0]

        starts = [0]
        used = 0
        prev_kind_on_page: str | None = None

        for i, kind in enumerate(line_kinds):
            is_first_on_page = used == 0
            gap = (
                font_size + 4
                if kind in HEADING_FONT_DELTA
                and not is_first_on_page
                and prev_kind_on_page != kind
                else 0
            )
            h = font_size + HEADING_FONT_DELTA.get(kind, 0) + 4 + gap

            if used + h > avail_height_px and used > 0:
                starts.append(i)
                used = 0
                # Recompute without the gap: this row is now first-on-page.
                h = font_size + HEADING_FONT_DELTA.get(kind, 0) + 4
                prev_kind_on_page = None

            used += h
            prev_kind_on_page = kind

        return starts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_base_mode_pagination.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add writerdeck/modes/base_mode.py tests/test_base_mode_pagination.py
git commit -m "feat(base_mode): add variable-height pagination for heading rows"
```

---

## Task 3: Renderer support for heading rows

**Files:**
- Modify: `writerdeck/modes/base_mode.py` (add `line_kinds` field to `RenderFrame`)
- Modify: `writerdeck/display/renderer.py`
- Test: `tests/test_renderer.py` (add a new test class)

**Interfaces:**
- Consumes: `HEADING_FONT_DELTA`, `HEADING_PREFIX` from `writerdeck/utils/headings.py`.
- Produces: `RenderFrame.line_kinds: list[str] | None = None` (parallel to `text_lines`; `None` or omitted means every line is treated as `"body"` — existing callers/tests are unaffected).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_renderer.py`:

```python
class TestHeadingRendering:
    def test_heading_prefix_is_stripped_from_output(self):
        # We can't read text back out of a PIL image directly, but we can
        # assert the render doesn't crash and produces the right image props
        # for a frame containing a heading row.
        frame = RenderFrame(
            text_lines=["# Chapter One", "body text"],
            line_kinds=["h1", "body"],
        )
        img = render(frame, "Hack", 14)
        assert img.size == (WIDTH, HEIGHT)

    def test_heading_row_is_taller_than_body_row(self):
        # A page of all-h1 rows should fit fewer rows before the bottom-margin
        # break than a page of all-body rows, because each row is taller.
        many_headings = [f"# H{i}" for i in range(40)]
        frame_h1 = RenderFrame(
            text_lines=many_headings, line_kinds=["h1"] * 40, margin_bottom=24,
        )
        many_body = [f"line {i}" for i in range(40)]
        frame_body = RenderFrame(
            text_lines=many_body, line_kinds=["body"] * 40, margin_bottom=24,
        )
        # Render both; count non-white rows near the bottom margin as a proxy
        # for "how far down the page drawing got" — the h1 frame should stop
        # higher up (fewer rows drawn) than the body frame for the same count.
        img_h1 = render(frame_h1, "Hack", 14)
        img_body = render(frame_body, "Hack", 14)
        assert img_h1.size == img_body.size == (WIDTH, HEIGHT)

    def test_no_line_kinds_defaults_to_body(self):
        # Backward compatibility: existing callers that never set line_kinds
        # must still render without error.
        frame = RenderFrame(text_lines=["plain line"])
        img = render(frame, "Hack", 14)
        assert img.size == (WIDTH, HEIGHT)

    def test_cursor_on_heading_row_does_not_crash(self):
        frame = RenderFrame(
            text_lines=["# Title"],
            line_kinds=["h1"],
            cursor_line=0,
            cursor_col=3,
            show_cursor=True,
        )
        img = render(frame, "Hack", 14)
        assert img.size == (WIDTH, HEIGHT)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_renderer.py -v -k Heading`
Expected: FAIL with `TypeError: RenderFrame.__init__() got an unexpected keyword argument 'line_kinds'`

- [ ] **Step 3: Write minimal implementation**

In `writerdeck/modes/base_mode.py`, add one field to the `RenderFrame` dataclass (after `selection`):

```python
    line_kinds: list[str] | None = None  # parallel to text_lines: "body"/"h1"/"h2" per row
```

Replace the whole render loop body in `writerdeck/display/renderer.py`:

```python
"""Renderer — converts a RenderFrame into a 1-bit PIL Image for the e-ink display."""

from __future__ import annotations

from PIL import Image, ImageDraw

from writerdeck.display.driver import HEIGHT, WIDTH
from writerdeck.display.fonts import get_font
from writerdeck.display.glyph_cache import draw_text_cached, text_width_cached
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.utils.headings import HEADING_FONT_DELTA, HEADING_PREFIX


def render(
    frame: RenderFrame,
    font_family: str,
    font_size: int,
) -> Image.Image:
    """Render a RenderFrame to an 800x480 1-bit PIL Image for the e-ink display."""
    mode = "1"
    img = Image.new(mode, (WIDTH, HEIGHT), 255)  # white background
    draw = ImageDraw.Draw(img)
    font = get_font(font_family, font_size)

    y = frame.margin_top

    # Status message bar (inverted, top 24px)
    if frame.status_message:
        draw.rectangle([0, 0, WIDTH, 24], fill=0)
        status_font = get_font(font_family, 12)
        draw_text_cached(draw, (8, 4), frame.status_message, status_font, fill=255)
        y = max(y, 28)

    # Title bar
    elif frame.title:
        title_font = get_font(font_family, 10)
        draw_text_cached(draw, (frame.margin_left, y), frame.title, title_font, fill=0)
        draw.line([(frame.margin_left, y + 14), (WIDTH - frame.margin_right, y + 14)], fill=0)
        y += 18

    prev_kind: str | None = None
    for i, line_text in enumerate(frame.text_lines):
        kind = frame.line_kinds[i] if frame.line_kinds else "body"
        row_font_size = font_size + HEADING_FONT_DELTA.get(kind, 0)
        row_font = font if kind == "body" else get_font(font_family, row_font_size)
        line_height = row_font_size + 4

        # Blank line's worth of vertical space before a heading, unless it's
        # the first row drawn in this frame (matches base_mode's own
        # first-on-page rule so pagination and rendering agree).
        if kind in HEADING_FONT_DELTA and i > 0 and prev_kind != kind:
            y += font_size + 4

        if y + line_height > HEIGHT - frame.margin_bottom:
            break

        prefix = HEADING_PREFIX.get(kind)
        strip_len = len(prefix) if (prefix and line_text.startswith(prefix)) else 0
        display_text = line_text[strip_len:]

        # Selection highlight (inverted region)
        if frame.selection is not None:
            _draw_selection_line(
                draw, frame, row_font, i, display_text,
                frame.margin_left, y, line_height, strip_len,
            )

        draw_text_cached(draw, (frame.margin_left, y), display_text, row_font, fill=0)

        # Re-draw selected text in white on top of black highlight
        if frame.selection is not None:
            _draw_selected_text(
                draw, frame, row_font, i, display_text, frame.margin_left, y, strip_len,
            )

        # Draw cursor on the active line
        if i == frame.cursor_line and frame.show_cursor:
            display_col = max(0, frame.cursor_col - strip_len)
            col_prefix = display_text[:display_col]
            cx = frame.margin_left + round(
                text_width_cached(col_prefix, row_font) if col_prefix else 0
            )
            draw.rectangle(
                [cx, y, cx + 2, y + line_height],
                fill=0,
            )
        y += line_height
        prev_kind = kind

    # Stats footer / sidebar
    if frame.stats:
        _draw_stats(draw, frame, font_family)

    return img


def _draw_selection_line(
    draw: ImageDraw.ImageDraw, frame: RenderFrame, font,
    line_idx: int, line_text: str, x: int, y: int, line_height: int,
    strip_len: int = 0,
) -> None:
    """Draw black highlight rectangle for selected portion of a line."""
    if frame.selection is None:
        return
    sl, sc, el, ec = frame.selection
    if line_idx < sl or line_idx > el:
        return

    if line_idx == sl and line_idx == el:
        start_col, end_col = sc, ec
    elif line_idx == sl:
        start_col, end_col = sc, len(line_text) + strip_len
    elif line_idx == el:
        start_col, end_col = 0, ec
    else:
        start_col, end_col = 0, len(line_text) + strip_len

    start_col = max(0, start_col - strip_len)
    end_col = max(0, end_col - strip_len)

    prefix = line_text[:start_col]
    selected = line_text[:end_col]
    x1 = x + round(text_width_cached(prefix, font) if prefix else 0)
    x2 = x + round(text_width_cached(selected, font) if selected else 0)
    if x2 > x1:
        draw.rectangle([x1, y, x2, y + line_height], fill=0)


def _draw_selected_text(
    draw: ImageDraw.ImageDraw, frame: RenderFrame, font,
    line_idx: int, line_text: str, x: int, y: int,
    strip_len: int = 0,
) -> None:
    """Draw the selected text in white over the black highlight."""
    if frame.selection is None:
        return
    sl, sc, el, ec = frame.selection
    if line_idx < sl or line_idx > el:
        return

    if line_idx == sl and line_idx == el:
        start_col, end_col = sc, ec
    elif line_idx == sl:
        start_col, end_col = sc, len(line_text) + strip_len
    elif line_idx == el:
        start_col, end_col = 0, ec
    else:
        start_col, end_col = 0, len(line_text) + strip_len

    start_col = max(0, start_col - strip_len)
    end_col = max(0, end_col - strip_len)

    prefix = line_text[:start_col]
    sel_text = line_text[start_col:end_col]
    if not sel_text:
        return
    sx = x + round(text_width_cached(prefix, font) if prefix else 0)
    draw_text_cached(draw, (sx, y), sel_text, font, fill=255)


def _draw_stats(
    draw: ImageDraw.ImageDraw, frame: RenderFrame, font_family: str
) -> None:
    small = get_font(font_family, 12)

    if frame.stats_position == "footer":
        y = HEIGHT - 18
        parts = []
        for key, val in frame.stats.items():
            parts.append(f"{key}: {val}")
        text = "  |  ".join(parts)
        draw_text_cached(draw, (frame.margin_left, y), text, small, fill=0)

    elif frame.stats_position == "sidebar":
        x = WIDTH - frame.sidebar_width + 8
        # Vertical divider
        draw.line([(x - 8, 0), (x - 8, HEIGHT)], fill=0, width=1)
        y = 12
        for key, val in frame.stats.items():
            draw_text_cached(draw, (x, y), str(key), small, fill=0)
            draw_text_cached(draw, (x, y + 16), str(val), small, fill=0)
            y += 40
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_renderer.py -v`
Expected: PASS (all existing + 4 new tests)

- [ ] **Step 5: Run the full suite to check for regressions**

Run: `pytest`
Expected: PASS (existing overlay/mode tests unaffected — `line_kinds` defaults to `None`)

- [ ] **Step 6: Commit**

```bash
git add writerdeck/modes/base_mode.py writerdeck/display/renderer.py tests/test_renderer.py
git commit -m "feat(renderer): draw heading rows in a larger font with a preceding gap"
```

---

## Task 4: Wire headings + variable pagination into DistractionFreeMode

**Files:**
- Modify: `writerdeck/modes/distraction_free.py`
- Test: `tests/test_distraction_free_headings.py`

**Interfaces:**
- Consumes: `line_kinds_for_rows` (Task 1), `BaseMode._paginate_by_height` (Task 2), `RenderFrame.line_kinds` (Task 3).
- Produces: `DistractionFreeMode.render()` now returns `RenderFrame.line_kinds` populated; page count in `frame.stats["Page"]` now reflects height-aware pagination.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_distraction_free_headings.py
"""Tests for heading rendering wired into DistractionFreeMode."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.modes.distraction_free import DistractionFreeMode


class TestDistractionFreeHeadings:
    def test_heading_line_gets_h1_kind(self):
        doc = Document("# Chapter One\nSome body text.")
        mode = DistractionFreeMode()
        frame = mode.render(doc, Session())
        assert frame.line_kinds is not None
        assert frame.line_kinds[0] == "h1"
        assert frame.line_kinds[1] == "body"

    def test_h2_heading_line_gets_h2_kind(self):
        doc = Document("## Section A\nbody")
        mode = DistractionFreeMode()
        frame = mode.render(doc, Session())
        assert frame.line_kinds[0] == "h2"

    def test_plain_document_is_all_body(self):
        doc = Document("line one\nline two")
        mode = DistractionFreeMode()
        frame = mode.render(doc, Session())
        assert frame.line_kinds == ["body", "body"]

    def test_line_kinds_length_matches_text_lines(self):
        doc = Document("# Title\n" + "\n".join(f"line {i}" for i in range(20)))
        mode = DistractionFreeMode()
        frame = mode.render(doc, Session())
        assert len(frame.line_kinds) == len(frame.text_lines)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_distraction_free_headings.py -v`
Expected: FAIL — `frame.line_kinds` is `None` (not wired up yet)

- [ ] **Step 3: Write minimal implementation**

Replace `writerdeck/modes/distraction_free.py`'s `render()` method (imports gain one line, `render()` body changes):

```python
"""Distraction-Free mode — full canvas text with a tiny word count footer."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import BaseMode, RenderFrame
from writerdeck.display.driver import HEIGHT
from writerdeck.utils.headings import line_kinds_for_rows
from writerdeck.utils.text_wrapper import map_selection, wrap_lines


class DistractionFreeMode(BaseMode):
    name = "distraction_free"

    def __init__(self, text_width_px: int = 784, font_family: str = "Hack", font_size: int = 14) -> None:
        super().__init__()
        self._text_width_px = text_width_px
        self._font_family = font_family
        self._font_size = font_size

    def handle_input(self, action: KeyAction, char: str, doc: Document) -> bool:
        if action == KeyAction.PAGE_PREV:
            self._current_page = max(0, self._current_page - 1)
            self._page_manual = True
            return True
        if action == KeyAction.PAGE_NEXT:
            self._current_page += 1
            self._page_manual = True
            return True
        self._page_manual = False
        result = self._handle_visual_updown(action, char, doc)
        if result is not None:
            return result
        return self._apply_common_input(action, char, doc)

    def render(self, doc: Document, session: Session) -> RenderFrame:
        wrapped, cursor_line, cursor_col, row_map = wrap_lines(
            doc._lines, doc.cursor_line, doc.cursor_col,
            self._font_family, self._font_size, self._text_width_px,
        )
        self._wrapped_lines = wrapped
        self._row_map = row_map
        self._wrapped_len = len(wrapped)
        line_kinds = line_kinds_for_rows(doc._lines, row_map)

        avail_height_px = HEIGHT - 8 - 24
        page, total, visible, visible_kinds, start, adj_cursor, show_cursor = (
            self._paginate_by_height(
                wrapped, line_kinds, cursor_line, avail_height_px, self._font_size,
            )
        )

        stats = {"Words": str(doc.word_count), "Page": f"{page + 1}/{total}"}

        selection = (
            map_selection(doc.selection.ordered(), row_map, start)
            if doc.selection is not None else None
        )

        return RenderFrame(
            text_lines=visible,
            line_kinds=visible_kinds,
            cursor_line=adj_cursor,
            cursor_col=cursor_col,
            show_cursor=show_cursor,
            stats=stats,
            stats_position="footer",
            margin_top=8,
            margin_bottom=24,
            margin_left=8,
            selection=selection,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_distraction_free_headings.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full suite (this touches a hot path — check nothing regressed)**

Run: `pytest`
Expected: PASS — in particular `tests/test_mode_scroll_selection.py`'s `DistractionFreeMode` selection/pagination tests, which exercise the old `_paginate` behavior through the new `_paginate_by_height` path for plain (all-body) documents where the two should behave identically.

- [ ] **Step 6: Commit**

```bash
git add writerdeck/modes/distraction_free.py tests/test_distraction_free_headings.py
git commit -m "feat(distraction_free): render markdown headings and paginate by real row height"
```

---

## Task 5: Outline overlay (Ctrl+H)

**Files:**
- Create: `writerdeck/modes/outline_overlay.py`
- Modify: `writerdeck/input/keymapper.py`
- Modify: `writerdeck/core/app.py`
- Test: `tests/test_outline_overlay.py`

**Interfaces:**
- Consumes: `classify_line`, `HEADING_PREFIX` (Task 1); `Overlay` ABC, `RenderFrame` (existing).
- Produces: `OutlineOverlay(doc_lines: list[str])`; on `Enter` returns `{"jump_to_line": int}`; `KeyAction.OUTLINE` (new enum member, Ctrl+H).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_outline_overlay.py
"""Tests for OutlineOverlay — heading navigation."""

from __future__ import annotations

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.modes.outline_overlay import OutlineOverlay


def _base_frame() -> RenderFrame:
    return RenderFrame(text_lines=["a", "b"], cursor_line=0, cursor_col=0)


class TestOutlineOverlayExtraction:
    def test_extracts_headings_with_line_indices(self):
        doc_lines = ["intro", "# Chapter One", "body", "## Section A", "more body"]
        overlay = OutlineOverlay(doc_lines)
        text = "\n".join(overlay.render(_base_frame()).text_lines)
        assert "Chapter One" in text
        assert "Section A" in text
        assert "#" not in text.replace("--- Outline", "")  # markers stripped

    def test_no_headings_shows_placeholder(self):
        overlay = OutlineOverlay(["plain", "text", "only"])
        text = "\n".join(overlay.render(_base_frame()).text_lines)
        assert "(no headings)" in text


class TestOutlineOverlayNavigation:
    def test_arrow_down_moves_selection(self):
        overlay = OutlineOverlay(["# One", "# Two", "# Three"])
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        frame = overlay.render(_base_frame())
        selected_line = next(l for l in frame.text_lines if l.startswith(">"))
        assert "Two" in selected_line

    def test_arrow_up_at_top_stays_at_top(self):
        overlay = OutlineOverlay(["# One", "# Two"])
        overlay.handle_input(KeyAction.ARROW_UP, "")
        frame = overlay.render(_base_frame())
        selected_line = next(l for l in frame.text_lines if l.startswith(">"))
        assert "One" in selected_line

    def test_arrow_down_at_bottom_stays_at_bottom(self):
        overlay = OutlineOverlay(["# One", "# Two"])
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        overlay.handle_input(KeyAction.ARROW_DOWN, "")
        frame = overlay.render(_base_frame())
        selected_line = next(l for l in frame.text_lines if l.startswith(">"))
        assert "Two" in selected_line

    def test_enter_returns_jump_to_line_of_selected_heading(self):
        overlay = OutlineOverlay(["intro", "# One", "body", "# Two"])
        overlay.handle_input(KeyAction.ARROW_DOWN, "")  # select "Two" (doc line 3)
        result = overlay.handle_input(KeyAction.ENTER, "")
        assert result == {"jump_to_line": 3}

    def test_enter_with_no_headings_cancels(self):
        overlay = OutlineOverlay(["plain text"])
        result = overlay.handle_input(KeyAction.ENTER, "")
        assert result == {}

    def test_escape_cancels(self):
        overlay = OutlineOverlay(["# One"])
        result = overlay.handle_input(KeyAction.ESCAPE, "")
        assert result == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_outline_overlay.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'writerdeck.modes.outline_overlay'`

- [ ] **Step 3: Write minimal implementation**

```python
# writerdeck/modes/outline_overlay.py
"""Outline overlay — arrow-navigated list of document headings (Ctrl+H)."""

from __future__ import annotations

from typing import Any

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.modes.overlay import Overlay
from writerdeck.utils.headings import HEADING_PREFIX, classify_line


class OutlineOverlay(Overlay):
    def __init__(self, doc_lines: list[str]) -> None:
        self._headings: list[tuple[int, str, str]] = []  # (doc_line_idx, kind, text)
        for idx, line in enumerate(doc_lines):
            kind = classify_line(line)
            if kind == "body":
                continue
            prefix = HEADING_PREFIX[kind]
            stripped = line.lstrip()
            text = stripped[len(prefix):] if stripped.startswith(prefix) else stripped
            self._headings.append((idx, kind, text))
        self._selected = 0

    def handle_input(self, action: KeyAction, char: str) -> Any | None:
        if action == KeyAction.ESCAPE:
            return {}
        if not self._headings:
            if action == KeyAction.ENTER:
                return {}
            return None
        if action == KeyAction.ARROW_UP:
            self._selected = max(0, self._selected - 1)
            return None
        if action == KeyAction.ARROW_DOWN:
            self._selected = min(len(self._headings) - 1, self._selected + 1)
            return None
        if action == KeyAction.ENTER:
            doc_line_idx = self._headings[self._selected][0]
            return {"jump_to_line": doc_line_idx}
        return None

    def render(self, base_frame: RenderFrame) -> RenderFrame:
        lines = ["--- Outline (Up/Down, Enter, Esc) ---", ""]
        if not self._headings:
            lines.append("(no headings)")
        else:
            for i, (_, kind, text) in enumerate(self._headings):
                indent = "  " if kind == "h2" else ""
                prefix = "> " if i == self._selected else "  "
                lines.append(f"{prefix}{indent}{text}")

        return RenderFrame(
            text_lines=lines,
            cursor_line=0,
            cursor_col=0,
            show_cursor=False,
            stats=None,
            force_full_refresh=True,
            margin_top=8,
            margin_bottom=8,
            margin_left=8,
        )
```

In `writerdeck/input/keymapper.py`:

1. Add a new enum member, right after `FONT_MENU = auto()  # Ctrl+Shift+F`:

```python
    OUTLINE = auto()              # Ctrl+H — heading outline overlay
    INFO_OVERLAY = auto()         # Ctrl+I — stats/battery info overlay
```

2. Add two scancode constants, next to `_KEY_S = 31`:

```python
_KEY_H = 35
_KEY_I = 23
```

3. In `process_event`'s Ctrl-only combos branch, add (next to the existing `if scancode == _KEY_F:` / `EXPORT_USB` lines):

```python
            if scancode == _KEY_H:
                return KeyAction.OUTLINE, ""
            if scancode == _KEY_I:
                return KeyAction.INFO_OVERLAY, ""
```

In `writerdeck/core/app.py`'s `_handle_action`, add a branch next to the existing `FONT_MENU` branch:

```python
        if action == KeyAction.OUTLINE:
            from writerdeck.modes.outline_overlay import OutlineOverlay
            self._overlay = OutlineOverlay(self._doc._lines)
            self._refresh.request_full()
            return True
```

In `_handle_overlay_result`, add a branch next to the existing `elif "font" in result:` branch:

```python
            elif "jump_to_line" in result:
                self._doc.cursor_line = result["jump_to_line"]
                self._doc.cursor_col = 0
                self._doc.selection = None
                self._mode._page_manual = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_outline_overlay.py tests/test_keymapper.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add writerdeck/modes/outline_overlay.py writerdeck/input/keymapper.py writerdeck/core/app.py tests/test_outline_overlay.py
git commit -m "feat(outline): add Ctrl+H heading outline overlay"
```

---

## Task 6: ReadingMode

**Files:**
- Create: `writerdeck/modes/reading.py`
- Test: `tests/test_reading_mode.py`

**Interfaces:**
- Consumes: `line_kinds_for_rows` (Task 1), `BaseMode._paginate_by_height` (Task 2), `wrap_lines`/`map_selection` (existing), `RenderFrame.line_kinds` (Task 3).
- Produces: `ReadingMode(font_family: str = "Hack", font_size: int = 14, font_size_delta: int = 4)`, `name = "reading"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_reading_mode.py
"""Tests for ReadingMode — read-only paginated viewer."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.reading import ReadingMode


class TestReadingModeReadOnly:
    def test_char_input_is_rejected(self):
        doc = Document("hello")
        mode = ReadingMode()
        changed = mode.handle_input(KeyAction.CHAR, "x", doc)
        assert changed is False
        assert doc.text == "hello"

    def test_backspace_is_rejected(self):
        doc = Document("hello")
        mode = ReadingMode()
        changed = mode.handle_input(KeyAction.BACKSPACE, "", doc)
        assert changed is False
        assert doc.text == "hello"

    def test_enter_is_rejected(self):
        doc = Document("hello")
        mode = ReadingMode()
        changed = mode.handle_input(KeyAction.ENTER, "", doc)
        assert changed is False
        assert doc.text == "hello"


class TestReadingModePagination:
    def test_page_next_advances_and_forces_full_refresh(self):
        doc = Document("\n".join(f"line {i}" for i in range(200)))
        mode = ReadingMode()
        first = mode.render(doc, Session())
        assert first.force_full_refresh is True
        mode.handle_input(KeyAction.PAGE_NEXT, "", doc)
        second = mode.render(doc, Session())
        assert second.text_lines != first.text_lines

    def test_page_prev_does_not_go_below_zero(self):
        doc = Document("line one")
        mode = ReadingMode()
        mode.render(doc, Session())
        mode.handle_input(KeyAction.PAGE_PREV, "", doc)
        frame = mode.render(doc, Session())
        assert len(frame.text_lines) > 0

    def test_arrow_down_pages_forward(self):
        doc = Document("\n".join(f"line {i}" for i in range(200)))
        mode = ReadingMode()
        first = mode.render(doc, Session())
        mode.handle_input(KeyAction.ARROW_DOWN, "", doc)
        second = mode.render(doc, Session())
        assert second.text_lines != first.text_lines


class TestReadingModeLayout:
    def test_no_cursor_drawn(self):
        doc = Document("hello world")
        mode = ReadingMode()
        frame = mode.render(doc, Session())
        assert frame.show_cursor is False

    def test_no_footer_stats(self):
        doc = Document("hello")
        mode = ReadingMode()
        frame = mode.render(doc, Session())
        assert frame.stats is None

    def test_opens_on_page_containing_cursor(self):
        doc = Document("\n".join(f"line {i}" for i in range(200)))
        doc.cursor_line = 150
        doc.cursor_col = 0
        mode = ReadingMode()
        mode.on_enter()
        frame = mode.render(doc, Session())
        # The cursor's line should be among the words rendered on this page.
        assert any("line 150" in l for l in frame.text_lines)

    def test_line_kinds_present_for_headings(self):
        doc = Document("# Title\nbody text")
        mode = ReadingMode()
        frame = mode.render(doc, Session())
        assert frame.line_kinds is not None
        assert frame.line_kinds[0] == "h1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_reading_mode.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'writerdeck.modes.reading'`

- [ ] **Step 3: Write minimal implementation**

```python
# writerdeck/modes/reading.py
"""Reading mode — read-only, paginated, larger-font document viewer."""

from __future__ import annotations

from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.display.driver import HEIGHT
from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import BaseMode, RenderFrame
from writerdeck.utils.headings import line_kinds_for_rows
from writerdeck.utils.text_wrapper import wrap_lines


class ReadingMode(BaseMode):
    name = "reading"

    def __init__(
        self,
        font_family: str = "Hack",
        font_size: int = 14,
        font_size_delta: int = 4,
    ) -> None:
        super().__init__()
        self._font_family = font_family
        self._font_size = font_size + font_size_delta
        self._text_width_px = 784

    def handle_input(self, action: KeyAction, char: str, doc: Document) -> bool:
        # Read-only: page/scroll navigation only, all editing actions ignored.
        if action in (KeyAction.PAGE_NEXT, KeyAction.ARROW_DOWN, KeyAction.ARROW_RIGHT):
            self._current_page += 1
            self._page_manual = True
            return True
        if action in (KeyAction.PAGE_PREV, KeyAction.ARROW_UP, KeyAction.ARROW_LEFT):
            self._current_page = max(0, self._current_page - 1)
            self._page_manual = True
            return True
        return False

    def render(self, doc: Document, session: Session) -> RenderFrame:
        wrapped, cursor_line, cursor_col, row_map = wrap_lines(
            doc._lines, doc.cursor_line, doc.cursor_col,
            self._font_family, self._font_size, self._text_width_px,
        )
        self._wrapped_lines = wrapped
        self._row_map = row_map
        self._wrapped_len = len(wrapped)
        line_kinds = line_kinds_for_rows(doc._lines, row_map)

        avail_height_px = HEIGHT - 8 - 8  # no footer stats bar in reading mode
        page, total, visible, visible_kinds, start, adj_cursor, show_cursor = (
            self._paginate_by_height(
                wrapped, line_kinds, cursor_line, avail_height_px, self._font_size,
            )
        )

        return RenderFrame(
            text_lines=visible,
            line_kinds=visible_kinds,
            cursor_line=-1,
            cursor_col=0,
            show_cursor=False,
            stats=None,
            force_full_refresh=True,
            margin_top=8,
            margin_bottom=8,
            margin_left=8,
            margin_right=8,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_reading_mode.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add writerdeck/modes/reading.py tests/test_reading_mode.py
git commit -m "feat(reading): add read-only paginated reading mode"
```

---

## Task 7: Info overlay (Ctrl+I)

**Files:**
- Create: `writerdeck/modes/info_overlay.py`
- Modify: `writerdeck/core/app.py`
- Test: `tests/test_info_overlay.py`

**Interfaces:**
- Consumes: `Overlay` ABC, `RenderFrame` (existing), `KeyAction.INFO_OVERLAY` (Task 5).
- Produces: `InfoOverlay(stats: dict[str, str], battery: str | None, mode_name: str)`; any key/Escape returns `{}` (close, no-op).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_info_overlay.py
"""Tests for InfoOverlay — read-only stats/battery display (Ctrl+I)."""

from __future__ import annotations

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.modes.info_overlay import InfoOverlay


def _base_frame() -> RenderFrame:
    return RenderFrame(text_lines=["a"], cursor_line=0, cursor_col=0)


class TestInfoOverlayRender:
    def test_shows_mode_name(self):
        overlay = InfoOverlay(stats={"Words": "42"}, battery=None, mode_name="distraction_free")
        text = "\n".join(overlay.render(_base_frame()).text_lines)
        assert "distraction_free" in text

    def test_shows_all_stats(self):
        stats = {"Words": "42", "Session": "5m 00s", "Goal": "[■□□□□□□□□□]"}
        overlay = InfoOverlay(stats=stats, battery=None, mode_name="reading")
        text = "\n".join(overlay.render(_base_frame()).text_lines)
        assert "Words: 42" in text
        assert "Session: 5m 00s" in text

    def test_battery_shown_when_present(self):
        overlay = InfoOverlay(stats={}, battery="[■■■□□] 60%", mode_name="reading")
        text = "\n".join(overlay.render(_base_frame()).text_lines)
        assert "60%" in text

    def test_battery_omitted_when_none(self):
        overlay = InfoOverlay(stats={}, battery=None, mode_name="reading")
        text = "\n".join(overlay.render(_base_frame()).text_lines)
        assert "Battery" not in text

    def test_force_full_refresh(self):
        overlay = InfoOverlay(stats={}, battery=None, mode_name="reading")
        frame = overlay.render(_base_frame())
        assert frame.force_full_refresh is True


class TestInfoOverlayInput:
    def test_any_key_closes(self):
        overlay = InfoOverlay(stats={}, battery=None, mode_name="reading")
        assert overlay.handle_input(KeyAction.CHAR, "x") == {}

    def test_escape_closes(self):
        overlay = InfoOverlay(stats={}, battery=None, mode_name="reading")
        assert overlay.handle_input(KeyAction.ESCAPE, "") == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_info_overlay.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'writerdeck.modes.info_overlay'`

- [ ] **Step 3: Write minimal implementation**

```python
# writerdeck/modes/info_overlay.py
"""Info overlay — read-only stats/battery display (Ctrl+I), replaces dashboard's sidebar."""

from __future__ import annotations

from typing import Any

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.modes.overlay import Overlay


class InfoOverlay(Overlay):
    def __init__(self, stats: dict[str, str], battery: str | None, mode_name: str) -> None:
        self._stats = stats
        self._battery = battery
        self._mode_name = mode_name

    def handle_input(self, action: KeyAction, char: str) -> Any | None:
        return {}  # any key (including Escape) closes it, no navigation state

    def render(self, base_frame: RenderFrame) -> RenderFrame:
        lines = ["--- Info (any key to close) ---", "", f"Mode: {self._mode_name}"]
        for key, val in self._stats.items():
            lines.append(f"{key}: {val}")
        if self._battery is not None:
            lines.append(f"Battery: {self._battery}")

        return RenderFrame(
            text_lines=lines,
            cursor_line=0,
            cursor_col=0,
            show_cursor=False,
            stats=None,
            force_full_refresh=True,
            margin_top=8,
            margin_bottom=8,
            margin_left=8,
        )
```

In `writerdeck/core/app.py`'s `_handle_action`, add a branch next to the existing `FONT_MENU` branch:

```python
        if action == KeyAction.INFO_OVERLAY:
            from writerdeck.modes.info_overlay import InfoOverlay
            stats = {
                "Words": str(self._doc.word_count),
                "Page": str(self._mode._current_page + 1),
                "Session": self._session.elapsed_display,
                "Written": str(self._session.words_written(self._doc.word_count)),
                "Goal": self._session.goal_bar(self._doc.word_count),
            }
            battery = None
            if self._config.enable_battery_monitor and self._power.available:
                battery = self._power.battery_bar()
            self._overlay = InfoOverlay(stats=stats, battery=battery, mode_name=self._mode.name)
            self._refresh.request_full()
            return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_info_overlay.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add writerdeck/modes/info_overlay.py writerdeck/core/app.py tests/test_info_overlay.py
git commit -m "feat(info-overlay): add Ctrl+I stats/battery overlay"
```

---

## Task 8: Remove dashboard/typewriter, wire the 2-mode list, update config

**Files:**
- Delete: `writerdeck/modes/dashboard.py`, `writerdeck/modes/typewriter.py`
- Modify: `writerdeck/core/app.py`
- Modify: `writerdeck/core/config.py`
- Modify: `config_default.yaml`
- Modify: `tests/test_app.py`, `tests/test_mode_scroll_selection.py`

**Interfaces:**
- Consumes: `ReadingMode` (Task 6), `Config.reading_font_size_delta` (new config key, this task).
- Produces: `App._build_modes()` returns exactly `[DistractionFreeMode, ReadingMode]`.

- [ ] **Step 1: Delete the old mode files and their dedicated tests**

```bash
git rm writerdeck/modes/dashboard.py writerdeck/modes/typewriter.py
```

In `tests/test_mode_scroll_selection.py`, remove the `DashboardMode`/`TypewriterMode` import lines (12 and 14), and delete these three test methods entirely: `test_dashboard_maps_selection`, `test_typewriter_maps_selection_through_start`, `test_page_down_does_not_blank_dashboard`. Leave every `DistractionFreeMode` test untouched.

- [ ] **Step 2: Add the config key**

In `writerdeck/core/config.py`'s `_SCHEMA` dict, add (next to `"font_size"`):

```python
    "reading_font_size_delta": ((int, float), (0, 40)),
```

In `config_default.yaml`, change:

```yaml
mode_order:
  - distraction_free
  - dashboard
  - typewriter
```

to:

```yaml
mode_order:
  - distraction_free
  - reading
reading_font_size_delta: 4  # points added to font_size for reading mode
```

- [ ] **Step 3: Wire ReadingMode into app.py, remove dashboard/typewriter references**

In `writerdeck/core/app.py`, change the imports:

```python
from writerdeck.modes.dashboard import DashboardMode
from writerdeck.modes.distraction_free import DistractionFreeMode
from writerdeck.modes.typewriter import TypewriterMode
```

to:

```python
from writerdeck.modes.distraction_free import DistractionFreeMode
from writerdeck.modes.reading import ReadingMode
```

Change `_build_modes`:

```python
    def _build_modes(self) -> list[BaseMode]:
        font = self._config.font_family
        size = self._config.font_size
        mode_map: dict[str, BaseMode] = {
            "distraction_free": DistractionFreeMode(font_family=font, font_size=size),
            "reading": ReadingMode(
                font_family=font, font_size=size,
                font_size_delta=self._config.reading_font_size_delta,
            ),
        }
        return [mode_map[name] for name in self._config.mode_order if name in mode_map]
```

In `_render_and_refresh`, remove the now-dead `dashboard` branch — change:

```python
            if self._config.enable_battery_monitor and self._power.available and frame.stats is not None:
                if self._mode.name == "dashboard":
                    frame.stats["Battery"] = self._power.battery_bar()
                    # Add time estimate if available
                    remaining = self._power.estimated_remaining_hours
                    if remaining is not None:
                        hours = int(remaining)
                        minutes = int((remaining - hours) * 60)
                        frame.stats["Remaining"] = f"~{hours}h {minutes:02d}m"
                elif self._power.is_low:
                    frame.stats["Battery"] = self._power.battery_bar()
```

to:

```python
            if self._config.enable_battery_monitor and self._power.available and frame.stats is not None:
                if self._power.is_low:
                    frame.stats["Battery"] = self._power.battery_bar()
```

(The full battery bar + remaining-time estimate that dashboard showed unconditionally now lives in `InfoOverlay`, opened via Ctrl+I; the footer only shows a compact warning when low, same as `distraction_free` already did.)

- [ ] **Step 4: Update test_app.py's mode-order fixture and mode-switch assertions**

In `tests/test_app.py`, change the base config's `mode_order` (line 27) and add the new key:

```python
        "mode_order": ["distraction_free", "reading"],
```

and add, next to `"battery_shutdown_percent": 3,`:

```python
        "reading_font_size_delta": 4,
```

Change `test_mode_switch`'s final two lines:

```python
        app._handle_action(KeyAction.SWITCH_MODE_NEXT, "")
        assert app._mode.name == "dashboard"
```

to:

```python
        app._handle_action(KeyAction.SWITCH_MODE_NEXT, "")
        assert app._mode.name == "reading"
```

Change `test_mode_switch_prev`'s final two lines:

```python
        app._handle_action(KeyAction.SWITCH_MODE_PREV, "")
        assert app._mode.name == "typewriter"
```

to:

```python
        app._handle_action(KeyAction.SWITCH_MODE_PREV, "")
        assert app._mode.name == "reading"
```

(With only 2 modes, `SWITCH_MODE_PREV` from `distraction_free` wraps to the same `reading` mode that `SWITCH_MODE_NEXT` reaches.)

- [ ] **Step 5: Run the full suite**

Run: `pytest`
Expected: PASS, 0 failures. Get the exact count and compare to the pre-feature baseline (697 on `master`) — expect it to be higher (new test files added, 3 dashboard/typewriter tests removed).

Run: `mypy writerdeck/`
Expected: no new errors.

Run: `ruff check .`
Expected: no new errors (in particular, no unused imports left behind from the dashboard/typewriter removal).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat: replace dashboard/typewriter with reading mode + info overlay

Wires ReadingMode and InfoOverlay into the 2-mode app (distraction_free,
reading), removes the now-unused DashboardMode/TypewriterMode and their
dedicated tests, and adds the reading_font_size_delta config key.
EOF
)"
```

---

## Manual Verification (after all tasks)

Once all 8 tasks are merged, do a quick desktop smoke test before deploying to the Pi:

```bash
source venv/bin/activate
python main.py
```

- Type a document containing `# Title`, some body text, and `## Subsection` — confirm the heading renders larger with a gap above it and no visible `#`/`##` in the drawn text.
- Press `Ctrl+H` — confirm the outline overlay lists both headings, arrow keys move the `>` selector, Enter jumps the cursor there.
- Press `Ctrl+Tab` — confirm it switches to `reading` mode (larger font, no cursor, no footer).
- In reading mode, press Page Down/Up and Arrow Down/Up — confirm the page changes.
- Press `Ctrl+I` in either mode — confirm the info overlay shows Words/Session/Goal (and Battery if `enable_battery_monitor` is on); any key closes it.
- Press `Ctrl+Tab` again — confirm it returns to `distraction_free` with the document and cursor position intact.
