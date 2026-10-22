"""Tests for the Q&A evidence nodes (Member A, Day 5).

Run from the project root:  python3 -m pytest tests/ -v
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.graph.build_graph import build_graph  # noqa: E402
from src.graph.evidence import evidence_for, evidence_nodes  # noqa: E402

NODE_KEYS = {"id", "kind", "title", "text", "links", "data"}


@pytest.fixture(scope="module")
def G():
    return build_graph()


def test_there_are_exactly_the_two_planted_findings(G):
    nodes = evidence_nodes(G)
    assert [(n["id"], n["kind"]) for n in nodes] == [("SUB-002", "deviation"), ("PO-008", "delay")]
    assert all(set(n) == NODE_KEYS for n in nodes)


def test_ups_evidence_has_the_numbers(G):
    n = evidence_for(G, ["EQ-UPS-02"])[0]
    for fact in ("SUB-002", "CL-4.2", "EQ-UPS-02", "400 kW", "500 kW", "100 kW", "20%"):
        assert fact in n["text"]
    assert n["data"]["gap"] == 100


def test_chiller_evidence_has_the_numbers(G):
    n = evidence_for(G, ["EQ-CHL-01"])[0]
    for fact in ("PO-008", "TASK-010", "47 days", "2027-06-22", "2027-08-08", "TASK-015", "TASK-031"):
        assert fact in n["text"]
    assert n["data"]["days_late"] == 47 and len(n["data"]["tasks"]) == 7


def test_evidence_for_matches_on_any_linked_id(G):
    assert [n["id"] for n in evidence_for(G, ["CL-4.2"])] == ["SUB-002"]
    assert [n["id"] for n in evidence_for(G, ["PO-008"])] == ["PO-008"]
    assert [n["id"] for n in evidence_for(G, ["TASK-010"])] == ["PO-008"]
    assert evidence_for(G, ["EQ-PDU-01"]) == []
    assert evidence_for(G, []) == []


def test_evidence_mentions_tests_once_they_are_in_the_graph(tmp_path):
    path = tmp_path / "tests.json"
    path.write_text(json.dumps([{"id": "T-L1-001", "clause_id": "CL-5.1", "equipment_id": "EQ-CHL-01",
                                 "level": "L1", "tier": "III"}]))
    n = evidence_for(build_graph(tests_path=path), ["PO-008"])[0]
    assert "T-L1-001" in n["text"] and n["data"]["tests"] == ["T-L1-001"]
