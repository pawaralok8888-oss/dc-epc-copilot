import json

from src.ai.extract import Requirement
from src.ai.llm import ask_llm_json

PROMPT = """Draft one verification test for EACH requirement below.
Return a JSON array with one object per requirement, in the same order.
Each object has these keys:
clause_id (copy exactly from the requirement),
steps (list of strings),
instruments (list of strings),
acceptance (string),
reason (one sentence on why this test belongs to the requirement's level).
Do not include id, level, tier, or any other keys.

Requirements (JSON list):
"""


def draft_tests_batch(reqs: list[Requirement]) -> list[dict]:
    payload = [r.model_dump() for r in reqs]
    return ask_llm_json(PROMPT + json.dumps(payload), max_tokens=8000)
