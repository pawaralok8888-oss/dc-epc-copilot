"""Tests for the deviation check, late-delivery check and gap detector (Member A, Day 3).

Run from the project root:  python3 -m pytest tests/ -v
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.graph.build_graph import build_graph  # noqa: E402
from src.graph.deviation import (  # noqa: E402
    find_untested_clauses, late_delivery_alerts, load_tested_clause_ids,
    meets, spec_deviation_alerts)

ALERT_KEYS = {"id", "type", "severity", "equipment_id", "title", "detail"}


@pytest.fixture(scope="module")
def G():
    return build_graph()


def test_meets_handles_all_three_operators():
    assert meets(500, ">=", 500) and not meets(400, ">=", 500)
    assert meets(15, "<=", 15) and not meets(16, "<=", 15)
    assert meets(630, "=", 630) and not meets(400, "=", 630)


def test_only_the_ups_submittal_is_below_spec(G):
    # planted error 1: SUB-002 says 400 kW, CL-4.2 requires >= 500 kW
    alerts = spec_deviation_alerts(G)
    assert [a["id"] for a in alerts] == ["DEV-SUB-002"]
    a = alerts[0]
    assert a["equipment_id"] == "EQ-UPS-02" and a["severity"] == "high"
    assert "100 kW" in a["detail"] and "20%" in a["detail"]


def test_only_the_chiller_po_is_late(G):
    # planted error 2: PO-008 promises 2027-06-01, TASK-010 needs it by 2027-04-15
    alerts = late_delivery_alerts(G)
    assert [a["id"] for a in alerts] == ["LATE-PO-008"]
    assert alerts[0]["title"] == "PO-008 delivery is 47 days late"
    assert alerts[0]["equipment_id"] == "EQ-CHL-01"


def test_alerts_have_the_fields_the_app_expects(G):
    for a in spec_deviation_alerts(G) + late_delivery_alerts(G):
        assert set(a) == ALERT_KEYS


def test_gap_detector_lists_clauses_without_tests(G, tmp_path):
    tests_file = tmp_path / "tests.json"
    tests_file.write_text(json.dumps([{"clause_id": "CL-4.1"}, {"clause_id": "CL-4.2"}]))
    gaps = find_untested_clauses(G, load_tested_clause_ids(tests_file))
    assert len(gaps) == 23
    assert "CL-4.1" not in gaps and "CL-4.2" not in gaps
    assert gaps[0] == "CL-4.3" and gaps[-1] == "CL-5.11"   # natural order, 4.10 after 4.9


def test_gap_detector_returns_none_when_tests_file_is_missing(tmp_path):
    assert load_tested_clause_ids(tmp_path / "missing.json") is None
