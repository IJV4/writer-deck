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
