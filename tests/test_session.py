"""Tests for Session — word count tracking, timer, daily goal, ledger persistence."""

from __future__ import annotations

import json
import time
from datetime import date
from unittest.mock import patch

from writerdeck.core.session import Session


class TestWordsWritten:
    def test_zero_when_no_change(self):
        s = Session(daily_goal=500)
        s.start(100)
        assert s.words_written(100) == 0

    def test_positive_delta(self):
        s = Session()
        s.start(10)
        assert s.words_written(25) == 15

    def test_negative_delta_clamped_to_zero(self):
        s = Session()
        s.start(50)
        # Deleting text shouldn't report negative words
        assert s.words_written(30) == 0

    def test_start_resets_baseline(self):
        s = Session()
        s.start(10)
        assert s.words_written(20) == 10
        s.start(20)
        assert s.words_written(20) == 0
        assert s.words_written(25) == 5


class TestElapsedDisplay:
    def test_seconds_only(self):
        s = Session()
        s._start_time = time.monotonic() - 45
        display = s.elapsed_display
        assert display == "0m 45s"

    def test_minutes_and_seconds(self):
        s = Session()
        s._start_time = time.monotonic() - 125  # 2m 5s
        display = s.elapsed_display
        assert display == "2m 05s"

    def test_hours_and_minutes(self):
        s = Session()
        s._start_time = time.monotonic() - 3720  # 1h 2m
        display = s.elapsed_display
        assert display == "1h 02m"

    def test_zero_elapsed(self):
        s = Session()
        # Just started, so elapsed ~0
        display = s.elapsed_display
        assert "0m" in display

    def test_elapsed_seconds_positive(self):
        s = Session()
        s._start_time = time.monotonic() - 10
        assert s.elapsed_seconds >= 9.5


class TestGoalProgress:
    def test_zero_progress(self):
        s = Session(daily_goal=500)
        s.start(0)
        # Mock _today_total to return 0
        with patch.object(s, "_today_total", return_value=0):
            assert s.goal_progress(0) == 0.0

    def test_full_progress(self):
        s = Session(daily_goal=100)
        s.start(0)
        with patch.object(s, "_today_total", return_value=0):
            assert s.goal_progress(100) == 1.0

    def test_capped_at_one(self):
        s = Session(daily_goal=100)
        s.start(0)
        with patch.object(s, "_today_total", return_value=0):
            assert s.goal_progress(200) == 1.0

    def test_partial_progress(self):
        s = Session(daily_goal=100)
        s.start(0)
        with patch.object(s, "_today_total", return_value=0):
            assert abs(s.goal_progress(50) - 0.5) < 0.01

    def test_includes_today_total(self):
        s = Session(daily_goal=100)
        s.start(0)
        with patch.object(s, "_today_total", return_value=40):
            # 40 from today + 10 new = 50/100 = 0.5
            assert abs(s.goal_progress(10) - 0.5) < 0.01

    def test_zero_goal_returns_one(self):
        s = Session(daily_goal=0)
        s.start(0)
        assert s.goal_progress(0) == 1.0

    def test_negative_goal_returns_one(self):
        s = Session(daily_goal=-10)
        s.start(0)
        assert s.goal_progress(0) == 1.0


class TestGoalBar:
    def test_empty_bar(self):
        s = Session(daily_goal=1000)
        s.start(0)
        with patch.object(s, "_today_total", return_value=0):
            bar = s.goal_bar(0, width=5)
            assert bar == "[\u25a1\u25a1\u25a1\u25a1\u25a1]"

    def test_full_bar(self):
        s = Session(daily_goal=100)
        s.start(0)
        with patch.object(s, "_today_total", return_value=0):
            bar = s.goal_bar(100, width=5)
            assert bar == "[\u25a0\u25a0\u25a0\u25a0\u25a0]"

    def test_half_bar(self):
        s = Session(daily_goal=100)
        s.start(0)
        with patch.object(s, "_today_total", return_value=0):
            bar = s.goal_bar(50, width=10)
            assert "\u25a0" in bar
            assert "\u25a1" in bar
            filled = bar.count("\u25a0")
            empty = bar.count("\u25a1")
            assert filled == 5
            assert empty == 5

    def test_custom_width(self):
        s = Session(daily_goal=100)
        s.start(0)
        with patch.object(s, "_today_total", return_value=0):
            bar = s.goal_bar(100, width=3)
            assert bar == "[\u25a0\u25a0\u25a0]"


