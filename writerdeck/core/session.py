"""Writing session tracker — word count deltas, timer, daily goal."""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import date
from pathlib import Path


class Session:
    def __init__(self, daily_goal: int = 500) -> None:  # noqa: D107
        self.daily_goal = daily_goal
        self._start_time = time.monotonic()
        self._start_word_count = 0
        # BUG-5: attribute words to the day the session's word-count baseline
        # was captured, not to date.today() at persist time. Otherwise a
        # session left open across midnight credits pre-midnight words to the
        # new day. The baseline date rolls forward on each persist (see below).
        self._baseline_date = date.today()
        self._ledger_path = (
            Path("~/.config/writer-deck/daily.json").expanduser()
        )
        self._ledger_cache: dict | None = None
        self._ledger_cache_time: float = 0.0

    def start(self, current_word_count: int) -> None:
        self._start_time = time.monotonic()
        self._start_word_count = current_word_count
        self._baseline_date = date.today()

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._start_time

    @property
    def elapsed_display(self) -> str:
        s = int(self.elapsed_seconds)
        hours, remainder = divmod(s, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes:02d}m"
        return f"{minutes}m {secs:02d}s"

    def _roll_over_if_needed(self, current_word_count: int) -> None:
        # BUG-5: when the wall clock advances past the day the current window
        # opened on, carry the window forward to today. We deliberately do NOT
        # credit the pending delta to the old day here: an implicit read (a
        # render/goal_progress tick) after midnight is dominated by words being
        # typed *now*, so they belong to today. Only an explicit persist() (an
        # autosave/save) credits the pending delta to the window's day. This is
        # the "persist on rollover" model from the plan, applied at the seam
        # where it's unambiguous. Net effect: goal_progress()/_today_total()
        # always reflect the current wall-clock day, never mixing yesterday's
        # ledger total with today's typing.
        today = date.today()
        if today != self._baseline_date:
            self._baseline_date = today

    def words_written(self, current_word_count: int) -> int:
        # BUG-4: count against a baseline that ratchets *down* to the lowest
        # word count seen since the last start()/persist(). If the user deletes
        # below the baseline (e.g. 100 -> 50) and then re-types (50 -> 130), the
        # re-typed words are counted (130 - 50 = 80), rather than being lost by
        # a naive max(0, current - 100) = 30. The baseline only moves down here;
        # persist() advances it up to the current count after crediting words.
        if current_word_count < self._start_word_count:
            self._start_word_count = current_word_count
        return current_word_count - self._start_word_count

    def goal_progress(self, current_word_count: int) -> float:
        self._roll_over_if_needed(current_word_count)
        today_words = self._today_total() + self.words_written(current_word_count)
        if self.daily_goal <= 0:
            return 1.0
        return min(1.0, today_words / self.daily_goal)

    def goal_bar(self, current_word_count: int, width: int = 10) -> str:
        pct = self.goal_progress(current_word_count)
        filled = int(pct * width)
        return "[" + "■" * filled + "□" * (width - filled) + "]"

    # -- Daily ledger persistence ------------------------------------------

    def _load_ledger(self) -> dict:
        now = time.monotonic()
        if self._ledger_cache is not None and now - self._ledger_cache_time < 30.0:
            return self._ledger_cache
        if self._ledger_path.exists():
            with open(self._ledger_path) as f:
                result = json.load(f)
        else:
            result = {}
        self._ledger_cache = result
        self._ledger_cache_time = now
        return result

    def _save_ledger(self, ledger: dict) -> None:
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(ledger, indent=2)
        fd = -1
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self._ledger_path.parent), suffix=".tmp",
            )
            os.write(fd, content.encode("utf-8"))
            os.fsync(fd)
            os.close(fd)
            fd = -1
            os.rename(tmp_path, str(self._ledger_path))
            self._ledger_cache = ledger
            self._ledger_cache_time = time.monotonic()
        except Exception:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise

    def _today_total(self) -> int:
        # BUG-5: read against the session's baseline date (which tracks the day
        # the current uncredited delta belongs to), not date.today(). This keeps
        # goal_progress()'s "today total + pending delta" arithmetic on a single
        # consistent day even when the wall clock has rolled past midnight.
        ledger = self._load_ledger()
        return ledger.get(str(self._baseline_date), 0)

    def _flush(self, current_word_count: int, day: date) -> None:
        # Credit words authored in the current window to `day`, then advance the
        # up-baseline to the current count. BUG-4: advance the baseline even
        # when the delta is <= 0, so a dip that reset the baseline downward does
        # not leave a stale high baseline that would swallow later words.
        words = self.words_written(current_word_count)
        if words > 0:
            ledger = self._load_ledger()
            key = str(day)
            ledger[key] = ledger.get(key, 0) + words
            self._save_ledger(ledger)
        self._start_word_count = current_word_count

    def persist(self, current_word_count: int) -> None:
        # BUG-5: an explicit persist credits the pending delta to the day the
        # current window opened on (_baseline_date). If a session opened before
        # midnight and the first save lands after midnight, the pre-midnight
        # words are still credited to the pre-midnight day. After crediting,
        # open a fresh window dated today so the next batch lands correctly.
        self._flush(current_word_count, self._baseline_date)
        self._baseline_date = date.today()
