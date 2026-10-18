"""Reality Delta: nameplate photo vs approved submittal.

Image in -> fields + confidence out (Gemini), then a plain-Python comparison
with a tolerance. The LLM only reads the plate; it never decides pass/fail.

Run from repo root:
    python -m src.vision.reality_delta              # all photos, uses cache when present
    python -m src.vision.reality_delta --refresh    # re-call Gemini for every photo
    python -m src.vision.reality_delta --selftest   # offline logic check, no API
Results are cached in data/cache/photo_results.json so the demo needs no live calls.
"""
import argparse, csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PHOTOS = ROOT / "data" / "photos"
SUBMITTALS = ROOT / "data" / "submittals.csv"
CACHE = ROOT / "data" / "cache" / "photo_results.json"

REL_TOL = 0.01        # rating may differ by 1 % before it counts as a mismatch
MIN_CONF = 0.80       # below this the photo goes to human review


# ---------- data ----------
def load_submittals(path=SUBMITTALS):
    by_eq = {}
    for r in csv.DictReader(open(path, newline="")):
        r["rating_value"] = float(r["rating_value"])
        by_eq.setdefault(r["equipment_id"], []).append(r)
    return by_eq


def load_manifest(path=PHOTOS / "ground_truth.json"):
    """Photo list: id, equipment_id, file. (ground truth fields are ignored here.)"""
    return [{k: p[k] for k in ("id", "equipment_id", "file")} for p in json.load(open(path))]


# ---------- vision ----------
def extract(image_path):
    """Call Gemini on one image. Returns dict(model, rating_value, unit, tag, confidence)."""
    from src.vision.gemini_test import read_nameplate   # lazy: logic below works offline
    return read_nameplate(str(image_path)).model_dump()


# ---------- comparison (plain Python) ----------
def _norm(s):
    return "".join(ch for ch in str(s or "").upper() if ch.isalnum())


def pick_submittal(subs, unit):
    """Equipment can have several submittals (e.g. BRK-05: 630 A and 50 kA).
    Choose the one whose unit matches the nameplate; None if no unit matches."""
    for s in subs:
        if _norm(s["unit"]) == _norm(unit):
            return s
    return None


def compare(extracted, equipment_id, subs_by_eq, rel_tol=REL_TOL, min_conf=MIN_CONF):
    """Return a result dict with status MATCH | MISMATCH | REVIEW and reasons."""
    subs = subs_by_eq.get(equipment_id, [])
    res = {"equipment_id": equipment_id, "extracted": extracted, "submittal_id": None,
           "expected": None, "status": None, "reasons": []}
    if not subs:
        res.update(status="REVIEW", reasons=["no submittal on file for this equipment"])
        return res

    conf = extracted.get("confidence") or 0.0
    model, rating, unit, tag = (extracted.get(k) for k in ("model", "rating_value", "unit", "tag"))
    missing = [k for k, v in (("model", model), ("rating", rating), ("unit", unit), ("tag", tag)) if v in (None, "")]
    if conf < min_conf or missing:
        why = [f"confidence {conf:.2f} < {min_conf}"] if conf < min_conf else []
        if missing:
            why.append("unreadable: " + ", ".join(missing))
        res.update(status="REVIEW", reasons=why + ["send to human review"])
        return res

    sub = pick_submittal(subs, unit)
    if sub is None:
        res.update(status="REVIEW", reasons=[f"unit '{unit}' not in submittals {[s['unit'] for s in subs]}"])
        return res

    res["submittal_id"] = sub["submittal_id"]
    res["expected"] = {"model": sub["model"], "rating_value": sub["rating_value"], "unit": sub["unit"],
                       "tag": equipment_id.replace("EQ-", "")}
    problems = []
    exp_rating = sub["rating_value"]
    if abs(rating - exp_rating) > rel_tol * abs(exp_rating):
        problems.append(f"rating {rating:g} {unit} vs submittal {exp_rating:g} {sub['unit']}")
    if _norm(model) != _norm(sub["model"]):
        problems.append(f"model {model} vs submittal {sub['model']}")
    if _norm(tag) != _norm(res["expected"]["tag"]):
        problems.append(f"tag {tag} vs expected {res['expected']['tag']}")
    res.update(status="MISMATCH" if problems else "MATCH", reasons=problems)
    return res


# ---------- runner ----------
def run_all(refresh=False):
    subs = load_submittals()
    cache = {} if refresh or not CACHE.exists() else json.loads(CACHE.read_text())
    out = []
    for p in load_manifest():
        if p["id"] not in cache:
            try:
                cache[p["id"]] = extract(PHOTOS / p["file"])
            except Exception as e:      # API error, quota, etc: do not crash the run
                cache[p["id"]] = {"model": None, "rating_value": None, "unit": None, "tag": None,
                                  "confidence": 0.0, "error": f"{type(e).__name__}: {e}"[:200]}
        r = compare(cache[p["id"]], p["equipment_id"], subs)
        r.update(photo_id=p["id"], file=p["file"])
        out.append(r)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=2))
    return out


def print_table(results):
    print(f"{'PHOTO':6} {'EQUIPMENT':11} {'READ':26} {'CONF':5} {'STATUS':9} REASON")
    for r in results:
        e = r["extracted"]
        read = f"{e.get('model')} {e.get('rating_value')}{e.get('unit') or ''}"
        print(f"{r['photo_id']:6} {r['equipment_id']:11} {read:26} {(e.get('confidence') or 0):<5.2f} "
              f"{r['status']:9} {'; '.join(r['reasons'])}")
    flagged = [r["photo_id"] for r in results if r["status"] != "MATCH"]
    print(f"\nNeed attention: {', '.join(flagged) or 'none'}")


# ---------- offline self-test ----------
def selftest():
    subs = load_submittals()
    truth = json.load(open(PHOTOS / "ground_truth.json"))
    ok = True
    for t in truth:
        ext = {"model": t["model"], "rating_value": float(t["rating_value"]), "unit": t["unit"],
               "tag": t["tag"], "confidence": 0.3 if t["variant"] == "blurry" else 0.95}
        if t["variant"] == "blurry":
            ext.update(model=None, rating_value=None)
        want = {"ok": "MATCH", "wrong": "MISMATCH", "blurry": "REVIEW"}[t["variant"]]
        got = compare(ext, t["equipment_id"], subs)["status"]
        ok &= got == want
        print(f"{t['id']} {t['equipment_id']:11} expected {want:8} got {got:8} {'OK' if got == want else 'FAIL'}")
    # tolerance edge cases
    base = {"model": "AMPC-SWG-4000", "rating_value": 4000.0, "unit": "A", "tag": "SWG-01", "confidence": 0.9}
    near = compare({**base, "rating_value": 4030.0}, "EQ-SWG-01", subs)["status"]   # +0.75 % inside tol
    far = compare({**base, "rating_value": 4100.0}, "EQ-SWG-01", subs)["status"]    # +2.5 % outside tol
    wrong_tag = compare({**base, "tag": "SWG-02"}, "EQ-SWG-01", subs)["status"]
    for name, got, want in (("within tolerance", near, "MATCH"), ("outside tolerance", far, "MISMATCH"),
                            ("wrong tag", wrong_tag, "MISMATCH")):
        ok &= got == want
        print(f"edge: {name:18} expected {want:8} got {got:8} {'OK' if got == want else 'FAIL'}")
    print("\nSELFTEST", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore cache and call Gemini again")
    ap.add_argument("--selftest", action="store_true", help="offline logic check, no API calls")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    print_table(run_all(refresh=a.refresh))
