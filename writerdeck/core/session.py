"""Writing session tracker — word count deltas, timer, daily goal."""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import date
from pathlib import Path


class Session:
    def __init__(self, daily_goal: int = 500) -> None:
        self.daily_goal = daily_goal
        self._start_time = time.monotonic()
        self._start_word_count = 0
        self._ledger_path = (
            Path("~/.config/writer-deck/daily.json").expanduser()
        )

    def start(self, current_word_count: int) -> None:
        self._start_time = time.monotonic()
        self._start_word_count = current_word_count

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

    def words_written(self, current_word_count: int) -> int:
        return max(0, current_word_count - self._start_word_count)

    def goal_progress(self, current_word_count: int) -> float:
        today_words = self._today_total() + self.words_written(current_word_count)
        if self.daily_goal <= 0:
            return 1.0
        return min(1.0, today_words / self.daily_goal)

    def goal_bar(self, current_word_count: int, width: int = 10) -> str:
        pct = self.goal_progress(current_word_count)
        filled = int(pct * width)
        return "[" + "\u25a0" * filled + "\u25a1" * (width - filled) + "]"

    # -- Daily ledger persistence ------------------------------------------

    def _load_ledger(self) -> dict:
        if self._ledger_path.exists():
            with open(self._ledger_path) as f:
                return json.load(f)
        return {}

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
        ledger = self._load_ledger()
        return ledger.get(str(date.today()), 0)

    def persist(self, current_word_count: int) -> None:
        words = self.words_written(current_word_count)
        if words <= 0:
            return
        ledger = self._load_ledger()
        key = str(date.today())
        ledger[key] = ledger.get(key, 0) + words
        self._save_ledger(ledger)
        self._start_word_count = current_word_count
