import json
from collections import defaultdict
from pathlib import Path

from src.ai.extract import load_requirements
from src.ai.generate_tests import draft_tests_batch
from src.ai.rules_engine import validate

OUT = Path("data/cache/tests.json")
PROGRESS = Path("data/cache/tests_progress.json")  # delete after the run is complete
BATCH = 5

done = json.loads(PROGRESS.read_text()) if PROGRESS.exists() else {}


def save_progress():
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(done, indent=2))


reqs = load_requirements()
todo = [r for r in reqs if r.clause_id not in done]
stopped_for_quota = False

for start in range(0, len(todo), BATCH):
    batch = todo[start:start + BATCH]
    try:
        drafts = draft_tests_batch(batch)
    except Exception as e:
        msg = str(e)
        if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
            print("QUOTA EXHAUSTED: stopping. Progress is saved. Run again after the limit resets.")
            stopped_for_quota = True
            break
        print(f"batch starting {batch[0].clause_id}: FAILED ({msg[:160]}); skipped for now")
        continue

    by_clause = {d.get("clause_id"): d for d in drafts}
    for r in batch:
        d = by_clause.get(r.clause_id)
        if d is None:
            print(f"{r.clause_id}: missing from reply; will retry next run")
            continue
        done[r.clause_id] = {
            "clause_id": r.clause_id,
            "level": r.level,
            "tier": r.tier,
            "system": r.system,
            "equipment_id": r.equipment_id,
            "steps": d.get("steps", []),
            "instruments": d.get("instruments", []),
            "acceptance": d.get("acceptance", ""),
            "reason": d.get("reason", ""),
            "status": "planned",
        }
    save_progress()
    print(f"batch {start // BATCH + 1}: saved {len(done)} of {len(reqs)}")

# IDs are assigned here, in code, so they are unique and match the level.
counters = defaultdict(int)
tests = []
for r in reqs:
    d = done.get(r.clause_id)
    if d is None:
        continue
    counters[r.level] += 1
    d["id"] = f"T-{r.level}-{counters[r.level]:03d}"
    tests.append(d)

accepted, rejected = validate(tests)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(accepted, indent=2))

for tid, problems in rejected:
    print("REJECTED", tid, problems)
remaining = len(reqs) - len(done)
print(f"drafted {len(done)}, accepted {len(accepted)}, rejected {len(rejected)}, remaining {remaining}")
if stopped_for_quota:
    print("Run again later to draft the remaining clauses.")
