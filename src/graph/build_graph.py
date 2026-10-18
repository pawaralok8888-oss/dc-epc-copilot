"""Build the project knowledge graph from the CSV files (Member A, Day 2).

Edges point in the direction of IMPACT: if the source changes or slips,
the target is affected. So the graph is a directed acyclic graph (DAG):

    Clause    -> Equipment      (REQUIRES: the clause sets requirements for it)
    Equipment -> PO             (ORDERED_VIA)
    Equipment -> Submittal      (SUBMITTED_AS)
    PO        -> Task           (GATES: the delivery task waits for the PO)
    Task      -> Task           (PRECEDES: a prerequisite points to the task that
                                 depends on it, the OPPOSITE of the depends_on column)

Submittal.clause_id is kept as a node attribute, not an edge, because an edge
back to the clause would create a loop.

Run:  python3 src/graph/build_graph.py
Test: python3 -m pytest tests/ -v
"""
import csv
from pathlib import Path

import networkx as nx

DATA = Path(__file__).resolve().parents[2] / "data"

# columns that should be numbers instead of text
FLOAT_FIELDS = {"value", "rating_value"}
INT_FIELDS = {"duration_days", "lead_time_days"}


def read_csv(name):
    """Read data/<name> and return a list of row dictionaries."""
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _clean(row):
    """Turn numeric columns into numbers and empty strings into None."""
    out = {}
    for key, val in row.items():
        if val == "":
            out[key] = None
        elif key in FLOAT_FIELDS:
            out[key] = float(val)
        elif key in INT_FIELDS:
            out[key] = int(val)
        else:
            out[key] = val
    return out


def _add_node(G, node_id, kind, label, row):
    attrs = _clean(row)
    G.add_node(node_id, kind=kind, label=f"{node_id} {label}", **attrs)


def _add_edge(G, source, target, relation):
    """Add an edge, but fail loudly if either end does not exist."""
    for n in (source, target):
        if n not in G:
            raise ValueError(f"Cannot link {source} -> {target} ({relation}): {n} is not in the graph")
    G.add_edge(source, target, relation=relation)


def build_graph():
    """Read all CSV files and return the project graph (a networkx DiGraph)."""
    G = nx.DiGraph()

    clauses = read_csv("spec_ground_truth.csv")
    equipment = read_csv("equipment.csv")
    pos = read_csv("pos.csv")
    submittals = read_csv("submittals.csv")
    tasks = read_csv("tasks.csv")

    # 1. nodes (all nodes first, so edges can be checked afterwards)
    for r in clauses:
        _add_node(G, r["clause_id"], "Clause", r["title"], r)
    for r in equipment:
        _add_node(G, r["equipment_id"], "Equipment", r["type"], r)
    for r in pos:
        _add_node(G, r["po_id"], "PO", r["vendor"], r)
    for r in submittals:
        _add_node(G, r["submittal_id"], "Submittal", r["model"], r)
    for r in tasks:
        _add_node(G, r["task_id"], "Task", r["name"], r)

    # 2. edges
    for r in clauses:
        _add_edge(G, r["clause_id"], r["equipment_id"], "REQUIRES")
    for r in pos:
        _add_edge(G, r["equipment_id"], r["po_id"], "ORDERED_VIA")
    for r in submittals:
        _add_edge(G, r["equipment_id"], r["submittal_id"], "SUBMITTED_AS")
    for r in tasks:
        if r["linked_id"]:
            _add_edge(G, r["linked_id"], r["task_id"], "GATES")
        for prerequisite in r["depends_on"].split(";"):
            if prerequisite:
                _add_edge(G, prerequisite, r["task_id"], "PRECEDES")

    return G


def downstream(G, node_id):
    """Return the set of everything affected if node_id changes or slips."""
    if node_id not in G:
        raise KeyError(f"{node_id} is not in the graph")
    return nx.descendants(G, node_id)


def print_chain(G, clause_id):
    """Print what one clause connects to: equipment, POs, submittals, and the tasks it affects."""
    print(f"\n{G.nodes[clause_id]['label']}")
    for eq in G.successors(clause_id):
        print(f"  -> {G.nodes[eq]['label']}")
        for nxt in G.successors(eq):
            print(f"       -> {G.nodes[nxt]['label']}")
    tasks = sorted(n for n in downstream(G, clause_id) if G.nodes[n]["kind"] == "Task")
    print(f"  Tasks affected ({len(tasks)}): {', '.join(tasks)}")


if __name__ == "__main__":
    G = build_graph()
    print(f"Nodes: {G.number_of_nodes()}")
    print(f"Edges: {G.number_of_edges()}")
    print(f"No loops (DAG): {nx.is_directed_acyclic_graph(G)}")
    print_chain(G, "CL-4.2")
    print(f"\nTASK-010 downstream: {sorted(downstream(G, 'TASK-010'))}")
