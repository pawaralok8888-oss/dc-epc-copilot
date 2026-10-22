"""Tests for the Day 6 benchmark helpers. They need no graph, data or API."""
from src.graph.benchmark import (build_rows, fmt_duration, fmt_hours, fmt_speedup,
                                 render_markdown, time_it)

ESTIMATES = [
    {"key": "a", "task": "Task A", "manual_hours_low": 2, "manual_hours_high": 4, "basis": "x"},
    {"key": "b", "task": "Task B", "manual_hours_low": 1, "manual_hours_high": 1, "basis": "y"},
]


def test_fmt_duration_units():
    assert fmt_duration(0.0001) == "under 1 ms"
    assert fmt_duration(0.25) == "250 ms"
    assert fmt_duration(2.5) == "2.5 s"
    assert fmt_duration(90) == "1.5 min"
    assert fmt_duration(7200) == "2.0 h"


def test_fmt_hours_small_values_in_minutes():
    assert fmt_hours(0.5) == "30 min"
    assert fmt_hours(16) == "16.0 h"


def test_time_it_returns_stats_and_runs_function():
    calls = []
    result = time_it(lambda: calls.append(1), repeats=5)
    assert len(calls) == 6  # 1 warm-up + 5 timed
    assert result["runs"] == 5
    assert result["min_s"] <= result["median_s"] <= result["max_s"]


def test_rows_use_midpoint_and_skip_missing_tasks():
    rows = build_rows(ESTIMATES, {"a": {"median_s": 1.0, "note": "n"}})
    assert [r["key"] for r in rows] == ["a"]  # b has no timing, so it is left out
    assert rows[0]["manual_mid_h"] == 3
    assert abs(rows[0]["hours_saved"] - (3 - 1 / 3600)) < 1e-9
    assert round(rows[0]["speedup"]) == 10800


def test_extra_live_ai_time_is_added():
    rows = build_rows(ESTIMATES, {"a": {"median_s": 1.0, "extra_s": 59.0, "note": ""}})
    assert rows[0]["system_s"] == 60.0


def test_markdown_labels_manual_times_as_estimates():
    rows = build_rows(ESTIMATES, {"a": {"median_s": 1.0, "note": "n"}})
    text = render_markdown(rows, repeats=20)
    assert "our estimate" in text.lower()
    assert "Task A" in text


def test_speedup_is_capped_for_believability():
    assert fmt_speedup(120) == "about 120x"
    assert fmt_speedup(5_000_000) == "over 10,000x"
