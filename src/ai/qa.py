import json
import re
from pathlib import Path

from src.ai.llm import ask_llm_json, ask_llm_text

REQS = Path("data/cache/requirements.json")
TESTS = Path("data/cache/tests.json")
QA_CACHE = Path("data/cache/qa_cache.json")

CLAUSE_RE = re.compile(r"\bCL-\d+(?:\.\d+)*\b", re.IGNORECASE)
EQUIP_RE = re.compile(r"\bEQ-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", re.IGNORECASE)
CITE_RE = re.compile(r"\b(?:CL-\d+(?:\.\d+)*|EQ-[A-Z0-9]+(?:-[A-Z0-9]+)*|T-L\d-\d{3}|SUB-\d+|PO-\d+|TASK-\d+|PH-\d+)\b")
UNAVAILABLE = "The answer service is unavailable right now"


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
    except Exception:
        return None
    ids = data.get("ids", []) if isinstance(data, dict) else data
    return {i for i in ids if i in clauses or i in equipment}


def connected(entity_ids, clauses, equipment, tests_by_clause):
    """Stand-in for the graph query. Replace with Member A's graph query when available."""
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


def clauses_without_tests():
    clauses, _, tests_by_clause = load_index()
    missing = [cid for cid in sorted(clauses) if not tests_by_clause.get(cid)]
    text = (f"{len(missing)} clauses have no accepted test: {', '.join(missing)}. "
            "Their drafted tests were rejected by the level rules, because the "
            "lower-level test for the same equipment or system is missing.")
    return {"text": text, "cites": missing,
            "evidence": [{"type": "Clause", "id": c} for c in missing]}


def _key(question):
    return " ".join(question.lower().split())


def _load_cache():
    return json.loads(QA_CACHE.read_text()) if QA_CACHE.exists() else {}


def answer(question):
    """App contract: returns dict(text, cites, evidence). Never raises."""
    try:
        if "no test" in question.lower():
            return clauses_without_tests()
        cache = _load_cache()
        if _key(question) in cache:
            return cache[_key(question)]

        clauses, equipment, tests_by_clause = load_index()
        entities = (pick_entities_llm(question, clauses, equipment)
                    or find_entities_offline(question, clauses, equipment))
        nodes = connected(entities, clauses, equipment, tests_by_clause)
        if not nodes:
            return {"text": "No matching clauses or equipment found for that question.",
                    "cites": [], "evidence": []}

        prompt = f"""Answer the question using ONLY the context below.
Cite every fact with its ID in square brackets, for example [CL-4.1].
If the context does not contain the answer, say so.

Context (graph nodes, JSON):
{json.dumps(nodes, indent=2)}

Question: {question}
"""
        text = ask_llm_text(prompt, max_tokens=1000)
        known = {n["id"] for n in nodes} | {n["equipment_id"] for n in nodes if n.get("equipment_id")}
        cites = sorted({m for m in CITE_RE.findall(text) if m in known})
        return {"text": text, "cites": cites, "evidence": nodes}
    except Exception as e:
        return {"text": f"{UNAVAILABLE} ({str(e)[:120]}). Try again later.",
                "cites": [], "evidence": []}
