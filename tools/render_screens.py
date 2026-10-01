#!/usr/bin/env python3
"""Render the README screenshots and demo GIF from the app's own pipeline.

Builds a sample document, renders it through the real modes and renderer (the
same path the NullDriver saves to PNG), and writes to ``docs/media/``:

- ``distraction_free.png`` and ``dashboard.png``: one frame per mode
- ``demo.gif``: finishing a sentence in distraction-free mode, then switching
  to the dashboard

Run from the repo root: ``python tools/render_screens.py``. HOME points at a
temp dir while it runs, so the session ledger never touches the real
``~/.config/writer-deck``.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "media"
FONT, SIZE = "Hack", 14
TITLE = "why-e-ink.md *"

TEXT = """# Why e-ink for writing

A screen that cannot show a notification is a screen that cannot interrupt you. E-ink draws a page and then holds it with no power at all, so the device feels closer to paper than to a laptop.

## The refresh problem

E-ink is slow. A full refresh flashes black and white and takes about a second, which is fine for a page turn and useless for typing. The trick is to redraw only the rows that changed since the last keystroke, so a partial refresh lands in about a third of a second.

## Testing without the hardware

Every frame goes through a display driver. On the Pi it talks to the panel; on a laptop a null driver saves each frame as a PNG, so the whole app can be tested without"""


def main() -> None:
    os.environ["HOME"] = tempfile.mkdtemp()
    sys.path.insert(0, str(ROOT))

    from writerdeck.core.document import Document
    from writerdeck.core.session import Session
    from writerdeck.display.renderer import render
    from writerdeck.modes.dashboard import DashboardMode
    from writerdeck.modes.distraction_free import DistractionFreeMode

    OUT.mkdir(parents=True, exist_ok=True)

    doc = Document(TEXT, TITLE.rstrip(" *"))
    for _ in range(200):
        doc.move_down()
    doc.move_end()

    session = Session(daily_goal=500)
    session.start(0)
    session._start_time -= 23 * 60 + 41  # a believable session timer

    free = DistractionFreeMode(font_family=FONT, font_size=SIZE)
    dash = DashboardMode(font_family=FONT, font_size=SIZE)

    def frame(mode):
        f = mode.render(doc, session)
        f.title = TITLE
        return render(f, FONT, SIZE).convert("L")

    frame(free).save(OUT / "distraction_free.png")
    frame(dash).save(OUT / "dashboard.png")

    frames, durations = [frame(free)], [1200]
    for ch in " a screen attached.":
        doc.insert(ch)
        frames.append(frame(free))
        durations.append(110)
    durations[-1] = 1400
    frames.append(frame(dash))
    durations.append(2600)
    frames[0].save(
        OUT / "demo.gif", save_all=True, append_images=frames[1:],
        duration=durations, loop=0, optimize=True,
    )
    print(f"Wrote {len(frames)}-frame demo.gif and 2 screenshots to {OUT}")


if __name__ == "__main__":
    main()
