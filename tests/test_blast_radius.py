"""Tests for the blast-radius and delay estimate (Member A, Day 4).

Run from the project root:  python3 -m pytest tests/ -v
"""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.graph.blast_radius import (  # noqa: E402
    forecast_handover, impact, planned_handover, simulate)
from src.graph.build_graph import build_graph  # noqa: E402

CHILLER_CHAIN = ["TASK-010", "TASK-011", "TASK-012", "TASK-013", "TASK-014", "TASK-015", "TASK-031"]


@pytest.fixture(scope="module")
def G():
    return build_graph()


def test_impact_of_the_late_chiller_po(G):
    imp = impact(G, "PO-008")
    assert imp["tasks"] == CHILLER_CHAIN
    assert isinstance(imp["tests"], list)   # filled once Member B's tests.json is in the graph


def test_impact_of_unknown_node_is_empty(G):
    assert impact(G, "NOPE")["all"] == set()


def test_late_chiller_pushes_handover_back_47_days(G):
    # planned: deliveries on their need-by dates; forecast: deliveries on the PO dates
    assert planned_handover(G) == date(2027, 6, 22)
    assert forecast_handover(G) == date(2027, 8, 8)
    assert (forecast_handover(G) - planned_handover(G)).days == 47


def test_no_extra_delay_gives_the_47_day_baseline(G):
    r = simulate(G, "PO-008", 0)
    assert r["median"] == r["p10"] == r["p90"] == 47
    assert r["added"] == 0


def test_twelve_extra_days_on_the_chiller(G):
    r = simulate(G, "PO-008", 12)
    assert {"median", "p10", "p90", "prob"} <= set(r)       # keys the app uses
    assert r["p10"] <= r["median"] <= r["p90"]
    assert abs(r["added"] - 12) <= 2                         # chiller is on the critical path
    assert r["prob"] == 1.0                                  # always more than a 7 day delay


def test_simulation_is_repeatable(G):
    assert simulate(G, "PO-008", 12) == simulate(G, "PO-008", 12)


def test_delay_on_a_po_with_float_adds_nothing(G):
    # the switchgear is not on the critical path, so +10 days does not move the handover
    assert simulate(G, "PO-001", 10)["added"] == 0


def test_simulate_rejects_something_that_is_not_a_po(G):
    with pytest.raises(ValueError):
        simulate(G, "EQ-UPS-02", 5)
