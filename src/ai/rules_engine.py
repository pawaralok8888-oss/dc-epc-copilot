import json
from pathlib import Path

RULES = json.loads(Path("rules/level_rules.json").read_text())


def check_test(test: dict, all_tests: list[dict]) -> list[str]:
    rule = RULES["levels"].get(test["level"])
    if rule is None:
        return [f"{test['id']}: unknown level {test['level']}"]
    problems = []
    for prereq in rule["prerequisites"]:
        has_prereq = any(
            t["clause_id"] == test["clause_id"] and t["level"] == prereq
            for t in all_tests
        )
        if not has_prereq:
            problems.append(f"{test['id']}: no {prereq} test for {test['clause_id']}")
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
