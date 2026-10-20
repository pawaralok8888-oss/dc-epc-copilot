from src.ai.extract import Requirement
from src.ai.llm import ask_llm_json

PROMPT = """Draft one verification test for this requirement. Return a JSON object with keys:
id (format T-L{level}-NNN), clause_id, level, tier, steps (list of strings),
instruments (list), acceptance (string), reason (why this level), status ("planned").

Requirement: """


def draft_test(req: Requirement) -> dict:
    return ask_llm_json(PROMPT + req.model_dump_json(), max_tokens=1500)
