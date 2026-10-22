"""Tests for adding Member B's generated tests to the graph (Member A, Day 5).

These use their own small tests file, so they do not depend on data/cache/tests.json.
Run from the project root:  python3 -m pytest tests/ -v
"""
import csv
import json
import sys
from pathlib import Path

import networkx as nx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.graph.blast_radius import impact  # noqa: E402
from src.graph.build_graph import DATA, build_graph  # noqa: E402


def _write(tmp_path, tests):
    path = tmp_path / "tests.json"
    path.write_text(json.dumps(tests))
    return path


def _test(tid, clause, eq, level):
    return {"id": tid, "clause_id": clause, "equipment_id": eq, "level": level,
            "tier": "III", "system": "cooling", "steps": [], "instruments": [],
            "acceptance": "", "reason": "", "status": "planned"}


@pytest.fixture()
def G(tmp_path):
    tests = [
        _test("T-L1-001", "CL-5.1", "EQ-CHL-01", "L1"),
        _test("T-L4-001", "CL-5.2", "EQ-CHL-01", "L4"),
        _test("T-L5-001", "CL-5.9", "EQ-CHL-01", "L5"),
        _test("T-L1-099", "CL-9.9", "EQ-CHL-01", "L1"),      # unknown clause, must be skipped
    ]
    return build_graph(tests_path=_write(tmp_path, tests))


def test_without_a_tests_file_there_are_no_test_nodes(tmp_path):
    G = build_graph(tests_path=tmp_path / "missing.json")
    assert not [n for n, d in G.nodes(data=True) if d["kind"] == "Test"]


def test_tests_are_added_and_the_bad_one_is_skipped(G):
    tests = {n for n, d in G.nodes(data=True) if d["kind"] == "Test"}
    assert tests == {"T-L1-001", "T-L4-001", "T-L5-001"}
    assert G.graph["skipped_tests"] == [("T-L1-099", "unknown clause CL-9.9")]
    assert nx.is_directed_acyclic_graph(G)


def test_each_test_is_scheduled_in_the_task_for_its_level(G):
    def scheduled(test):
        return [p for p in G.predecessors(test) if G.nodes[p]["kind"] == "Task"]
    assert scheduled("T-L1-001") == ["TASK-010"]     # chiller delivery
    assert scheduled("T-L4-001") == ["TASK-014"]     # cooling functional test (L4)
    assert scheduled("T-L5-001") == ["TASK-015"]     # integrated systems test (L5)


def test_a_late_chiller_po_affects_the_chiller_tests(G):
    assert impact(G, "PO-008")["tests"] == ["T-L1-001", "T-L4-001", "T-L5-001"]


def test_a_chiller_spec_change_reaches_the_chiller_tests(G):
    assert impact(G, "CL-5.1")["tests"] == ["T-L1-001", "T-L4-001", "T-L5-001"]


def test_a_switchgear_change_only_reaches_the_integrated_test(G):
    # the chiller delivery and cooling test do not wait for the switchgear,
    # but the integrated systems test (L5) waits for both the power and cooling chains
    assert impact(G, "CL-4.1")["tests"] == ["T-L5-001"]
    assert impact(G, "PO-001")["tests"] == ["T-L5-001"]


def test_all_25_clauses_get_scheduled_when_levels_match_the_ground_truth(tmp_path):
    with open(DATA / "spec_ground_truth.csv", encoding="utf-8") as f:
        clauses = list(csv.DictReader(f))
    tests = [_test(f"T-{c['level']}-{i:03d}", c["clause_id"], c["equipment_id"], c["level"])
             for i, c in enumerate(clauses, start=1)]
    G = build_graph(tests_path=_write(tmp_path, tests))
    assert G.graph["skipped_tests"] == []
    unscheduled = [t["id"] for t in tests
                   if not [p for p in G.predecessors(t["id"]) if G.nodes[p]["kind"] == "Task"]]
    assert unscheduled == []
