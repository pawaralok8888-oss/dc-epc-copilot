"""Blast-radius and delay estimate (Member A, Day 4).

impact(G, node)               -> what is affected if a node changes or slips
simulate(G, po_id, extra_days) -> how many days the handover slips (Monte Carlo)

The schedule model (all dates are calendar days):
  * a task starts when all its prerequisite tasks have finished,
  * a task finishes `duration_days` after it starts,
  * a delivery task cannot finish before its delivery date:
        PLAN     = the date it is needed on site (tasks.csv need_by_date)
        FORECAST = the date its PO promises (pos.csv promised_date)
  * the handover date is when TASK-031 finishes.
So the delay is "forecast handover minus planned handover". The chiller PO is
already 47 days late, so the baseline delay is not zero.

The result is a simulation-based estimate, not a prediction.

Run:  python3 src/graph/blast_radius.py
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import networkx as nx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.graph.build_graph import build_graph, downstream  # noqa: E402

PROJECT_START = date(2027, 1, 4)
HANDOVER_TASK = "TASK-031"


# ---------------------------------------------------------------- impact
def impact(G, node):
    """What is affected if `node` changes or slips (same shape as the app's impact())."""
    d = downstream(G, node) if node in G else set()
    by_kind = lambda kind: sorted(n for n in d if G.nodes[n]["kind"] == kind)
    return dict(all=d, tests=by_kind("Test"), tasks=by_kind("Task"),
                equipment=by_kind("Equipment"), pos=by_kind("PO"), submittals=by_kind("Submittal"))


# ------------------------------------------------------------ schedule model
def _model(G):
    """Read everything the schedule needs from the graph once."""
    tasks = [n for n, d in G.nodes(data=True) if d["kind"] == "Task"]
    order = list(nx.topological_sort(G.subgraph(tasks)))
    preds = {t: [p for p in G.predecessors(t) if G.nodes[p]["kind"] == "Task"] for t in tasks}
    duration = {t: G.nodes[t]["duration_days"] for t in tasks}
    plan, promised, task_of_po = {}, {}, {}
    for t in tasks:
        for p in G.predecessors(t):
            if G.nodes[p]["kind"] == "PO" and G.nodes[t].get("need_by_date"):
                plan[t] = date.fromisoformat(G.nodes[t]["need_by_date"]).toordinal()
                promised[t] = date.fromisoformat(G.nodes[p]["promised_date"]).toordinal()
                task_of_po[p] = t
    return dict(order=order, preds=preds, duration=duration, plan=plan,
                promised=promised, task_of_po=task_of_po)


def _handover(m, delivery_dates):
    """Finish day (as an ordinal) of the handover task for the given delivery dates."""
    finish = {}
    for t in m["order"]:
        start = max((finish[p] for p in m["preds"][t]), default=PROJECT_START.toordinal())
        end = start + m["duration"][t]
        if t in delivery_dates:
            end = max(end, delivery_dates[t])
        finish[t] = end
    return finish[HANDOVER_TASK]


def _forecast_dates(m, po_id=None, extra=0):
    dates = dict(m["promised"])
    if po_id is not None and extra:
        dates[m["task_of_po"][po_id]] += int(round(extra))
    return dates


def planned_handover(G):
    m = _model(G)
    return date.fromordinal(_handover(m, m["plan"]))


def forecast_handover(G, po_id=None, extra_days=0):
    m = _model(G)
    return date.fromordinal(_handover(m, _forecast_dates(m, po_id, extra_days)))


# ------------------------------------------------------------ simulation
def simulate(G, po_id, extra_days, n=1000, buffer_days=7, seed=42):
    """Monte Carlo on one delayed delivery (same keys as the app's simulate() plus extras).

    extra_days = extra delay on top of the date the PO already promises.
    The extra delay is sampled between 0.5x and 1.4x of extra_days (most likely 1x).

    median, p10, p90 : handover delay versus the plan, in days
    prob             : chance that the delay is more than buffer_days
    baseline         : delay with no extra slip (already includes late POs)
    added            : median extra days the slip adds to the handover
    """
    m = _model(G)
    if po_id not in m["task_of_po"]:
        raise ValueError(f"{po_id} has no delivery task in the schedule")
    plan = _handover(m, m["plan"])
    baseline = _handover(m, _forecast_dates(m)) - plan

    if extra_days <= 0:
        delays = np.full(n, float(baseline))
    else:
        rng = np.random.default_rng(seed)
        extras = rng.triangular(extra_days * 0.5, extra_days, extra_days * 1.4, n)
        delays = np.array([_handover(m, _forecast_dates(m, po_id, e)) - plan for e in extras], dtype=float)

    median = float(np.median(delays))
    return dict(
        median=median,
        p10=float(np.percentile(delays, 10)),
        p90=float(np.percentile(delays, 90)),
        prob=float((delays > buffer_days).mean()),
        baseline=float(baseline),
        added=median - baseline,
        planned_handover=date.fromordinal(plan).isoformat(),
        median_handover=(date.fromordinal(plan) + timedelta(days=median)).isoformat(),
    )


if __name__ == "__main__":
    G = build_graph()
    print(f"Planned handover:  {planned_handover(G)}")
    print(f"Forecast handover: {forecast_handover(G)}  (using the PO dates in pos.csv)")
    imp = impact(G, "PO-008")
    print(f"\nPO-008 (late chiller) affects {len(imp['tasks'])} tasks: {', '.join(imp['tasks'])}")
    for extra in (0, 12):
        r = simulate(G, "PO-008", extra)
        print(f"\nChiller +{extra} days: median delay {r['median']:.0f} d "
              f"(p10 {r['p10']:.0f}, p90 {r['p90']:.0f}), adds {r['added']:.0f} d, "
              f"handover about {r['median_handover']}")
    r = simulate(G, "PO-001", 10)
    print(f"\nSwitchgear PO-001 +10 days: adds {r['added']:.0f} d (has schedule float?)")
