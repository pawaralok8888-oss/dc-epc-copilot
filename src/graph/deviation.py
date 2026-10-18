"""Spec deviation check, late-delivery check and gap detector (Member A, Day 3).

Uses the graph from build_graph.py. Writes data/cache/alerts.json, which the
app's alert feed (src/common/alerts.py) reads instead of computing the alerts itself.
Because that file REPLACES the app's fallback, it must hold both kinds of alert.

Alert dict (same as the app expects): id, type, severity, equipment_id, title, detail

Run:  python3 src/graph/deviation.py
"""
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

# allow running this file directly as well as importing it
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.graph.build_graph import DATA, build_graph, downstream  # noqa: E402

ALERTS_PATH = DATA / "cache" / "alerts.json"
TESTS_PATH = DATA / "cache" / "tests.json"   # written by Member B


def meets(value, operator, spec):
    """True if a submittal value satisfies the clause (operator is >=, <= or =)."""
    if operator == ">=":
        return value >= spec
    if operator == "<=":
        return value <= spec
    return math.isclose(value, spec)


def _tasks_affected(G, node_id):
    """Task nodes that are downstream of node_id."""
    return sorted(n for n in downstream(G, node_id) if G.nodes[n]["kind"] == "Task")


def spec_deviation_alerts(G):
    """Compare every submittal rating with its clause value (plain code, no AI)."""
    alerts = []
    for sub_id, sub in G.nodes(data=True):
        if sub["kind"] != "Submittal":
            continue
        clause = G.nodes[sub["clause_id"]]
        spec, value, op = clause["value"], sub["rating_value"], clause["operator"]
        if meets(value, op, spec):
            continue
        gap = abs(spec - value)
        eq = sub["equipment_id"]
        tasks = _tasks_affected(G, eq)
        alerts.append(dict(
            id=f"DEV-{sub_id}", type="spec_deviation", severity="high", equipment_id=eq,
            title=f"{eq} rating below spec",
            detail=(f"{sub['clause_id']} requires {op} {spec:g} {clause['unit']}; {sub_id} says "
                    f"{value:g} {sub['unit']} ({gap:g} {clause['unit']}, {gap / spec:.0%} off). "
                    f"{len(tasks)} schedule tasks depend on this equipment.")))
    return alerts


def late_delivery_alerts(G):
    """Compare each PO's promised date with the date its delivery task needs it."""
    alerts = []
    for po_id, po in G.nodes(data=True):
        if po["kind"] != "PO":
            continue
        for task_id in G.successors(po_id):
            task = G.nodes[task_id]
            if task["kind"] != "Task" or not task.get("need_by_date"):
                continue
            late = (date.fromisoformat(po["promised_date"]) - date.fromisoformat(task["need_by_date"])).days
            if late > 0:
                affected = _tasks_affected(G, po_id)
                alerts.append(dict(
                    id=f"LATE-{po_id}", type="late_delivery", severity="high",
                    equipment_id=po["equipment_id"],
                    title=f"{po_id} delivery is {late} days late",
                    detail=(f"{task_id} needs it by {task['need_by_date']}; {po_id} promises "
                            f"{po['promised_date']}. {len(affected)} tasks could slip by up to {late} days.")))
    return alerts


def _natural_key(clause_id):
    return [int(n) for n in re.findall(r"\d+", clause_id)]


def load_tested_clause_ids(path=TESTS_PATH):
    """Clause IDs that have a generated test, or None if Member B's file does not exist yet."""
    if not Path(path).exists():
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tests = data["tests"] if isinstance(data, dict) and "tests" in data else data
    return {t["clause_id"] for t in tests if t.get("clause_id")}


def find_untested_clauses(G, tested_ids):
    """Gap detector: clauses that have no linked test."""
    clauses = [n for n, d in G.nodes(data=True) if d["kind"] == "Clause"]
    return sorted((c for c in clauses if c not in tested_ids), key=_natural_key)


def all_alerts(G):
    return spec_deviation_alerts(G) + late_delivery_alerts(G)


def write_alerts(G, path=ALERTS_PATH):
    alerts = all_alerts(G)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(alerts, indent=2, ensure_ascii=False), encoding="utf-8")
    return alerts


if __name__ == "__main__":
    G = build_graph()
    alerts = write_alerts(G)
    print(f"Wrote {len(alerts)} alerts to {ALERTS_PATH}\n")
    for a in alerts:
        print(f"[{a['severity']}] {a['id']}: {a['title']}\n    {a['detail']}")
    tested = load_tested_clause_ids()
    if tested is None:
        print("\nGap detector: data/cache/tests.json not found yet (Member B writes it).")
    else:
        gaps = find_untested_clauses(G, tested)
        print(f"\nGap detector: {len(gaps)} clauses have no test: {', '.join(gaps) or 'none'}")
