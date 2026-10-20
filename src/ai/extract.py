import json
from pathlib import Path
from typing import Optional

import pymupdf as fitz  # PyMuPDF
from pydantic import BaseModel

from src.ai.llm import ask_llm_json

CACHE = Path("data/cache/requirements.json")


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
clause_id (like CL-4.2), title, text, value, unit, operator (one of >=, <=, =),
equipment_id (like EQ-UPS-02, or null), system, level (L1 to L5), tier (III or IV).
Use null when a value is absent. Only include clauses that appear in the text.

Spec text:
"""


def read_pdf_chunks(path: str, pages_per_chunk: int = 3):
    doc = fitz.open(path)
    pages = [doc[i].get_text() for i in range(len(doc))]
    for i in range(0, len(pages), pages_per_chunk):
        yield "\n".join(pages[i:i + pages_per_chunk])


def extract_requirements(chunk: str) -> list[Requirement]:
    data = ask_llm_json(PROMPT + chunk, max_tokens=4000)
    return [Requirement(**item) for item in data]


def save_requirements(reqs: list[Requirement], path: Path = CACHE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([r.model_dump() for r in reqs], indent=2))


def load_requirements(path: Path = CACHE) -> list[Requirement]:
    return [Requirement(**x) for x in json.loads(path.read_text())]
