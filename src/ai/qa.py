import json
import re
from functools import lru_cache
from pathlib import Path

from src.ai.llm import ask_llm_json, ask_llm_text

REQS = Path("data/cache/requirements.json")
TESTS = Path("data/cache/tests.json")
QA_CACHE = Path("data/cache/qa_cache.json")

CLAUSE_RE = re.compile(r"\bCL-\d+(?:\.\d+)*\b", re.IGNORECASE)
EQUIP_RE = re.compile(r"\bEQ-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", re.IGNORECASE)
CITE_RE = re.compile(r"\b(?:CL-\d+(?:\.\d+)*|EQ-[A-Z0-9]+(?:-[A-Z0-9]+)*|T-L\d-\d{3}|SUB-\d+|PO-\d+|TASK-\d+|PH-\d+)\b")
UNAVAILABLE = "The answer service is unavailable right now"
STOP = {"the", "is", "are", "was", "what", "why", "does", "which", "how", "this", "that",
        "and", "for", "with", "from", "affect", "affects", "any", "all", "its", "not"}


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


@lru_cache(maxsize=1)
def _graph():
    from src.graph.build_graph import build_graph
    return build_graph()


def _evidence_nodes():
    try:
        from src.graph.evidence import evidence_nodes
        return evidence_nodes(_graph())
    except Exception:
        return []


def _evidence_for(ids):
    if not ids:
        return []
    try:
        from src.graph.evidence import evidence_for
        return evidence_for(_graph(), sorted(ids))
    except Exception:
        return []


def _words(text):
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2 and w not in STOP}


def evidence_keyword_hits(question, ev_nodes):
    qwords = _words(question)
    hits = set()
    for n in ev_nodes:
        if qwords & _words(str(n.get("title", "")) + " " + str(n.get("text", ""))):
            hits.add(n["id"])
    return hits


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


def pick_entities_llm(question, clauses, equipment, extra_ids=()):
    allowed = set(clauses) | set(equipment) | set(extra_ids)
    prompt = (
        "Pick the clause IDs, equipment IDs and evidence IDs that the question is about.\n"
        f"Allowed IDs: {json.dumps(sorted(allowed))}\n"
        f"Question: {question}\n"
        'Return a JSON object: {"ids": ["..."]}. Use only allowed IDs. '
        "Return an empty list if none apply."
    )
    try:
        data = ask_llm_json(prompt, max_tokens=500)
    except Exception:
        return None
    ids = data.get("ids", []) if isinstance(data, dict) else data
    return {i for i in ids if i in allowed}


def connected(entity_ids, clauses, equipment, tests_by_clause):
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


def answer(question, use_llm=True, dry_run=False):
    """App contract: returns dict(text, cites, evidence). Never raises."""
    try:
        if "no test" in question.lower():
            return clauses_without_tests()
        cache = _load_cache()
        if _key(question) in cache:
            return cache[_key(question)]

        clauses, equipment, tests_by_clause = load_index()
        ev_all = _evidence_nodes()
        ev_ids = {n["id"] for n in ev_all}

        entities = None
        if use_llm:
            entities = pick_entities_llm(question, clauses, equipment, ev_ids)
        if not entities:
            entities = find_entities_offline(question, clauses, equipment)
        entities = set(entities) | evidence_keyword_hits(question, ev_all)

        nodes = connected(entities, clauses, equipment, tests_by_clause)
        seen = {n["id"] for n in nodes}
        for ev in _evidence_for(entities):
            if ev["id"] not in seen:
                nodes.append(ev)
                seen.add(ev["id"])
        if not nodes:
            return {"text": "No matching clauses, equipment or evidence found for that question.",
                    "cites": [], "evidence": []}

        prompt = f"""Answer the question using ONLY the context below.
Cite every fact with its ID in square brackets, for example [CL-4.1] or [PO-008].
If the context does not contain the answer, say so.

Context (graph nodes, JSON):
{json.dumps(nodes, indent=2, default=str)}

Question: {question}
"""
        if dry_run:
            return {"text": "(dry run: no model call)", "cites": [],
                    "evidence": nodes, "entities": sorted(entities), "prompt": prompt}

        text = ask_llm_text(prompt, max_tokens=1000)
        known = {n["id"] for n in nodes} | {n["equipment_id"] for n in nodes if n.get("equipment_id")}
        cites = sorted({m for m in CITE_RE.findall(text) if m in known})
        return {"text": text, "cites": cites, "evidence": nodes}
    except Exception as e:
        return {"text": f"{UNAVAILABLE} ({str(e)[:120]}). Try again later.",
                "cites": [], "evidence": []}
