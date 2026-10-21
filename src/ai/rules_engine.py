import json
from pathlib import Path

RULES = json.loads(Path("rules/level_rules.json").read_text())


def _same_scope(a: dict, b: dict) -> bool:
    if a.get("equipment_id") and b.get("equipment_id"):
        return a["equipment_id"] == b["equipment_id"]
    return a.get("system") == b.get("system")


def check_test(test: dict, all_tests: list[dict]) -> list[str]:
    rule = RULES["levels"].get(test["level"])
    if rule is None:
        return [f"{test['id']}: unknown level {test['level']}"]
    problems = []
    for prereq in rule["prerequisites"]:
        has_prereq = any(
            t["level"] == prereq and _same_scope(test, t)
            for t in all_tests
        )
        if not has_prereq:
            problems.append(f"{test['id']}: no {prereq} test for the same equipment or system")
    return problems


def validate(tests: list[dict]):
    accepted, rejected = [], []
    for t in tests:
        problems = check_test(t, tests)
        if problems:
            rejected.append((t["id"], problems))
        else:
            accepted.append(t)
    return accepted, rejected
