"""Alert feed for the app.
Uses data/cache/alerts.json if the graph module wrote one (list of alert dicts);
otherwise computes the planted deviations straight from the CSVs so the app always works.
Photo alerts always come from the cached Reality Delta results.
Alert dict: id, type, severity (high|medium|low), equipment_id, title, detail
"""
import csv, json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


def _rows(name):
    return list(csv.DictReader(open(DATA / name, newline="")))


def spec_deviation_alerts():
    clauses = {c["clause_id"]: c for c in _rows("spec_ground_truth.csv")}
    out = []
    for s in _rows("submittals.csv"):
        c = clauses.get(s["clause_id"])
        if not c:
            continue
        spec, val, op = float(c["value"]), float(s["rating_value"]), c["operator"]
        ok = val >= spec if op == ">=" else val <= spec if op == "<=" else val == spec
        if not ok:
            gap = abs(spec - val)
            out.append(dict(id=f"DEV-{s['submittal_id']}", type="spec_deviation", severity="high",
                            equipment_id=s["equipment_id"],
                            title=f"{s['equipment_id']} rating below spec",
                            detail=f"{c['clause_id']} requires {op} {spec:g} {c['unit']}; {s['submittal_id']} says "
                                   f"{val:g} {s['unit']} ({gap:g} {c['unit']}, {gap / spec:.0%} off)."))
    return out


def late_delivery_alerts():
    pos = {p["po_id"]: p for p in _rows("pos.csv")}
    out = []
    for t in _rows("tasks.csv"):
        po = pos.get(t["linked_id"])
        if po and t["need_by_date"]:
            late = (date.fromisoformat(po["promised_date"]) - date.fromisoformat(t["need_by_date"])).days
            if late > 0:
                out.append(dict(id=f"LATE-{po['po_id']}", type="late_delivery", severity="high",
                                equipment_id=po["equipment_id"],
                                title=f"{po['po_id']} delivery is {late} days late",
                                detail=f"{t['task_id']} needs it by {t['need_by_date']}; {po['po_id']} promises "
                                       f"{po['promised_date']}."))
    return out


def photo_alerts():
    from src.vision.reality_delta import cached_results
    out = []
    for r in cached_results():
        if r["status"] == "MISMATCH":
            out.append(dict(id=f"PHOTO-{r['photo_id']}", type="reality_delta", severity="high",
                            equipment_id=r["equipment_id"],
                            title=f"Photo {r['photo_id']} does not match approved design ({r['equipment_id']})",
                            detail="; ".join(r["reasons"])))
        elif r["status"] == "REVIEW":
            out.append(dict(id=f"PHOTO-{r['photo_id']}", type="reality_delta", severity="low",
                            equipment_id=r["equipment_id"],
                            title=f"Photo {r['photo_id']} needs human review ({r['equipment_id']})",
                            detail="; ".join(r["reasons"])))
    return out


def load_alerts():  
    shared = DATA / "cache" / "alerts.json"
    base = json.loads(shared.read_text()) if shared.exists() else spec_deviation_alerts() + late_delivery_alerts()
    return sorted(base + photo_alerts(), key=lambda a: (SEV_ORDER.get(a["severity"], 9), a["id"]))