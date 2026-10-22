"""Day 4 (Member A): blast radius, delay through the schedule, Monte Carlo estimate.

Built against docs/schema.md from the plan (tasks.csv also has need_by_date, used as the earliest start):
  node types   Clause, Equipment, PO, Submittal, Test, Task, Photo   (stored in node attribute TYPE_ATTR)
  PO           promised_date, lead_time_days
  Task         duration_days, depends_on (list of task ids, or "TASK-001;TASK-002" from a CSV)
  links        Clause REQUIRES Equipment, Equipment ORDERED_VIA PO, Equipment SUBMITTED_AS Submittal,
               Clause VERIFIED_BY Test, Test SCHEDULED_AS Task, PO GATES Task, Task DEPENDS_ON Task
The DEPENDS_ON direction does not matter: task order is rebuilt from each task's depends_on field.
"""
import datetime as dt
import re

import networkx as nx
import numpy as np

TYPE_ATTR = "type"  # change if your loader names the node-type attribute differently
LABEL = "simulation-based estimate"  # always show this next to the number in the UI
DOC_TYPES = ("PO", "Submittal")


def _kind(G, n):
    return G.nodes[n].get(TYPE_ATTR)


def _day(x):
    if isinstance(x, str):
        x = dt.date.fromisoformat(x[:10])
    return x.toordinal() if hasattr(x, "toordinal") else float(x)


def _ids(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return []
    return [s for s in re.split(r"[;,|\s]+", v) if s] if isinstance(v, str) else list(v)


def _flow(G):
    """Copy of G where every Task->Task edge is rebuilt as prerequisite -> dependent from depends_on."""
    F = nx.DiGraph()
    F.add_nodes_from(G.nodes(data=True))
    F.add_edges_from((a, b) for a, b in G.edges if not (_kind(G, a) == "Task" and _kind(G, b) == "Task"))
    for t in G:
        if _kind(G, t) == "Task":
            F.add_edges_from((p, t) for p in _ids(G.nodes[t].get("depends_on")) if p in G)
    return F


def downstream(G, node):
    """Everything affected if `node` changes (follows the flow of the project, not the arrow names)."""
    F = _flow(G)
    return nx.descendants(F, node) if node in F else set()


def _prep(G, project_start=None):
    F = _flow(G)
    order = [n for n in nx.topological_sort(F) if _kind(F, n) == "Task"]
    preds = {t: [p for p in F.predecessors(t) if _kind(F, p) == "Task"] for t in order}
    gates = {t: [p for p in F.predecessors(t) if _kind(F, p) == "PO"] for t in order}
    dates = [_day(G.nodes[n]["promised_date"]) for n in G if _kind(G, n) == "PO" and G.nodes[n].get("promised_date")]
    start0 = _day(project_start) if project_start else (min(dates) if dates else 0)
    need = {t: _day(G.nodes[t]["need_by_date"]) for t in order if G.nodes[t].get("need_by_date")}
    return F, order, preds, gates, start0, need


def schedule(G, shift=None, prep=None, project_start=None):
    """Forward pass. `shift` = {po_id: days late}. A task starts at the latest of its need-by date (or the project start),
    its prerequisites' finish and the promised dates (plus shift) of the POs that gate it."""
    shift = shift or {}
    F, order, preds, gates, start0, need = prep or _prep(G, project_start)
    start, finish = {}, {}
    for t in order:
        s = need.get(t, start0)
        for p in preds[t]:
            s = max(s, finish[p])
        for po in gates[t]:
            s = max(s, _day(G.nodes[po]["promised_date"]) + shift.get(po, 0))
        start[t], finish[t] = s, s + float(G.nodes[t].get("duration_days") or 0)
    return start, finish


def project_finish(G, shift=None, prep=None):
    _, finish = schedule(G, shift, prep)
    return max(finish.values()) if finish else 0


def blast_radius(G, node, slip_days=0, project_start=None):
    """What a change to `node` touches, and (if it is a PO slipping by slip_days) how far each task moves."""
    F = _flow(G)
    d = nx.descendants(F, node) if node in F else set()
    kind = lambda *ts: sorted(n for n in d if _kind(G, n) in ts)
    prep = _prep(G, project_start)
    _, base = schedule(G, prep=prep)
    _, scen = schedule(G, {node: slip_days}, prep)
    return dict(changed=node, tests=kind("Test"), tasks=kind("Task"), documents=kind(*DOC_TYPES), all=sorted(d),
                task_slips={t: round(scen[t] - base[t], 1) for t in base if scen[t] > base[t]},
                delay_days=round(max(scen.values()) - max(base.values()), 1) if base else 0.0)


def simulate_delay(G, node, slip_days, runs=1000, buffer_days=5, seed=42, project_start=None):
    """Monte Carlo: the late PO slips by triangular(0.5x, 1x, 1.4x) of slip_days. Returns median and range."""
    if slip_days <= 0 or node not in G:
        return dict(median=0.0, p10=0.0, p90=0.0, prob_miss=0.0, runs=0, label=LABEL)
    rng = np.random.default_rng(seed)
    prep = _prep(G, project_start)
    base = project_finish(G, prep=prep)
    d = np.array([project_finish(G, {node: rng.triangular(slip_days * 0.5, slip_days, slip_days * 1.4)}, prep) - base
                  for _ in range(runs)])
    return dict(median=float(np.median(d)), p10=float(np.percentile(d, 10)), p90=float(np.percentile(d, 90)),
                prob_miss=float((d > buffer_days).mean()), runs=runs, label=LABEL)


if __name__ == "__main__":  # self-check on a toy project that follows the schema
    g = nx.DiGraph()
    g.add_node("PO-023", type="PO", promised_date="2027-02-10", lead_time_days=60)
    g.add_node("T-L4-021", type="Test")
    g.add_node("TASK-010", type="Task", duration_days=14, depends_on="")             # unrelated, sets the start
    g.add_node("TASK-012", type="Task", duration_days=10, depends_on="TASK-010")
    g.add_node("TASK-031", type="Task", duration_days=5, depends_on="TASK-012;TASK-010")
    g.add_edges_from([("PO-023", "TASK-012"), ("T-L4-021", "TASK-031"), ("TASK-012", "TASK-010")])  # DEPENDS_ON drawn backwards
    print(blast_radius(g, "PO-023", 12, project_start="2027-02-01"))
    print(simulate_delay(g, "PO-023", 12, project_start="2027-02-01"))
