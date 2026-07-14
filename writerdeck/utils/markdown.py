"""Markdown line-level parser for styled rendering."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class StyledSpan:
    text: str
    bold: bool = False
    italic: bool = False


@dataclass
class StyledLine:
    text: str
    font_size: int = 14
    bold: bool = False
    indent: int = 0
    spans: list[StyledSpan] = field(default_factory=list)


def parse_line(raw: str, base_family: str, base_size: int) -> StyledLine:
    """Parse a single line for Markdown-style formatting.

    Supports:
    - # / ## / ### headings (larger font)
    - - list items (indent)
    - **bold** and *italic* inline spans
    """
    stripped = raw

    # Headings
    if stripped.startswith("### "):
        text = stripped[4:]
        return StyledLine(
            text=text,
            font_size=base_size + 2,
            bold=True,
            spans=_parse_inline(text),
        )
    if stripped.startswith("## "):
        text = stripped[3:]
        return StyledLine(
            text=text,
            font_size=base_size + 4,
            bold=True,
            spans=_parse_inline(text),
        )
    if stripped.startswith("# "):
        text = stripped[2:]
        return StyledLine(
            text=text,
            font_size=base_size + 8,
            bold=True,
            spans=_parse_inline(text),
        )

    # List items
    if stripped.startswith("- "):
        text = stripped[2:]
        return StyledLine(
            text=text,
            font_size=base_size,
            indent=16,
            spans=_parse_inline(text),
        )

    return StyledLine(
        text=raw,
        font_size=base_size,
        spans=_parse_inline(raw),
    )


def _parse_inline(text: str) -> list[StyledSpan]:
    """Parse inline **bold** and *italic* spans."""
    spans: list[StyledSpan] = []
    # Pattern: **bold**, *italic*, plain text, or a lone `*`. The final
    # alternative also matches a solitary asterisk so an unpaired `*` (e.g.
    # "a * b") is preserved as literal text rather than silently dropped.
    pattern = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*|([^*]+|\*)")
    for m in pattern.finditer(text):
        if m.group(1):
            spans.append(StyledSpan(text=m.group(1), bold=True))
        elif m.group(2):
            spans.append(StyledSpan(text=m.group(2), italic=True))
        else:
            spans.append(StyledSpan(text=m.group(3)))
    if not spans:
        spans.append(StyledSpan(text=text))
    return spans
