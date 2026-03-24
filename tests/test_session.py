"""Tests for Session — word count tracking, timer, daily goal, ledger persistence."""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
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
