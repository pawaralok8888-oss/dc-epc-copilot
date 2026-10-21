import json
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font


def build_rows(reqs_path: str, tests_path: str) -> list[list[str]]:
    reqs = json.loads(Path(reqs_path).read_text())
    tests = json.loads(Path(tests_path).read_text())
    by_clause: dict[str, list[dict]] = {}
    for t in tests:
        by_clause.setdefault(t["clause_id"], []).append(t)
    rows = []
    for r in reqs:
        matched = by_clause.get(r["clause_id"], [])
        if not matched:
            rows.append([r["clause_id"], "NO TEST", "not run", ""])
        for t in matched:
            rows.append([r["clause_id"], t["id"], t.get("status", "planned"), ""])
    return rows


def build_matrix_bytes(reqs_path="data/cache/requirements.json",
                       tests_path="data/cache/tests.json") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Traceability"
    ws.append(["Clause", "Test", "Result", "Sign-off"])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in build_rows(reqs_path, tests_path):
        ws.append(row)
    for col in "ABCD":
        ws.column_dimensions[col].width = 22
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


if __name__ == "__main__":
    Path("data/exports").mkdir(parents=True, exist_ok=True)
    Path("data/exports/traceability.xlsx").write_bytes(build_matrix_bytes())
    print("Saved data/exports/traceability.xlsx")
