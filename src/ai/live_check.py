import json
from src.ai.qa import answer, QA_CACHE, UNAVAILABLE, _key, _load_cache

QUESTIONS = ["Why is the UPS flagged?", "What does the chiller delay affect?"]
cache = _load_cache()

for q in QUESTIONS:
    r = answer(q)  # at most 2 model calls
    if "RESOURCE_EXHAUSTED" in r["text"] or "429" in r["text"]:
        print("QUOTA REACHED: stopping. Nothing more was called.")
        break
    if r["text"].startswith(UNAVAILABLE):
        print("UNAVAILABLE, not cached:", q)
        continue
    print("\n" + q)
    print("cites:", r["cites"])
    print(r["text"])
    if r["cites"] and "does not contain" not in r["text"].lower():
        cache[_key(q)] = r
        print("-> cached")
    else:
        print("-> NOT cached (no cites or context missing)")

QA_CACHE.parent.mkdir(parents=True, exist_ok=True)
QA_CACHE.write_text(json.dumps(cache, indent=2))
