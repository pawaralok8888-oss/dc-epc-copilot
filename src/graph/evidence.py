"""Evidence nodes for the Q&A (Member A, Day 5).

Turns the two planted findings (UPS rating below spec, late chiller delivery) into
plain-English evidence nodes that qa.py can hand to the model, with real numbers
from deviation.py, impact() and simulate().

    evidence_nodes(G)        -> all evidence nodes
    evidence_for(G, ids)     -> only the nodes that match any of the given IDs

Node format (a dict):
    id     "SUB-002" or "PO-008"                 the ID the answer should cite
    kind   "deviation" or "delay"
    title  short headline
    text   the facts in one paragraph (this is what the model should read)
    links  other IDs this node is about, e.g. ["CL-4.2", "EQ-UPS-02"]
    data   the raw numbers, e.g. {"spec": 500, "declared": 400, "gap": 100, ...}

Run:  python3 src/graph/evidence.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.graph.blast_radius import impact, simulate  # noqa: E402
from src.graph.build_graph import build_graph  # noqa: E402
from src.graph.deviation import late_delivery_alerts, spec_deviation_alerts  # noqa: E402


def _list(ids):
    return ", ".join(ids)


def _tests_sentence(tests):
    return f" It also affects {len(tests)} tests: {_list(tests)}." if tests else ""


def deviation_nodes(G):
    nodes = []
    for alert in spec_deviation_alerts(G):
        sub_id = alert["id"].removeprefix("DEV-")
        sub, eq = G.nodes[sub_id], alert["equipment_id"]
        clause_id = sub["clause_id"]
        clause = G.nodes[clause_id]
        spec, declared, op, unit = clause["value"], sub["rating_value"], clause["operator"], clause["unit"]
        gap = abs(spec - declared)
        imp = impact(G, eq)
        text = (f"{eq} ({G.nodes[eq]['type']}) is flagged because submittal {sub_id} ({sub['model']}) "
                f"declares {declared:g} {sub['unit']}, but clause {clause_id} ({clause['title']}) "
                f"requires {op} {spec:g} {unit}. That is {gap:g} {unit} ({gap / spec:.0%}) below spec. "
                f"It affects {len(imp['tasks'])} schedule tasks: {_list(imp['tasks'])}."
                f"{_tests_sentence(imp['tests'])}")
        nodes.append(dict(id=sub_id, kind="deviation", title=alert["title"], text=text,
                          links=[clause_id, eq],
                          data=dict(spec=spec, declared=declared, operator=op, unit=unit, gap=gap,
                                    tasks=imp["tasks"], tests=imp["tests"])))
    return nodes


def delay_nodes(G):
    nodes = []
    for alert in late_delivery_alerts(G):
        po_id = alert["id"].removeprefix("LATE-")
        po, eq = G.nodes[po_id], alert["equipment_id"]
        task_id = next(t for t in G.successors(po_id) if G.nodes[t]["kind"] == "Task")
        need_by = G.nodes[task_id]["need_by_date"]
        imp = impact(G, po_id)
        sim = simulate(G, po_id, 0)
        late = int(sim["baseline"])
        text = (f"{po_id} ({po['vendor']}) for {eq} ({G.nodes[eq]['type']}) promises delivery on "
                f"{po['promised_date']}, but {task_id} needs it by {need_by}. It is {late} days late. "
                f"The chiller is on the critical path, so the planned handover date {sim['planned_handover']} "
                f"moves to {sim['median_handover']}, which is {late} days later. "
                f"It affects {len(imp['tasks'])} schedule tasks: {_list(imp['tasks'])}."
                f"{_tests_sentence(imp['tests'])}")
        nodes.append(dict(id=po_id, kind="delay", title=alert["title"], text=text,
                          links=[eq, task_id],
                          data=dict(promised=po["promised_date"], need_by=need_by, days_late=late,
                                    planned_handover=sim["planned_handover"],
                                    forecast_handover=sim["median_handover"],
                                    tasks=imp["tasks"], tests=imp["tests"])))
    return nodes


def evidence_nodes(G):
    """All evidence nodes: flagged deviations first, then late deliveries."""
    return deviation_nodes(G) + delay_nodes(G)


def evidence_for(G, ids):
    """Evidence nodes whose own ID or linked IDs match any of `ids` (for the entities in a question)."""
    wanted = set(ids)
    return [n for n in evidence_nodes(G) if n["id"] in wanted or wanted & set(n["links"])]


if __name__ == "__main__":
    G = build_graph()
    for n in evidence_nodes(G):
        print(f"[{n['kind']}] {n['id']}  links={n['links']}\n  {n['text']}\n")
