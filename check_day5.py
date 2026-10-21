"""Day 5 smoke test: opens every tab, approves one item, checks it reached SQLite. Run from the repo root:
    python check_day5.py
Exit code 0 = main is green. Uses streamlit's built-in AppTest (no browser needed). Resets the decision log at the end."""
import sqlite3
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

PAGES = ["Overview", "Insights", "Graph", "Tests", "Photos", "Ask"]
DB = Path("data/approvals.db")
problems = []


def check(at, label):
    if at.exception:
        problems.append(f"{label}: {at.exception[0].value}")
        print("FAIL", label)
    else:
        print("ok  ", label)


at = AppTest.from_file("app.py", default_timeout=90).run()
check(at, "start-up (Overview)")

for p in PAGES[1:]:
    btns = [b for b in at.button if b.key == f"nav_{p}_off"]
    if not btns:
        problems.append(f"{p}: nav button not found")
        continue
    btns[0].click().run()
    check(at, f"tab {p}")

# approve the first item that offers an Approve button on Insights, then on Tests
for page in ("Insights", "Tests"):
    nav = [b for b in at.button if b.key == f"nav_{page}_off"]
    if nav:
        nav[0].click().run()
    appr = [b for b in at.button if (b.key or "").startswith("appr_")]
    if not appr:
        print(f"skip  no Approve button on {page} (no items yet)")
        continue
    appr[0].click().run()
    check(at, f"approve on {page}")

rows = sqlite3.connect(DB).execute("SELECT ts, kind, item_id, decision FROM decisions").fetchall() if DB.exists() else []
print(f"decisions in SQLite: {len(rows)}")
if not rows:
    problems.append("no decision reached data/approvals.db")

# a fresh session must come back with the same approvals (the Day 5 persistence fix)
fresh = AppTest.from_file("app.py", default_timeout=90).run()
check(fresh, "fresh session")
if rows and len(fresh.session_state.decisions) == 0:
    problems.append("approvals were not reloaded from SQLite")

reset = [b for b in fresh.button if b.key == "reset"]
if reset:
    reset[0].click().run()

print("\nGREEN" if not problems else "\nPROBLEMS:\n  " + "\n  ".join(problems))
sys.exit(1 if problems else 0)
