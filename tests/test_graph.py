"""Tests for the project graph (Member A, Day 2).

Run from the project root:  python3 -m pytest tests/ -v
"""
import sys
from pathlib import Path

import networkx as nx
import pytest

# make "src" importable even if pytest is started from another folder
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.graph.build_graph import build_graph, downstream  # noqa: E402


def tasks_only(G, nodes):
    return {n for n in nodes if G.nodes[n]["kind"] == "Task"}

CHILLER_CHAIN = {"TASK-011", "TASK-012", "TASK-013", "TASK-014", "TASK-015", "TASK-031"}


@pytest.fixture(scope="module")
def G():
    return build_graph()


def test_graph_has_no_loops(G):
    # impact must flow one way only, so the graph has to be a DAG
    assert nx.is_directed_acyclic_graph(G)


def test_chiller_delivery_task_affects_the_cooling_chain(G):
    # if TASK-010 (chiller delivery) slips, exactly these tasks are affected
    assert tasks_only(G, downstream(G, "TASK-010")) == CHILLER_CHAIN


def test_late_chiller_po_affects_delivery_task_and_chain(G):
    # PO-008 is the late chiller PO (planted error 2)
    assert tasks_only(G, downstream(G, "PO-008")) == CHILLER_CHAIN | {"TASK-010"}