class TestLedgerPersistence:
    def test_persist_writes_to_ledger(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        s = Session(daily_goal=500)
        s._ledger_path = ledger_path
        s.start(10)
        s.persist(25)  # 15 words written

        assert ledger_path.exists()
        data = json.loads(ledger_path.read_text())
        key = str(date.today())
        assert key in data
        assert data[key] == 15

    def test_persist_accumulates(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        s = Session(daily_goal=500)
        s._ledger_path = ledger_path

        s.start(0)
        s.persist(10)  # +10
        s.persist(20)  # +10 more (start_word_count updated to 10 after first persist)

        data = json.loads(ledger_path.read_text())
        key = str(date.today())
        assert data[key] == 20

    def test_persist_skips_zero_words(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        s = Session()
        s._ledger_path = ledger_path
        s.start(10)
        s.persist(10)  # 0 words written — should be no-op

        assert not ledger_path.exists()

    def test_persist_skips_negative_words(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        s = Session()
        s._ledger_path = ledger_path
        s.start(50)
        s.persist(30)  # negative delta — should be no-op

        assert not ledger_path.exists()

    def test_load_ledger_missing_file(self, tmp_path):
        s = Session()
        s._ledger_path = tmp_path / "nonexistent.json"
        assert s._load_ledger() == {}

    def test_load_ledger_existing_file(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        ledger_path.write_text('{"2026-01-01": 42}')
        s = Session()
        s._ledger_path = ledger_path
        assert s._load_ledger() == {"2026-01-01": 42}

    def test_today_total_reads_today(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        today_key = str(date.today())
        ledger_path.write_text(json.dumps({today_key: 77}))
        s = Session()
        s._ledger_path = ledger_path
        assert s._today_total() == 77

    def test_today_total_missing_date(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        ledger_path.write_text('{"1999-01-01": 42}')
        s = Session()
        s._ledger_path = ledger_path
        assert s._today_total() == 0

    def test_persist_updates_start_word_count(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        s = Session()
        s._ledger_path = ledger_path
        s.start(0)
        s.persist(10)
        # After persist, _start_word_count should be updated
        assert s._start_word_count == 10
        assert s.words_written(10) == 0


class TestDeleteBelowBaseline:
    """BUG-4: words re-typed after dipping below the baseline are counted."""

    def test_words_written_counts_retyped_after_dip(self):
        s = Session(daily_goal=500)
        s.start(100)  # baseline 100
        assert s.words_written(50) == 0  # deleted below baseline -> ratchets to 50
        # Re-type up to 130: authored 130-50 = 80 words, not 130-100 = 30.
        assert s.words_written(130) == 80

    def test_baseline_ratchets_down_on_dip(self):
        s = Session()
        s.start(100)
        s.words_written(50)  # observation ratchets baseline to 50
        assert s._start_word_count == 50

    def test_ledger_reflects_authored_words_after_dip(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        s = Session(daily_goal=500)
        s._ledger_path = ledger_path
        s.start(100)  # baseline 100
        s.words_written(50)  # dip below baseline (edit-and-delete)
        s.persist(130)  # re-typed up to 130

        data = json.loads(ledger_path.read_text())
        key = str(date.today())
        # 80 words actually authored (50 -> 130), not 30 (130 - 100).
        assert data[key] == 80

    def test_persist_advances_baseline_even_when_delta_nonpositive(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        s = Session()
        s._ledger_path = ledger_path
        s.start(100)
        s.persist(60)  # delta <= 0 after ratchet -> no ledger write
        assert not ledger_path.exists()
        # Baseline must be advanced to 60, not left stale at 100, so later
        # words are not swallowed.
        assert s._start_word_count == 60
        s.persist(90)  # +30 authored from the new baseline
        data = json.loads(ledger_path.read_text())
        assert data[str(date.today())] == 30


class _FakeDate:
    """Helper to drive date.today() across a midnight boundary in tests."""

    def __init__(self, sequence):
        self._sequence = list(sequence)
        self._idx = 0

    def today(self):
        d = self._sequence[min(self._idx, len(self._sequence) - 1)]
        self._idx += 1
        return d


class TestMidnightAttribution:
    """BUG-5: words are attributed to the day they were written."""

    def test_words_attributed_to_start_day_after_rollover(self, tmp_path):
        from datetime import date as real_date

        ledger_path = tmp_path / "daily.json"
        day1 = real_date(2026, 7, 10)
        day2 = real_date(2026, 7, 11)

        s = Session(daily_goal=500)
        s._ledger_path = ledger_path
        # Session starts on day1.
        with patch("writerdeck.core.session.date", _FakeDate([day1])):
            s.start(0)
        assert s._baseline_date == day1

        # Persist happens after midnight (now day2), but words were written
        # on day1 and must be credited to day1.
        with patch("writerdeck.core.session.date", _FakeDate([day2, day2])):
            s.persist(40)

        data = json.loads(ledger_path.read_text())
        assert data[str(day1)] == 40
        assert str(day2) not in data
        # Baseline date rolls forward to day2 for the next window.
        assert s._baseline_date == day2

    def test_goal_progress_does_not_double_count_across_midnight(self, tmp_path):
        from datetime import date as real_date

        ledger_path = tmp_path / "daily.json"
        day1 = real_date(2026, 7, 10)
        day2 = real_date(2026, 7, 11)

        s = Session(daily_goal=100)
        s._ledger_path = ledger_path
        with patch("writerdeck.core.session.date", _FakeDate([day1])):
            s.start(0)

        # Credit 40 words to day1.
        with patch("writerdeck.core.session.date", _FakeDate([day1, day1])):
            s.persist(40)

        # Now on day2 with a fresh 30-word delta. goal_progress must reflect
        # day2's ledger (0 so far) + the pending 30 = 0.3, NOT day1's 40 mixed
        # in as well.
        with patch("writerdeck.core.session.date", _FakeDate([day2, day2, day2])):
            progress = s.goal_progress(70)  # baseline is 40 -> delta 30
        assert abs(progress - 0.3) < 0.01

    def test_rollover_detected_by_goal_progress(self, tmp_path):
        from datetime import date as real_date

        ledger_path = tmp_path / "daily.json"
        day1 = real_date(2026, 7, 10)
        day2 = real_date(2026, 7, 11)

        s = Session(daily_goal=500)
        s._ledger_path = ledger_path
        with patch("writerdeck.core.session.date", _FakeDate([day1])):
            s.start(0)
        # 20 words written and persisted on day1 (e.g. an autosave tick).
        with patch("writerdeck.core.session.date", _FakeDate([day1, day1])):
            s.persist(20)
        data = json.loads(ledger_path.read_text())
        assert data[str(day1)] == 20

        # Clock rolls to day2 with no further typing yet (current count still
        # 20). The first observation flushes the pending window to day1 (0 new
        # words) and opens a day2 window. goal_progress reflects day2's ledger
        # (0), NOT day1's 20 -> no double-count.
        with patch("writerdeck.core.session.date", _FakeDate([day2, day2, day2])):
            progress = s.goal_progress(20)
        data = json.loads(ledger_path.read_text())
        assert data[str(day1)] == 20  # day1 total unchanged
        assert str(day2) not in data  # nothing written on day2 yet
        assert progress == 0.0  # day2 progress excludes day1's total

        # Now type 10 words on day2; they credit toward day2's goal only.
        with patch("writerdeck.core.session.date", _FakeDate([day2, day2, day2])):
            progress = s.goal_progress(30)
        assert progress == 10 / 500


class TestLedgerCache:
    """Ledger reads are cached with a 30s TTL to avoid disk I/O per render."""

    def test_load_ledger_cached_within_ttl(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        ledger_path.write_text('{"2026-01-01": 42}')
        s = Session()
        s._ledger_path = ledger_path
        # First call reads from disk and populates cache
        result1 = s._load_ledger()
        assert result1 == {"2026-01-01": 42}
        assert s._ledger_cache is not None
        assert s._ledger_cache_time > 0
        # Second call within TTL should return cached value without reading disk
        with patch("builtins.open", side_effect=OSError("should not read disk")):
            result2 = s._load_ledger()
        assert result2 == {"2026-01-01": 42}

    def test_save_ledger_updates_cache(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        s = Session()
        s._ledger_path = ledger_path
        s._save_ledger({"2026-01-01": 100})
        assert s._ledger_cache == {"2026-01-01": 100}
        assert s._ledger_cache_time > 0


class TestCorruptLedger:
    """A corrupt/unreadable daily.json must degrade to an empty ledger, not
    crash the dashboard render path (goal_bar -> goal_progress -> _load_ledger).
    """

    def test_load_ledger_invalid_json_returns_empty(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        ledger_path.write_text("{not valid json")  # malformed
        s = Session()
        s._ledger_path = ledger_path
        assert s._load_ledger() == {}

    def test_load_ledger_truncated_json_returns_empty(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        ledger_path.write_text('{"2026-01-01": 4')  # truncated mid-value
        s = Session()
        s._ledger_path = ledger_path
        assert s._load_ledger() == {}

    def test_load_ledger_empty_file_returns_empty(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        ledger_path.write_text("")  # empty -> JSONDecodeError
        s = Session()
        s._ledger_path = ledger_path
        assert s._load_ledger() == {}

    def test_goal_progress_survives_corrupt_ledger(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        ledger_path.write_text("garbage!!!")
        s = Session(daily_goal=100)
        s._ledger_path = ledger_path
        s.start(0)
        # Corrupt ledger treated as empty -> only pending delta counts.
        assert abs(s.goal_progress(50) - 0.5) < 0.01

    def test_goal_bar_survives_corrupt_ledger(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        ledger_path.write_text("\x00\x01\x02not-json")
        s = Session(daily_goal=100)
        s._ledger_path = ledger_path
        s.start(0)
        bar = s.goal_bar(0, width=5)
        assert bar == "[□□□□□]"

    def test_today_total_survives_corrupt_ledger(self, tmp_path):
        ledger_path = tmp_path / "daily.json"
        ledger_path.write_text("[]corrupt")
        s = Session()
        s._ledger_path = ledger_path
        assert s._today_total() == 0
