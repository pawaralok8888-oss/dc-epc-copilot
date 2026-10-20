import json
from pathlib import Path
from typing import Optional

import pymupdf as fitz  # PyMuPDF
from pydantic import BaseModel

from src.ai.llm import ask_llm_json

CACHE = Path("data/cache/requirements.json")

UNIT_MAP = {
    "minutes": "min", "minute": "min",
    "seconds": "s", "second": "s",
    "hours": "h", "hour": "h",
}

SYSTEM_MAP = {
    "electrical": "power",
    "mechanical": "cooling",
}


class Requirement(BaseModel):
    clause_id: str
    title: Optional[str] = None
    text: str
    value: Optional[str] = None
    unit: Optional[str] = None
    operator: Optional[str] = None  # one of >=, <=, =
    equipment_id: Optional[str] = None
    system: str
    level: str
    tier: str


PROMPT = """You extract requirements from data-centre EPC specification text.
Return a JSON array. Each item has these keys:
clause_id, title, text, value, unit, operator (one of >=, <=, =),
equipment_id, system, level (L1 to L5), tier (III or IV).

Formats:
- clause_id starts with CL- followed by the clause number (for example CL-4.1).
- equipment_id starts with EQ- (for example EQ-SWG-01), or null.
- system must be exactly one of: power, cooling.
- unit uses short symbols: min for minutes, s for seconds, h for hours, A, kVA, % and so on.
  For a ratio with no unit symbol, such as a coefficient of performance, use its name (COP).
- Use null when a value is absent. Only include clauses that appear in the text.

Level meanings. Choose the stage where the requirement is verified:
- L1 factory and delivery: nameplate, rating, or factory test values
- L2 installation: mounting, clearances, cabling, terminations
- L3 start-up: power-on, commissioning, alarms, settings
- L4 functional performance: performance at load, efficiency, response times
- L5 integrated systems: failover, redundancy, whole-system behaviour

Spec text:
"""


def read_pdf_chunks(path: str, pages_per_chunk: int = 2):
    doc = fitz.open(path)
    pages = [doc[i].get_text() for i in range(len(doc))]
    for i in range(0, len(pages), pages_per_chunk):
        yield "\n".join(pages[i:i + pages_per_chunk])


def _normalize(item: dict) -> dict:
    cid = str(item.get("clause_id", "")).strip()
    if cid and not cid.upper().startswith("CL-"):
        cid = "CL-" + cid
    item["clause_id"] = cid.upper()

    eid = item.get("equipment_id")
    if eid:
        eid = str(eid).strip().upper()
        if not eid.startswith("EQ-"):
            eid = "EQ-" + eid
        item["equipment_id"] = eid

    unit = item.get("unit")
    if unit:
        unit = str(unit).strip()
        item["unit"] = UNIT_MAP.get(unit.lower(), unit)

    system = item.get("system")
    if system:
        item["system"] = SYSTEM_MAP.get(str(system).strip().lower(), str(system).strip().lower())
    return item


def extract_requirements(chunk: str) -> list[Requirement]:
    data = ask_llm_json(PROMPT + chunk, max_tokens=8000, schema=list[Requirement])
    return [Requirement(**_normalize(item)) for item in data]


def save_requirements(reqs: list[Requirement], path: Path = CACHE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([r.model_dump() for r in reqs], indent=2))


def load_requirements(path: Path = CACHE) -> list[Requirement]:
    return [Requirement(**x) for x in json.loads(path.read_text())]
