import json
from src.ai.qa import QA_CACHE, UNAVAILABLE, _key, _load_cache, answer

QUESTIONS = [
    "Why is the UPS flagged?",
    "What does the chiller delay affect?",
    "Which clauses have no test?",
]

cache = _load_cache()
for q in QUESTIONS:
    result = answer(q)
    if result["text"].startswith(UNAVAILABLE):
        print("NOT cached (service unavailable):", q)
        continue
    cache[_key(q)] = result
    print("cached:", q)

QA_CACHE.parent.mkdir(parents=True, exist_ok=True)
QA_CACHE.write_text(json.dumps(cache, indent=2))
