"""Tests for writerdeck.utils.perf — PerfMetrics timing and gauge system."""

import time

import pytest

from writerdeck.utils.perf import PerfMetrics


@pytest.fixture(autouse=True)
def fresh_metrics():
    """Each test gets a clean PerfMetrics instance."""
    m = PerfMetrics()
    yield m


def test_disabled_time_is_noop(fresh_metrics):
    m = fresh_metrics
    m.enabled = False
    with m.time("render_frame"):
        pass
    assert len(m._frames) == 0
    assert m._current == {}


def test_enabled_time_records_elapsed(fresh_metrics):
    m = fresh_metrics
    m.enabled = True
    with m.time("render_frame"):
        time.sleep(0.01)
    assert "render_frame" in m._current
    assert m._current["render_frame"] >= 0.01


def test_multiple_time_calls_accumulate(fresh_metrics):
    m = fresh_metrics
    m.enabled = True
    with m.time("render_frame"):
        time.sleep(0.005)
    with m.time("render_frame"):
        time.sleep(0.005)
    assert m._current["render_frame"] >= 0.01


def test_total_frame_commits_to_deque(fresh_metrics):
    m = fresh_metrics
    m.enabled = True
    with m.time("total_frame"), m.time("render_frame"):
        pass
    assert len(m._frames) == 1
    assert "total_frame" in m._frames[0]
    assert "render_frame" in m._frames[0]
    # current frame dict is cleared after commit
    assert m._current == {}


def test_deque_bounded_to_120(fresh_metrics):
    m = fresh_metrics
    m.enabled = True
    for _ in range(121):
        with m.time("total_frame"):
            pass
    assert len(m._frames) == 120


def test_log_summary_empty_does_not_crash(fresh_metrics, caplog):
    import logging
    m = fresh_metrics
    m.enabled = True
    with caplog.at_level(logging.INFO, logger="writerdeck.perf"):
        m.log_summary()
    assert any("no frames" in r.message for r in caplog.records)


def test_record_gauge_stores_latest(fresh_metrics):
    m = fresh_metrics
    m.enabled = True
    m.record_gauge("doc_lines", 10)
    assert m._gauges["doc_lines"] == 10
    m.record_gauge("doc_lines", 20)
    assert m._gauges["doc_lines"] == 20


def test_record_gauge_disabled_noop(fresh_metrics):
    m = fresh_metrics
    m.enabled = False
    m.record_gauge("doc_lines", 42)
    assert m._gauges == {}


def test_reset_clears_all_data(fresh_metrics):
    m = fresh_metrics
    m.enabled = True
    with m.time("total_frame"), m.time("render_frame"):
        pass
    m.record_gauge("doc_lines", 5)
    m.reset()
    assert len(m._frames) == 0
    assert m._current == {}
    assert m._gauges == {}


def test_time_propagates_exception_and_clears_current(fresh_metrics):
    m = fresh_metrics
    m.enabled = True
    with pytest.raises(ValueError), m.time("total_frame"):
        raise ValueError("boom")
    assert m._current == {}
