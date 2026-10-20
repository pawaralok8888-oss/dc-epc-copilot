import json
import re
from pathlib import Path

from src.ai.llm import ask_llm_json, ask_llm_text

REQS = Path("data/cache/requirements.json")
TESTS = Path("data/cache/tests.json")

CLAUSE_RE = re.compile(r"\bCL-\d+(?:\.\d+)*\b", re.IGNORECASE)
EQUIP_RE = re.compile(r"\bEQ-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", re.IGNORECASE)
CITE_RE = re.compile(r"CL-\d+(?:\.\d+)*")


def load_index():
    reqs = json.loads(REQS.read_text())
    tests = json.loads(TESTS.read_text()) if TESTS.exists() else []
    clauses = {r["clause_id"]: r for r in reqs}
    equipment = {}
    for r in reqs:
        if r.get("equipment_id"):
            equipment.setdefault(r["equipment_id"], []).append(r["clause_id"])
    tests_by_clause = {}
    for t in tests:
        tests_by_clause.setdefault(t["clause_id"], []).append(t)
    return clauses, equipment, tests_by_clause


def find_entities_offline(question, clauses, equipment):
    """No API needed: exact IDs first, then equipment names such as 'SWG-01'."""
    found = set()
    for m in CLAUSE_RE.findall(question):
        if m.upper() in clauses:
            found.add(m.upper())
    for m in EQUIP_RE.findall(question):
        if m.upper() in equipment:
            found.add(m.upper())
    q = question.lower()
    for eid in equipment:
        if eid[3:].lower() in q:
            found.add(eid)
    return found


def pick_entities_llm(question, clauses, equipment):
    """LLM picks the IDs the question is about. Returns None if the call fails."""
    known = sorted(set(clauses) | set(equipment))
    prompt = (
        "Pick the clause IDs and equipment IDs that the question is about.\n"
        f"Allowed IDs: {json.dumps(known)}\n"
        f"Question: {question}\n"
        'Return a JSON object: {"ids": ["..."]}. Use only allowed IDs. '
        "Return an empty list if none apply."
    )
    try:
        data = ask_llm_json(prompt, max_tokens=500)
    except Exception as e:
        print(f"note: entity picking used offline matching instead ({str(e)[:80]})")
        return None
    ids = data.get("ids", []) if isinstance(data, dict) else data
    return {i for i in ids if i in clauses or i in equipment}


def connected(entity_ids, clauses, equipment, tests_by_clause):
    """Stand-in for the graph query: clauses, the equipment they require, and their tests."""
    clause_ids = set()
    for e in entity_ids:
        if e in clauses:
            clause_ids.add(e)
        elif e in equipment:
            clause_ids.update(equipment[e])

    nodes = []
    for cid in sorted(clause_ids):
        r = clauses[cid]
        nodes.append({
            "type": "Clause", "id": cid, "title": r.get("title"), "text": r["text"],
            "value": r.get("value"), "unit": r.get("unit"), "operator": r.get("operator"),
            "equipment_id": r.get("equipment_id"), "level": r["level"], "tier": r["tier"],
        })
        for t in tests_by_clause.get(cid, []):
            nodes.append({
                "type": "Test", "id": t["id"], "clause_id": cid,
                "steps": t.get("steps", []), "acceptance": t.get("acceptance", ""),
            })
    return nodes


def answer(question, use_llm=True, dry_run=False):
    clauses, equipment, tests_by_clause = load_index()

    entities = pick_entities_llm(question, clauses, equipment) if use_llm else None
    if not entities:
        entities = find_entities_offline(question, clauses, equipment)

    nodes = connected(entities, clauses, equipment, tests_by_clause)
    if not nodes:
        return {"answer": "No matching clauses found for that question.",
                "citations": [], "entities": sorted(entities), "context": []}

    prompt = f"""Answer the question using ONLY the context below.
Cite every fact with its clause ID in square brackets, for example [CL-4.1].
If the context does not contain the answer, say so.

Context (graph nodes, JSON):
{json.dumps(nodes, indent=2)}

Question: {question}
"""
    if dry_run:
        return {"answer": "(dry run: no model call)", "citations": [],
                "entities": sorted(entities), "context": nodes, "prompt": prompt}

    text = ask_llm_text(prompt, max_tokens=1000)
    citations = sorted(set(CITE_RE.findall(text)))
    return {"answer": text, "citations": citations,
            "entities": sorted(entities), "context": nodes}
