"""DC Copilot - Streamlit dashboard (Member C).

Runs on built-in demo data so it works with no API calls. Each loader checks
data/cache/*.json first, so Member A/B output replaces the demo data automatically.
Run:  streamlit run app.py
Needs: streamlit pandas numpy networkx openpyxl pillow  (python-docx optional)
"""
import datetime as dt
import base64
import io
import re
import json
import sqlite3
from collections import Counter
from pathlib import Path

import csv

import networkx as nx
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFilter

from src.vision.checklists import l2_checklist  # Day 3: L2 installation checklists

st.set_page_config(page_title="DC Copilot", page_icon="🏗️", layout="wide")

ROOT = Path(__file__).parent
CACHE, PHOTO_DIR, DB = ROOT / "data" / "cache", ROOT / "data" / "photos", ROOT / "data" / "approvals.db"
PAGES = ["Overview", "Insights", "Graph", "Tests", "Photos", "Ask"]
LEVELS = ["L1", "L2", "L3", "L4", "L5"]
FOCUS = "PO-023"                      # default changed node (chiller PO)
BASE_FINISH = dt.date(2027, 3, 12)    # planned handover (demo)
BUFFER_DAYS = 5                       # schedule buffer used for "chance of missing target"
CONF_MIN = 0.60                       # below this a photo reading goes to human review
SLACK = {"PO-023": 3}                 # days of float on the delivery (demo)
def load(name, default):
    f = CACHE / name
    return json.loads(f.read_text()) if f.exists() else default


# ----------------------------------------------------------------------------- demo data
# Test tuple: id, level, tier, clause, equipment, system, status, steps, instruments, acceptance, reason
_T = [
    ("T-L1-001", "L1", "III", "CL-4.2", "EQ-UPS-02", "Power", "Approved", "Read nameplate; compare with submittal SUB-009; record variance", "Camera", "Nameplate rating equals 500 kVA", "L1 covers document and nameplate checks before installation."),
    ("T-L3-009", "L3", "III", "CL-5.1", "EQ-BRK-02", "Power", "Draft", "Check trip settings; run primary injection; record trip times", "Primary injection set", "Trips within curve +/-10%", "L3 covers start-up tests of protective devices."),
    ("T-L4-017", "L4", "III", "CL-4.2", "EQ-UPS-02", "Power", "Draft", "Connect load bank; step load 25-100%; record output voltage", "Load bank, power analyser", "Output voltage within +/-1% at 100% load", "Recommended at L4 because this needs the UPS under real load."),
    ("T-L4-018", "L4", "III", "CL-4.2", "EQ-UPS-02", "Power", "Draft", "Simulate mains failure at full load; time the transfer; record runtime", "Load bank, scope", "Zero-break transfer; runtime of at least 10 min", "L4 covers failover under load."),
    ("T-L4-021", "L4", "III", "CL-6.1", "EQ-CH-01", "Cooling", "Draft", "Run chiller at design load; log supply temperature; check flow", "Flow meter, data logger", "Supply temperature within 1 C of setpoint", "L4 needs the chiller under real heat load."),
    ("T-L4-022", "L4", "III", "CL-6.1", "EQ-CH-01", "Cooling", "Approved", "Pressure-test circuit; inspect joints; record decay", "Pressure gauge", "No pressure decay over 30 min", "L4 includes leakage checks before integrated runs."),
    ("T-L4-030", "L4", "IV", "CL-4.2", "EQ-UPS-02", "Power", "Draft", "Fail one UPS module; verify load stays up; restore module", "Load bank", "No load interruption", "Tier IV adds fault-tolerance tests."),
    ("T-L5-002", "L5", "III", "CL-6.1", "EQ-CH-01", "Both", "Draft", "Run integrated failure scenario across power and cooling", "Full load bank, BMS", "Site stays within thermal limits", "L5 is the full integrated test."),
]
_K = ("id", "level", "tier", "clause", "equipment", "system", "status", "steps", "instruments", "acceptance", "reason")
TESTS = load("tests.json", [dict(zip(_K, t)) for t in _T])

NODES = {  # id: (type, label, system)
    "CL-4.2": ("Clause", "UPS capacity", "Power"), "CL-5.1": ("Clause", "Breaker rating", "Power"),
    "CL-6.1": ("Clause", "Cooling capacity", "Cooling"), "CL-7.3": ("Clause", "Fire interlock", "Both"),
    "CL-8.1": ("Clause", "Generator autostart", "Power"),
    "EQ-UPS-02": ("Equipment", "UPS-02", "Power"), "EQ-BRK-02": ("Equipment", "Breaker-02", "Power"),
    "EQ-CH-01": ("Equipment", "Chiller-01", "Cooling"),
    "SUB-009": ("PO / Submittal", "UPS submittal", "Power"), "SUB-012": ("PO / Submittal", "Breaker submittal", "Power"),
    "PO-023": ("PO / Submittal", "Chiller PO", "Cooling"),
    "TASK-012": ("Task", "Chiller install", "Cooling"), "TASK-018": ("Task", "UPS install", "Power"),
    "TASK-024": ("Task", "Breaker testing", "Power"), "TASK-031": ("Task", "Commissioning", "Both"),
}
for _t in TESTS:
    NODES[_t["id"]] = ("Test", _t["id"], _t.get("system", "Both"))
EDGES = [("CL-4.2", "EQ-UPS-02"), ("CL-5.1", "EQ-BRK-02"), ("CL-6.1", "EQ-CH-01"),
         ("EQ-UPS-02", "SUB-009"), ("EQ-BRK-02", "SUB-012"), ("EQ-CH-01", "PO-023"),
         ("SUB-009", "T-L4-017"), ("SUB-009", "T-L4-018"), ("SUB-009", "T-L4-030"), ("SUB-012", "T-L3-009"),
         ("PO-023", "T-L4-021"), ("PO-023", "T-L4-022"), ("PO-023", "TASK-012"),
         ("T-L4-017", "T-L5-002"), ("T-L4-021", "T-L5-002"), ("T-L5-002", "TASK-031"),
         ("T-L4-017", "TASK-018"), ("T-L4-018", "TASK-031"), ("T-L4-022", "TASK-031"),
         ("TASK-012", "TASK-031"), ("T-L3-009", "TASK-024")]
G = nx.DiGraph()
G.add_nodes_from(NODES)
G.add_edges_from(e for e in EDGES if e[0] in NODES and e[1] in NODES)
G.add_edges_from((t["clause"], t["id"]) for t in TESTS if t["clause"] in NODES)  # VERIFIED_BY

INSIGHTS = load("insights.json", [
    dict(id="INS-UPS", sev="Critical", system="Power", node="SUB-009", vendor="Voltix", days=9,
         title="UPS-02 rated 400 kVA, spec CL-4.2 requires 500 kVA", ids=["CL-4.2", "SUB-009", "EQ-UPS-02"],
         what="Submittal SUB-009 lists UPS-02 at 400 kVA, but clause CL-4.2 requires 500 kVA.",
         why="May lead to insufficient capacity at peak load and put availability and SLA compliance at risk.",
         cause="Vendor supplied a lower-rated model than specified.",
         action="Request a 500 kVA unit, or get a formal deviation approval with a risk assessment."),
    dict(id="INS-CH", sev="Warning", system="Cooling", node="PO-023", vendor="CoolFlow", days=None,
         title="Chiller PO-023 delivery delayed", ids=["CL-6.1", "PO-023", "EQ-CH-01"],
         what="Delivery of PO-023 has slipped by {delay} days (what-if value from the sidebar).",
         why="Delays cooling commissioning and every test and task that depends on the chiller.",
         cause="Not determinable from the available documents.",
         action="Expedite with the vendor or request a plan from an alternate supplier."),
    dict(id="INS-PH", sev="Info", system="Power", node=None, vendor="Voltix", days=3,
         title="Photo PH-08 needs human review", ids=["CL-4.2", "SUB-009", "EQ-UPS-02"],
         what="The nameplate image is blurry, so the rating could not be read with confidence.",
         why="A non-compliant unit or missing nameplate data could stay hidden.",
         cause="Poor photo quality or lighting.",
         action="Request a clearer photo or verify on site."),
])
_P = dict(
    PH_03=dict(id="PH-03", equipment="EQ-BRK-02", location="Level 4 - Electrical Room", blur=False,
               expected=dict(Model="Masterpact NW16", Rating="630 A", Tag="EQ-BRK-02"),
               read=dict(Model="Masterpact NW16", Rating="400 A", Tag="EQ-BRK-02"),
               conf=dict(Model=0.96, Rating=0.92, Tag=0.98),
               why="Breaker rating is below the approved value and can affect load capacity and safety compliance.",
               action="Verify with the site team, check the breaker model and update the submittal if required."),
    PH_08=dict(id="PH-08", equipment="EQ-UPS-02", location="Level 4 - UPS Room", blur=True,
               expected=dict(Model="Galaxy VX", Rating="500 kVA", Tag="EQ-UPS-02"),
               read=dict(Model="Galaxy VX", Rating="500 kVA", Tag="EQ-UPS-02"),
               conf=dict(Model=0.81, Rating=0.42, Tag=0.77),
               why="The rating cannot be confirmed, so a mismatch could be hidden.",
               action="Send to human review and request a clearer photo."),
)
PHOTOS = {p["id"]: p for p in load("photos.json", list(_P.values()))}
SUGGESTED = ["Why is the UPS flagged?", "What does the chiller delay affect?", "Which clauses have no test?"]


# ----------------------------------------------------------------------------- logic (plain code, no LLM)
def impact(node):
    d = nx.descendants(G, node) if node in G else set()
    return dict(all=d, tests=[n for n in d if NODES[n][0] == "Test"], tasks=[n for n in d if NODES[n][0] == "Task"])


def simulate(node, delay, n=1000):
    """Monte Carlo on one delayed delivery. Simulation-based estimate, not a prediction."""
    if delay <= 0:
        return dict(median=0.0, p10=0.0, p90=0.0, prob=0.0)
    x = np.random.default_rng(42).triangular(delay * 0.5, delay, delay * 1.4, n) - SLACK.get(node, 0)
    x = np.maximum(0, x)
    return dict(median=float(np.median(x)), p10=float(np.percentile(x, 10)),
                p90=float(np.percentile(x, 90)), prob=float((x > BUFFER_DAYS).mean()))


def gap_clauses():
    return [n for n, v in NODES.items() if v[0] == "Clause"
            and not any(NODES[d][0] == "Test" for d in nx.descendants(G, n))]


def test_status(t):
    d = st.session_state.decisions.get(("test", t["id"]))
    if d:
        return d
    if t["level"] == "L5" and any(x["level"] == "L4" and test_status(x) != "Approved" for x in TESTS):
        return "Blocked"  # rule: no L5 before all L4 tests are approved
    return t["status"]


def compare(p):
    rows = []
    for f in ("Model", "Rating", "Tag"):
        e, r, c = p["expected"][f], p["read"][f], p["conf"][f]
        same = e.replace(" ", "").lower() == r.replace(" ", "").lower()
        rows.append(dict(Field=f, Expected=e, Read=r, Match="⚠️ Review" if c < CONF_MIN else ("✅ Match" if same else "❌ Mismatch"), Confidence=c))
    return rows


def photo_open(p):
    return ("photo", p["id"]) not in st.session_state.decisions and any(r["Match"] != "✅ Match" for r in compare(p))


def vis_sys(system):
    s = st.session_state.system
    return s == "All" or system in (s, "Both")


def open_insights():
    return [i for i in INSIGHTS if vis_sys(i["system"]) and ("insight", i["id"]) not in st.session_state.decisions]


def insight_days(i):
    return i["days"] if i["days"] is not None else round(simulate(i["node"], st.session_state.delay)["median"])


def log_decision(kind, item_id, decision):
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as c:
        c.execute("CREATE TABLE IF NOT EXISTS decisions(ts TEXT, kind TEXT, item_id TEXT, decision TEXT)")
        c.execute("INSERT INTO decisions VALUES (?,?,?,?)",
                  (dt.datetime.now().isoformat(timespec="seconds"), kind, item_id, decision))
    st.session_state.decisions[(kind, item_id)] = decision
    st.toast(f"{item_id} {decision.lower()}")


def go(page, focus=None):
    st.session_state.page = page
    if focus:
        st.session_state.focus = focus


def reset():
    st.session_state.update(decisions={}, chat=[], delay=12, focus=FOCUS)
    if DB.exists():
        with sqlite3.connect(DB) as c:
            c.execute("DROP TABLE IF EXISTS decisions")


def answer(q):
    try:
        from src.ai.qa import answer as live  # Member B: should return dict(text, cites, evidence)
        return live(q)
    except ImportError:
        pass
    ql, delay = q.lower(), st.session_state.delay
    if "ups" in ql:
        imp = impact("SUB-009")
        return dict(text=f"UPS-02 is flagged because submittal SUB-009 lists 400 kVA while clause CL-4.2 requires 500 kVA. "
                         f"It affects {len(imp['tests'])} tests and {len(imp['tasks'])} tasks.",
                    cites=["CL-4.2", "SUB-009", "EQ-UPS-02", "T-L4-017"])
    if "chiller" in ql or "delay" in ql:
        imp, sim = impact("PO-023"), simulate("PO-023", delay)
        return dict(text=f"The **{delay}-day** delay on PO-023 affects **{len(imp['tests'])}** tests and "
                         f"**{len(imp['tasks'])}** tasks and pushes handover by about **{sim['median']:.0f} days** "
                         f"(simulation-based estimate, range {sim['p10']:.0f}-{sim['p90']:.0f}).",
                    cites=["CL-6.1", "PO-023", "T-L4-021", "TASK-031"])
    if "test" in ql or "clause" in ql or "gap" in ql:
        g = gap_clauses()
        return dict(text=f"{len(g)} clauses have no linked test: {', '.join(g)}.", cites=g)
    return dict(text="I can answer questions about the UPS deviation, the chiller delay and clauses without tests.", cites=[])


# ----------------------------------------------------------------------------- look and feel (matches the mockups)
PALETTE = {
    "light": dict(bg="#f4f7fb", panel="#ffffff", side="#ffffff", text="#0f1b3d", muted="#64748b", border="#e3e8ef",
                  pill="#f1f5f9", edge="#c3ccd9", blue="#1570ef", blue_bg="#eaf2fe", red="#e5484d", red_bg="#fdeeee",
                  amber="#f59e0b", amber_bg="#fff4e0", green="#16a34a", green_bg="#e8f7ee",
                  shadow="0 1px 3px rgba(16,24,40,.07)"),
    "dark": dict(bg="#0b1220", panel="#121a2b", side="#0f1727", text="#e6edf7", muted="#93a1b8", border="#24304a",
                 pill="#1b2640", edge="#3a4864", blue="#4c8dff", blue_bg="#14264a", red="#ff7a7f", red_bg="#3a1a1f",
                 amber="#fbbf24", amber_bg="#3a2c12", green="#4ade80", green_bg="#12301f", shadow="none"),
}
NAV = {"Overview": "🏠", "Insights": "💡", "Graph": "🕸️", "Tests": "🧪", "Photos": "📷", "Ask": "💬"}
TYPES = ["Clause", "Equipment", "PO / Submittal", "Test", "Task"]
ICON = {"Clause": "📄", "Equipment": "⚙️", "PO / Submittal": "🧾", "Test": "🧪", "Task": "📋"}
SEVK = {"Critical": ("red", "!"), "Warning": ("amber", "▲"), "Info": ("blue", "i")}

CSS = """
.stApp,[data-testid="stAppViewContainer"]{background:var(--bg);color:var(--text);font-family:Inter,"Segoe UI",system-ui,sans-serif}
header[data-testid="stHeader"]{display:none}
#MainMenu,footer{visibility:hidden}
.block-container{padding:14px 28px 28px;max-width:100%}
[data-testid="stSidebar"]{background:var(--side);border-right:1px solid var(--border);width:235px!important;min-width:235px!important}
.stMarkdown p,.stMarkdown li,.stApp h1,.stApp h2,.stApp h3,.stApp label p{color:var(--text)}
[data-testid="stSliderTickBarMin"],[data-testid="stSliderTickBarMax"]{display:none}
.stApp [data-baseweb="select"]>div,.stApp [data-baseweb="input"]>div,.stApp input{background:var(--panel)!important;color:var(--text)!important;border-color:var(--border)!important}
[data-baseweb="popover"] ul{background:var(--panel)!important}[data-baseweb="popover"] li{color:var(--text)!important}
[class*="st-key-panel_"],[class*="st-key-card_"]{background:var(--panel);border:1px solid var(--border);border-radius:14px;box-shadow:var(--shadow);padding:16px 18px}
.st-key-topbar{background:var(--panel);border-bottom:1px solid var(--border);margin:-14px -28px 18px;padding:4px 28px}
.st-key-health{background:var(--blue_bg);border:1px solid var(--border);border-radius:14px;padding:14px 20px;margin-bottom:16px}
.logo{display:flex;gap:10px;align-items:center}.lg{width:38px;height:38px;border-radius:10px;background:var(--blue);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px}
.logo b{font-size:19px;color:var(--text)}.logo small{display:block;color:var(--muted);font-size:11px;margin-top:-2px}
.who{display:flex;gap:12px;align-items:center;justify-content:flex-end;font-size:13px;color:var(--text)}
.who .dot{width:8px;height:8px;border-radius:50%;background:var(--green)}
.av{width:36px;height:36px;border-radius:50%;background:var(--blue);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px}
.stButton>button{border-radius:8px;border:1px solid var(--blue);background:var(--panel);color:var(--blue);font-weight:600;padding:.3rem .8rem;min-height:0}
.stButton>button p,.stDownloadButton>button p{color:inherit!important;font-size:13px}
.stButton>button:hover{background:var(--blue_bg);border-color:var(--blue);color:var(--blue)}
.stDownloadButton>button{border-radius:8px;border:1px solid var(--blue);background:var(--panel);color:var(--blue);font-weight:600}
[class*="st-key-appr_"] button{background:var(--green);border-color:var(--green);color:#fff}
[class*="st-key-appr_"] button:hover{background:var(--green);border-color:var(--green);color:#fff;opacity:.9}
[class*="st-key-rej_"] button{border-color:var(--red);color:var(--red);background:var(--red_bg)}
[class*="st-key-rej_"] button:hover{border-color:var(--red);color:var(--red);background:var(--red_bg)}
[class*="st-key-hr_"] button{background:var(--blue_bg)}
[class*="st-key-sq_"] button{border-radius:20px;background:var(--panel);font-weight:500}
[data-testid="stFormSubmitButton"] button{background:var(--blue);border-color:var(--blue);color:#fff;padding:.45rem 1.2rem}
[data-testid="stForm"]{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:10px 14px}
[data-testid="stForm"] input{border:0!important}
div[role="radiogroup"]{gap:6px;flex-wrap:wrap}
div[role="radiogroup"] label[data-baseweb="radio"]{background:var(--pill);border:1px solid var(--border);border-radius:8px;padding:5px 14px;margin:0}
div[role="radiogroup"] label[data-baseweb="radio"]{position:relative;cursor:pointer}
div[role="radiogroup"] label[data-baseweb="radio"]>div:first-child{position:absolute;opacity:0;pointer-events:none;width:0;height:0;overflow:hidden}
div[role="radiogroup"] label[data-baseweb="radio"] p{font-weight:600;font-size:13px;color:var(--muted)!important}
div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked){background:var(--blue);border-color:var(--blue)}
div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) p{color:#fff!important}
[class*="st-key-nav_"] button{background:transparent!important;border:0!important;border-bottom:2px solid transparent!important;border-radius:0!important;box-shadow:none!important;color:var(--muted)!important;padding:14px 4px!important}
[class*="st-key-nav_"] button p{font-size:14px;font-weight:600;color:inherit!important}
[class*="st-key-nav_"][class*="_on"] button{color:var(--blue)!important;border-bottom-color:var(--blue)!important}
.sh{font-weight:600;font-size:13px;color:var(--text);margin:14px 0 6px}.sht{font-weight:600;font-size:13px}.shs{font-size:12px;color:var(--muted);margin:2px 0 6px}
.badge{background:var(--blue);color:#fff;border-radius:8px;text-align:center;padding:4px 0;font-weight:600;font-size:12px}
.note{background:var(--blue_bg);color:var(--blue);border-radius:8px;padding:8px 10px;font-size:11px;margin-top:8px}
.hl{display:flex;gap:14px;align-items:center}.shield{font-size:30px}.ht{font-size:20px;font-weight:700;color:var(--text)}.hs{font-size:14.5px;font-weight:500;color:var(--text)}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin-bottom:16px}
.kpi{border-radius:14px;padding:16px 18px;border:1px solid var(--border);background:var(--panel)}
.kpi.red{background:var(--red_bg);border-color:color-mix(in srgb,var(--red) 25%,transparent)}
.kpi.green{background:var(--green_bg);border-color:color-mix(in srgb,var(--green) 25%,transparent)}
.kpi.blue{background:var(--blue_bg);border-color:color-mix(in srgb,var(--blue) 25%,transparent)}
.kpi.amber{background:var(--amber_bg);border-color:color-mix(in srgb,var(--amber) 25%,transparent)}
.ki{font-size:22px}.kl{font-size:15px;font-weight:600;color:var(--text);margin-top:6px}.kv{font-size:30px;font-weight:800;color:var(--text);line-height:1.2}
.kd{font-size:13px;font-weight:600;margin-top:4px}.t-red{color:var(--red)}.t-green{color:var(--green)}.t-amber{color:var(--amber)}.t-muted{color:var(--muted)}
.bar{display:flex;align-items:center;gap:10px;margin-top:6px;font-size:12px;color:var(--muted)}.bar i{display:block;height:7px;background:var(--blue);border-radius:4px}
.bar b{flex:1;height:7px;background:var(--border);border-radius:4px;overflow:hidden;display:block}
.pt{font-size:17px;font-weight:700;color:var(--text)}.pl{color:var(--blue);font-size:13px;font-weight:600;float:right}
.num{width:26px;height:26px;border-radius:50%;background:var(--pill);display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;color:var(--text)}
.rt{font-size:14px;font-weight:600;color:var(--text)}.rs{font-size:12px;color:var(--muted)}
.chip{display:inline-block;padding:2px 10px;border-radius:7px;font-size:12px;font-weight:600;margin-right:6px}
.c-blue{background:var(--blue_bg);color:var(--blue)}.c-red{background:var(--red_bg);color:var(--red)}.c-amber{background:var(--amber_bg);color:var(--amber)}
.c-green{background:var(--green_bg);color:var(--green)}.c-gray{background:var(--pill);color:var(--muted)}
.sico{display:inline-flex;width:30px;height:30px;border-radius:50%;align-items:center;justify-content:center;color:#fff;font-weight:700;margin-right:8px;vertical-align:middle}
.s-red{background:var(--red)}.s-amber{background:var(--amber)}.s-blue{background:var(--blue)}
.strip{background:var(--blue_bg);border:1px solid var(--border);border-radius:12px;padding:12px 16px;font-size:14px;color:var(--text);margin-bottom:14px}
.ititle{font-size:17px;font-weight:700;color:var(--text);margin-left:6px}.right{text-align:right;color:var(--muted);font-size:12px}
.sec{display:flex;gap:10px;margin-bottom:12px}.si{font-size:16px;width:22px}.sl2{font-weight:700;font-size:13px;color:var(--text)}.st2{font-size:13px;color:var(--muted)}
.tb{width:100%;border-collapse:collapse;font-size:13px;color:var(--text)}.tb th{text-align:left;color:var(--muted);font-weight:600;padding:10px 12px;border-bottom:1px solid var(--border)}
.tb td{padding:11px 12px;border-bottom:1px solid var(--border)}.tb tr.bad td{background:var(--red_bg)}
.cb{height:6px;background:var(--border);border-radius:4px;overflow:hidden;margin-top:3px;width:90px}.cb i{display:block;height:6px;border-radius:4px}
.kvr{display:flex;justify-content:space-between;font-size:13px;padding:5px 0;color:var(--text)}.kvr span:first-child{color:var(--muted)}
.insb{background:var(--blue_bg);border-radius:10px;padding:12px;font-size:13px;color:var(--text);margin:8px 0 14px}
.fin{display:grid;grid-template-columns:1fr 24px 1fr;gap:6px;align-items:center;margin:8px 0 14px}.fin div.b{border:1px solid var(--border);border-radius:10px;padding:10px;font-size:12px;color:var(--muted)}
.fin div.b b{display:block;font-size:20px;color:var(--text)}.fin div.b.hot{background:var(--red_bg);border-color:var(--red)}.fin div.b.hot b{color:var(--red)}
.legend{display:flex;gap:18px;font-size:12px;color:var(--muted);border:1px solid var(--border);border-radius:10px;padding:8px 14px;margin-top:8px}
.photo{position:relative;border-radius:12px;overflow:hidden}.photo img{width:100%;display:block}
.bbox{position:absolute;border:3px solid var(--blue);border-radius:6px}.aib{position:absolute;left:12px;bottom:12px;background:var(--blue);color:#fff;padding:5px 12px;border-radius:16px;font-size:12px;font-weight:600}
.banner{display:flex;align-items:center;gap:12px;background:var(--red_bg);border:1px solid var(--red);border-radius:10px;padding:12px 16px;font-weight:700;color:var(--red);margin-bottom:14px;font-size:15px}
.banner.warn{background:var(--amber_bg);border-color:var(--amber);color:var(--amber)}.banner.ok{background:var(--green_bg);border-color:var(--green);color:var(--green)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:14px 0}.box{border-radius:10px;padding:12px 14px;font-size:13px;color:var(--text)}.box b{display:block;margin-bottom:4px}
.box.r{background:var(--red_bg)}.box.b{background:var(--blue_bg)}.box.b b{color:var(--blue)}.box.r b{color:var(--red)}
.addl{display:grid;grid-template-columns:1.2fr 1fr 1fr 1.4fr 1.2fr;gap:10px;font-size:13px;color:var(--text);align-items:center}.addl small{display:block;color:var(--muted);font-size:11px}
.ub{display:flex;justify-content:flex-end;gap:10px;align-items:center;margin-bottom:4px}.bub{background:var(--blue);color:#fff;padding:10px 18px;border-radius:12px;font-weight:600;font-size:14px}
.tm{text-align:right;color:var(--muted);font-size:11px;margin-bottom:14px}.ab{display:flex;gap:12px;margin-bottom:6px}.ab .av{flex:none}
.acard{background:var(--blue_bg);border:1px solid var(--border);border-radius:12px;padding:16px 18px;max-width:760px;font-size:14.5px;color:var(--text)}
.ev{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:10px 14px;margin-top:10px}.ev summary{font-weight:700;font-size:13px;cursor:pointer}
.evf{display:flex;justify-content:space-between;align-items:center;margin-top:10px;font-size:12px;color:var(--blue);font-weight:600}
"""


def inject_css():
    vars_ = "".join(f"--{k}:{v};" for k, v in PALETTE["dark" if st.session_state.get("dark") else "light"].items())
    st.markdown(f"<style>:root{{{vars_}}}{CSS}</style>", unsafe_allow_html=True)


def H(s, target=st):
    target.markdown(re.sub(r"\n\s*", "", s), unsafe_allow_html=True)


def chip(text, kind="blue"):
    return f'<span class="chip c-{kind}">{text}</span>'


def sev_chip(sev):
    return chip(sev, SEVK[sev][0])


def now_str(fmt="%b %d, %Y %H:%M"):
    return dt.datetime.now().strftime(fmt)


def sec(icon, label, text):
    return f'<div class="sec"><div class="si">{icon}</div><div><div class="sl2">{label}</div><div class="st2">{text}</div></div></div>'


def kpi(cls, icon, label, value, foot, foot_cls, extra=""):
    return (f'<div class="kpi {cls}"><div class="ki">{icon}</div><div class="kl">{label}</div>'
            f'<div class="kv">{value}</div>{extra}<div class="kd {foot_cls}">{foot}</div></div>')


def risk_sub(i):
    if i["node"]:
        imp = impact(i["node"])
        return f"Affects: {len(imp['tests'])} tests, {len(imp['tasks'])} tasks • ~{insight_days(i)} days delay"
    low = min((min(p["conf"].values()) for p in PHOTOS.values()), default=1)
    return f"Low confidence ({low:.0%})"


def chart_svg(df):
    ymax = max(15, int(np.ceil(df.sum(axis=1).max() / 5) * 5))
    W, Ht, L, Tp, B = 520, 290, 34, 26, 30
    ph = Ht - Tp - B
    o = [f'<svg viewBox="0 0 {W} {Ht}" width="100%">']
    for v in range(0, ymax + 1, 5):
        y = Tp + ph - v / ymax * ph
        o.append(f'<line x1="{L}" x2="{W - 6}" y1="{y:.1f}" y2="{y:.1f}" style="stroke:var(--border)"/>'
                 f'<text x="{L - 8}" y="{y + 4:.1f}" font-size="11" text-anchor="end" style="fill:var(--muted)">{v}</text>')
    slot = (W - L - 6) / 5
    for k, lv in enumerate(LEVELS):
        x, base = L + slot * k + slot / 2 - 28, Tp + ph
        for col, key in (("--blue", "Pending"), ("--green", "Approved"), ("--red", "Rejected")):
            v = int(df.loc[lv, key])
            if v:
                h = v / ymax * ph
                base -= h
                o.append(f'<rect x="{x:.1f}" y="{base:.1f}" width="56" height="{h:.1f}" rx="2" style="fill:var({col})"/>')
        o.append(f'<text x="{x + 28:.1f}" y="{base - 6:.1f}" font-size="13" font-weight="700" text-anchor="middle" style="fill:var(--text)">{int(df.loc[lv].sum())}</text>'
                 f'<text x="{x + 28:.1f}" y="{Ht - 10}" font-size="12" font-weight="600" text-anchor="middle" style="fill:var(--text)">{lv}</text>')
    return "".join(o) + "</svg>"


def to_excel(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Traceability")
    return buf.getvalue()


def to_word(rows):
    from docx import Document
    d = Document()
    d.add_heading("Commissioning test package", 1)
    for t in rows:
        d.add_heading(f"{t['id']} ({t['level']}, Tier {t['tier']}) - {t['clause']}", 2)
        d.add_paragraph("Steps: " + t["steps"])
        d.add_paragraph("Instruments: " + t["instruments"])
        d.add_paragraph("Acceptance: " + t["acceptance"])
        d.add_paragraph("Why this level: " + t["reason"])
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


# ----------------------------------------------------------------------------- pages
def overview():
    s = st.session_state
    sim = simulate(FOCUS, s.delay)
    open_i = open_insights()
    crit = sum(i["sev"] == "Critical" for i in open_i)
    gaps = gap_clauses()
    cov = 1 - len(gaps) / sum(v[0] == "Clause" for v in NODES.values())
    stat = [test_status(t) for t in TESTS]
    appr = stat.count("Approved")
    pct = appr / max(len(TESTS), 1)
    review = sum(photo_open(p) for p in PHOTOS.values())
    state = "at risk" if sim["prob"] > 0.3 else "on track"
    with st.container(key="health"):
        a, b = st.columns([8, 1.5], vertical_alignment="center")
        H(f'<div class="hl"><div class="shield">🛡️</div><div><div class="ht">Project Health</div><div class="hs">'
          f'Handover {state}: +{sim["median"]:.0f} days, {sim["prob"]:.0%} chance of missing target date. '
          f'Main driver: Chiller {FOCUS}.</div></div></div>', a)
        b.button("View Details  →", key="vd", on_click=go, args=("Insights",), use_container_width=True)
    bar = f'<div class="bar"><b><i style="width:{pct:.0%}"></i></b>{pct:.0%}</div>'
    H('<div class="kpis">'
      + kpi("red", "⚠️", "Open Deviations", len(open_i), f"↑ {crit} critical", "t-red")
      + kpi("green", "📋", "Spec Coverage", f"{cov:.0%}", f"{len(gaps)} clauses without a test", "t-green" if not gaps else "t-amber")
      + kpi("blue", "🧪", "Tests Approved", f"{appr} / {len(TESTS)}", "", "", bar)
      + kpi("amber", "⏱️", "Projected Delay", f"+{sim['median']:.0f} days", f"↑ range {sim['p10']:.0f}-{sim['p90']:.0f} d", "t-red")
      + kpi("", "🖼️", "Photos for Review", review, f"↑ {review} flagged" if review else "none open", "t-amber") + '</div>')
    left, right = st.columns(2)
    with left, st.container(key="panel_risks"):
        H('<div class="pt">⚠️ Top 3 Risks <span class="pl">View All →</span></div><br>')
        order = {"Critical": 0, "Warning": 1, "Info": 2}
        for n, i in enumerate(sorted(open_i, key=lambda x: order[x["sev"]])[:3], 1):
            c = st.columns([0.5, 1.5, 6, 1.1], vertical_alignment="center")
            H(f'<div class="num">{n}</div>', c[0])
            H(sev_chip(i["sev"]), c[1])
            H(f'<div class="rt">{i["title"]}</div><div class="rs">{risk_sub(i)}</div>', c[2])
            c[3].button("Open", key=f"open_{i['id']}", on_click=go, args=("Insights",), use_container_width=True)
        if not open_i:
            st.success("No open deviations. Run the spec check to refresh.")
    with right, st.container(key="panel_chart"):
        H('<div class="pt">📊 Test Status by Level</div>')
        df = pd.DataFrame({"level": [t["level"] for t in TESTS],
                           "status": ["Approved" if x == "Approved" else "Rejected" if x == "Rejected" else "Pending" for x in stat]})
        df = df.groupby(["level", "status"]).size().unstack(fill_value=0).reindex(LEVELS, fill_value=0)
        df = df.reindex(columns=["Approved", "Pending", "Rejected"], fill_value=0)
        H('<div style="text-align:right;font-size:12px;color:var(--muted)">'
          '<span style="color:var(--green)">●</span> Approved &nbsp; <span style="color:var(--blue)">●</span> Pending &nbsp; '
          '<span style="color:var(--red)">●</span> Rejected</div>' + chart_svg(df))
    H(f'<div style="font-size:12px;color:var(--muted);margin-top:12px"><span style="color:var(--green)">●</span> Live Data • '
      f'Auto Refresh: 30s &nbsp; Last updated {now_str()}</div>')


def insights():
    cnt = Counter(i["vendor"] for i in INSIGHTS)
    top, n = cnt.most_common(1)[0]
    H(f'<div class="strip">🔽 &nbsp;<b>{n} of {len(INSIGHTS)} deviations come from the same vendor ({top})</b></div>')
    for i in [i for i in INSIGHTS if vis_sys(i["system"])]:
        dec = st.session_state.decisions.get(("insight", i["id"]))
        kind, glyph = SEVK[i["sev"]]
        imp = impact(i["node"]) if i["node"] else None
        impact_line = (f"{len(imp['tests'])} tests, {len(imp['tasks'])} tasks, ~{insight_days(i)} days delay" if imp
                       else f"~{insight_days(i)} days delay if the unit has to be replaced")
        with st.container(key=f"card_{i['id']}"):
            t = st.columns([5, 3], vertical_alignment="center")
            H(f'<span class="sico s-{kind}">{glyph}</span>{sev_chip(i["sev"])}<span class="ititle">{i["title"]}</span>', t[0])
            H("".join(chip(x) for x in i["ids"]) + (chip(f"✔ {dec}", "green") if dec else "")
              + f' <span class="right">🕒 {now_str()}</span>', t[1])
            b = st.columns([4, 4, 2.6])
            H(sec("📄", "What happened", i["what"].format(delay=st.session_state.delay))
              + sec("⚠️", "Why it matters", i["why"]), b[0])
            H(sec("⚡", "Impact", impact_line) + sec("🔗", "Likely cause", i["cause"])
              + sec("⚙️", "Recommended action", i["action"]), b[1])
            b[2].button("⌗  View in graph", key=f"vg_{i['id']}", on_click=go, args=("Graph", i["node"] or "SUB-009"), use_container_width=True)
            r = b[2].columns(2)
            if r[0].button("✔ Approve", key=f"appr_{i['id']}", use_container_width=True):
                log_decision("insight", i["id"], "Approved"); st.rerun()
            if r[1].button("✕ Reject", key=f"rej_{i['id']}", use_container_width=True):
                log_decision("insight", i["id"], "Rejected"); st.rerun()


def graph_svg(blast, focus):
    aff = impact(focus)["all"] if blast else set()
    hot = aff | {focus}
    cols = [[n for n in G if NODES[n][0] == t and vis_sys(NODES[n][2])] for t in TYPES]
    NW, NH, GY, GX, TOP = 150, 50, 16, 190, 58
    rows = max(len(c) for c in cols) or 1
    pos = {}
    for k, c in enumerate(cols):
        off = (rows - len(c)) * (NH + GY) / 2
        for j, n in enumerate(c):
            pos[n] = (8 + k * GX, TOP + off + j * (NH + GY))
    W, Ht = 8 + 4 * GX + NW + 8, TOP + rows * (NH + GY)
    o = [f'<svg viewBox="0 0 {W} {Ht}" width="100%"><defs><marker id="ah" viewBox="0 0 8 8" refX="7" refY="4" '
         'markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8 z" style="fill:var(--red)"/></marker></defs>']
    for k, t in enumerate(TYPES):
        x = 8 + k * GX
        o.append(f'<text x="{x + 4}" y="24" style="font:700 13px Segoe UI,sans-serif;fill:var(--text)">{ICON[t]} {t}</text>'
                 f'<text x="{x + 4}" y="42" style="font:12px Segoe UI,sans-serif;fill:var(--muted)">({len(cols[k])})</text>')
    tidx = {t: i for i, t in enumerate(TYPES)}
    for a, b in G.edges:
        if a in pos and b in pos and tidx[NODES[b][0]] - tidx[NODES[a][0]] in (1, 2):
            x1, y1, x2, y2 = pos[a][0] + NW, pos[a][1] + NH / 2, pos[b][0], pos[b][1] + NH / 2
            dx = (x2 - x1) / 2
            red = blast and a in hot and b in hot
            style = "stroke:var(--red);stroke-width:2" if red else "stroke:var(--edge);stroke-width:1.2"
            o.append(f'<path d="M{x1},{y1} C{x1 + dx},{y1} {x2 - dx},{y2} {x2},{y2}" style="fill:none;{style}"'
                     + (' marker-end="url(#ah)"' if red else "") + "/>")
    for n, (x, y) in pos.items():
        typ, label, _ = NODES[n]
        icon = ICON[typ]
        if n == focus:
            st_ = "fill:var(--panel);stroke:var(--blue);stroke-width:2.5"
        elif n in aff:
            st_, icon = "fill:var(--red_bg);stroke:var(--red);stroke-width:1.5", "❗"
        elif blast:
            st_ = "fill:var(--pill);stroke:var(--border);opacity:.8"
        else:
            st_ = "fill:var(--panel);stroke:var(--border)"
        o.append(f'<rect x="{x}" y="{y}" width="{NW}" height="{NH}" rx="10" style="{st_}"/>'
                 f'<text x="{x + 12}" y="{y + 31}" font-size="16">{icon}</text>'
                 f'<text x="{x + 38}" y="{y + 22}" style="font:700 12px Segoe UI,sans-serif;fill:var(--text)">{n}</text>'
                 f'<text x="{x + 38}" y="{y + 38}" style="font:11px Segoe UI,sans-serif;fill:var(--muted)">{label}</text>')
    return "".join(o) + "</svg>"


def graph():
    s = st.session_state
    focus = s.focus if s.focus in G else FOCUS
    left, right = st.columns([3.2, 1.15])
    with left, st.container(key="panel_graph"):
        a, b = st.columns([3, 2], vertical_alignment="center")
        H('<div class="pt">🕸️ Dependency Graph</div><div class="rs">Blast-radius view of how a change affects related nodes across the project.</div>', a)
        mode = b.radio("View", ["Normal view", "Blast-radius mode"], horizontal=True, index=1, key="gmode", label_visibility="collapsed")
        blast = mode.startswith("Blast")
        H(graph_svg(blast, focus))
        H('<div class="legend"><b style="color:var(--text)">Node legend:</b><span>🧾 PO / Submittal</span><span>⚙️ Equipment</span>'
          '<span>📄 Clause</span><span>🧪 Test</span><span>📋 Task</span><span style="margin-left:auto">'
          '<span style="color:var(--red)">●</span> Affected &nbsp; <span style="color:var(--muted)">●</span> Unaffected &nbsp; '
          '<span style="color:var(--blue)">○</span> Changed</span></div>')
    imp, sim = impact(focus), simulate(focus, s.delay)
    typ, label, system = NODES[focus]
    anc = nx.ancestors(G, focus) | {focus}
    clause = next((x for x in anc if NODES[x][0] == "Clause"), "-")
    equip = next((x for x in anc if NODES[x][0] == "Equipment"), "-")
    after = BASE_FINISH + dt.timedelta(days=round(sim["median"]))
    text = (f"Delaying {label.lower()} by {s.delay} days affects the installation, testing and commissioning chain, "
            f"causing a {sim['median']:.0f}-day overall delay." if typ == "PO / Submittal" else
            f"A {s.delay}-day change on {focus} affects {len(imp['tests'])} tests and {len(imp['tasks'])} tasks, "
            f"with about {sim['median']:.0f} days overall delay.")
    with right, st.container(key="panel_gdetail"):
        H(f'<div class="pt">📄 {label} {focus}</div><div class="rs">{typ}</div><br>'
          f'{chip("Affected" if blast else "Selected", "red" if blast else "blue")}'
          '<div class="sl2" style="margin:14px 0 4px">Node details</div>'
          f'<div class="kvr"><span>ID</span><span>{focus}</span></div><div class="kvr"><span>Type</span><span>{typ}</span></div>'
          f'<div class="kvr"><span>System</span><span>{system}</span></div><div class="kvr"><span>Clause</span><span>{clause}</span></div>'
          f'<div class="kvr"><span>Equipment</span><span>{equip}</span></div>'
          f'<div class="kvr"><span>Status</span><span style="color:var(--red)">{"● At risk" if blast else "Normal"}</span></div>'
          f'<div class="sl2" style="margin:14px 0 4px">💡 Insight</div><div class="insb">{text} <span class="rs">(simulation-based estimate)</span></div>'
          f'<div class="sl2">📅 Finish date comparison</div><div class="fin"><div class="b">Before<b>{BASE_FINISH:%d %b}</b>(Planned)</div>'
          f'<div style="text-align:center">→</div><div class="b hot">After<b>{after:%d %b}</b>(New)</div></div>')
        st.button("View in graph", key="vg_detail", on_click=go, args=("Graph", focus), use_container_width=True)


def tests():
    s = st.session_state
    tiers = ["III"] if s.tier == "III" else ["III", "IV"]
    c = st.columns([1, 1, 1, 1.4, 1.4], vertical_alignment="center")
    show_all = c[0].checkbox("Show all levels", value=False)
    rows = [dict(t, status=test_status(t)) for t in TESTS if vis_sys(t["system"]) and t["tier"] in tiers and (show_all or t["level"] == s.level)]
    gaps = gap_clauses()
    H(f'<div class="rs">Level {s.level} · Tier {s.tier} · {len(rows)} tests · {sum(r["status"] == "Approved" for r in rows)} approved</div>', c[1])
    matrix = pd.DataFrame([dict(Clause=t["clause"], Test=t["id"], Level=t["level"], Tier=t["tier"], Status=test_status(t),
                                SignOff=s.decisions.get(("test", t["id"]), "")) for t in TESTS])
    c[3].download_button("⬇ Traceability matrix (Excel)", to_excel(matrix), "traceability_matrix.xlsx", use_container_width=True)
    try:
        c[4].download_button("⬇ Test package (Word)", to_word(rows or TESTS), "test_package.docx", use_container_width=True)
    except ImportError:
        c[4].caption("Install python-docx for Word export")
    kind = {"Approved": "green", "Draft": "gray", "Rejected": "red", "Blocked": "amber"}
    with st.container(key="panel_tests"):
        if not rows:
            st.info(f"No {s.level} tests for this filter. Pick another level or tick 'Show all levels'.")
        else:
            body = "".join(f'<tr><td><b>{r["id"]}</b></td><td>{chip(r["level"])}</td><td>{chip(r["tier"], "gray")}</td>'
                           f'<td>{chip(r["clause"])}</td><td>{r["equipment"]}</td><td>{chip(r["status"], kind[r["status"]])}</td></tr>' for r in rows)
            H('<table class="tb"><tr><th>Test ID</th><th>Level</th><th>Tier</th><th>Clause</th><th>Equipment</th><th>Status</th></tr>' + body + "</table>")
    if rows:
        pick = st.selectbox("Test details", [r["id"] for r in rows])
        t = next(r for r in rows if r["id"] == pick)
        steps = "".join(f"<li>{x.strip()}</li>" for x in t["steps"].split(";"))
        with st.container(key="panel_tdetail"):
            H(f'<div class="pt">{t["id"]} {chip(t["level"])}{chip("Tier " + t["tier"], "gray")}{chip(t["status"], kind[t["status"]])}</div>'
              f'<div class="sl2" style="margin-top:10px">Steps</div><ol class="st2">{steps}</ol>'
              + sec("🧰", "Instruments", t["instruments"]) + sec("✅", "Acceptance criteria", t["acceptance"])
              + sec("🎯", "Why this level", t["reason"]) + sec("📄", "Cited clause", f'{t["clause"]} – {NODES[t["clause"]][1]}'))
            if t["status"] == "Blocked":
                st.warning("Blocked by rule: no L5 test before all L4 tests are approved.")
            b = st.columns([1, 1, 5])
            if b[0].button("✔ Approve", key=f"appr_{pick}", use_container_width=True):
                log_decision("test", pick, "Approved"); st.rerun()
            if b[1].button("✕ Reject", key=f"rej_{pick}", use_container_width=True):
                log_decision("test", pick, "Rejected"); st.rerun()
    if gaps:
        H(f'<div class="strip" style="margin-top:14px;background:var(--amber_bg)">⚠️ <b>Clauses with no test ({len(gaps)}):</b> '
          + ", ".join(f"{g} ({NODES[g][1]})" for g in gaps) + "</div>")


def nameplate(p):
    f = PHOTO_DIR / p.get("file", f"{p['id']}.png")
    if f.exists():
        return Image.open(f)
    img = Image.new("RGB", (560, 340), "#9aa1ab")
    d = ImageDraw.Draw(img)
    d.rectangle((40, 30, 520, 310), fill="#d9dde2", outline="#6b7280", width=3)
    for n, line in enumerate([p["read"]["Model"], f"In {p['read']['Rating']}", p["read"]["Tag"], "Ue 690V  50/60Hz"]):
        d.text((70, 60 + n * 55), line, fill="#111827")
    return img.filter(ImageFilter.GaussianBlur(5)) if p["blur"] else img


def install_checks():
    """L2: installation checklist per equipment (engineer confirms from site photos)."""
    f = ROOT / "data" / "equipment.csv"
    equip = list(csv.DictReader(open(f))) if f.exists() else [
        dict(equipment_id=n, type=v[1], system=v[2].lower()) for n, v in NODES.items() if v[0] == "Equipment"]
    equip = [e for e in equip if vis_sys(e["system"].title())]
    done = sum(st.session_state.get(f"l2-{e['equipment_id']}-{i}", False)
               for e in equip for i in range(len(l2_checklist(e["system"]))))
    total = sum(len(l2_checklist(e["system"])) for e in equip)
    H('<div style="display:flex;gap:12px;align-items:center"><div class="lg" style="width:40px;height:40px">📷</div>'
      '<div><div class="pt" style="font-size:22px">Photos: L2 installation checks</div>'
      f'<div class="rs">Confirm each item from site photos. {done} of {total} items checked.</div></div></div>')
    with st.container(key="panel_l2"):
        for e in equip:
            eq = e["equipment_id"]
            state = st.session_state.decisions.get(("install", eq))
            with st.expander(f"{eq}  {e['type']}" + (f"   ✔ {state}" if state else "")):
                for i, item in enumerate(l2_checklist(e["system"])):
                    st.checkbox(item, key=f"l2-{eq}-{i}")
                b = st.columns([1, 1, 5])
                if b[0].button("✔ Approve", key=f"appr_l2_{eq}", use_container_width=True):
                    log_decision("install", eq, "Approved"); st.rerun()
                if b[1].button("✕ Reject", key=f"rej_l2_{eq}", use_container_width=True):
                    log_decision("install", eq, "Rejected"); st.rerun()


def photos():
    if st.session_state.level == "L2":
        return install_checks()
    top = st.columns([4, 2], vertical_alignment="center")
    H('<div style="display:flex;gap:12px;align-items:center"><div class="lg" style="width:40px;height:40px">📷</div>'
      '<div><div class="pt" style="font-size:22px">Photos</div><div class="rs">Verify equipment in the field against approved design using AI vision.</div></div></div>', top[0])
    pid = top[1].radio("Photo", list(PHOTOS), horizontal=True, key="photo_sel", label_visibility="collapsed")
    p = PHOTOS[pid]
    rows = compare(p)
    bad = [r for r in rows if r["Match"] == "❌ Mismatch"]
    low = [r for r in rows if r["Match"] == "⚠️ Review"]
    buf = io.BytesIO()
    nameplate(p).convert("RGB").save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    bx = p.get("bbox", (11, 31, 26, 14))
    with st.container(key="panel_photo"):
        left, right = st.columns([2.1, 3.6])
        H(f'<div class="photo"><img src="data:image/png;base64,{b64}"/><div class="bbox" style="left:{bx[0]}%;top:{bx[1]}%;width:{bx[2]}%;height:{bx[3]}%"></div>'
          '<div class="aib">✦ AI Extracted</div></div>', left)
        if bad:
            r = bad[0]
            banner = f'<div class="banner">❗ Mismatch: {r["Field"].lower()} {r["Read"]}, approved {r["Expected"]}</div>'
        elif low:
            banner = f'<div class="banner warn">⚠️ Needs review: {low[0]["Field"].lower()} read with {low[0]["Confidence"]:.0%} confidence</div>'
        else:
            banner = '<div class="banner ok">✔ All fields match the approved submittal</div>'
        trs = ""
        for r in rows:
            m = r["Match"]
            mk = ('<span class="t-green">✔ Match</span>' if m.startswith("✅") else
                  '<span class="t-red">✖ Mismatch</span>' if m.startswith("❌") else '<span class="t-amber">⚠ Needs review</span>')
            col = "var(--amber)" if m.startswith("⚠") else "var(--blue)" if m.startswith("❌") else "var(--green)"
            trs += (f'<tr class="{"bad" if m.startswith("❌") else ""}"><td>{r["Field"]}</td><td>{r["Expected"]}</td>'
                    f'<td>{"<b class=t-red>" + r["Read"] + "</b>" if m.startswith("❌") else r["Read"]}</td><td>{mk}</td>'
                    f'<td>{r["Confidence"]:.0%}<div class="cb"><i style="width:{r["Confidence"]:.0%};background:{col}"></i></div></td></tr>')
        H(banner + '<table class="tb"><tr><th>Field</th><th>Expected (Approved)</th><th>Read from photo</th><th>Match</th><th>Confidence</th></tr>'
          + trs + '</table>' + f'<div class="two"><div class="box r"><b>❗ Why it matters</b>{p["why"]}</div>'
          f'<div class="box b"><b>💡 Recommended action</b>{p["action"]}</div></div>', right)
        c = right.columns([2, 0.6, 1.5, 1.5])
        if c[0].button("↻  Send to human review", key=f"hr_{pid}", use_container_width=True):
            log_decision("photo", pid, "In review"); st.rerun()
        if c[2].button("✔ Approve", key=f"appr_ph_{pid}", use_container_width=True):
            log_decision("photo", pid, "Approved"); st.rerun()
        if c[3].button("✕ Reject", key=f"rej_ph_{pid}", use_container_width=True):
            log_decision("photo", pid, "Rejected"); st.rerun()
        dec = st.session_state.decisions.get(("photo", pid))
        if dec:
            right.caption(f"Status: {dec}")
    with st.container(key="panel_addl"):
        H(f'<div class="addl"><div><b>📄 Additional details</b></div><div><small>Photo ID</small>{pid}</div>'
          f'<div><small>Equipment</small>{p["equipment"]}</div><div><small>Location</small>{p["location"]}</div>'
          f'<div><small>Timestamp</small>{now_str()}</div></div>')


def ask():
    hist = st.session_state.chat
    with st.container(key="panel_chat"):
        box = st.container()
    cols, pending = st.columns([1.3, 1.9, 1.6, 2.6]), None
    for col, q in zip(cols, SUGGESTED):
        if col.button("💬  " + q, key=f"sq_{q}", use_container_width=True):
            pending = q
    with st.form("askform", clear_on_submit=True):
        f = st.columns([10, 1.3], vertical_alignment="center")
        text = f[0].text_input("Ask", placeholder="✦  Ask about specs, equipment, tests or risks...", label_visibility="collapsed")
        sent = f[1].form_submit_button("➤  Send")
    prompt = (text.strip() if sent and text.strip() else None) or pending
    if prompt:
        hist.append(dict(role="user", text=prompt, t=now_str("%I:%M %p")))
        hist.append(dict(role="assistant", t=now_str("%I:%M %p"), **answer(prompt)))
    with box:
        if not hist:
            H('<div class="rs" style="padding:60px 0;text-align:center">Pick a suggested question below or type your own.</div>')
        for k, m in enumerate(hist):
            if m["role"] == "user":
                H(f'<div class="ub"><div class="bub">{m["text"]}</div><div class="av">👤</div></div><div class="tm">{m["t"]}</div>')
                continue
            cites = m.get("cites", [])
            ev = ""
            if cites:
                rows = "".join(f'<tr><td>{ICON[NODES[c][0]]} {c}</td><td>{NODES[c][0]}</td><td>{FIELD_FOR[NODES[c][0]]}</td></tr>' for c in cites if c in NODES)
                ok = all(c in G for c in cites)
                badge = (chip("✔ All citations verified", "green") if ok else chip("Some citations not in graph", "amber"))
                ev = (f'<div>{"".join(chip(c) for c in cites)}</div><details class="ev" {"open" if k == len(hist) - 1 else ""}>'
                      f'<summary>Evidence used ({len(cites)} graph nodes)</summary><table class="tb"><tr><th>Node ID</th><th>Type</th><th>Field used</th></tr>{rows}</table>'
                      f'<div class="evf"><span>↗ Open in graph</span>{badge}</div></details>')
            H(f'<div class="ab"><div class="av">🧊</div><div class="acard">{m["text"]}{ev}</div></div><div class="rs" style="margin:0 0 14px 48px">{m["t"]}</div>')


# ----------------------------------------------------------------------------- shell
for k, v in dict(page="Overview", focus=FOCUS, decisions={}, chat=[], delay=12, level="L4", tier="III", system="All", dark=False).items():
    st.session_state.setdefault(k, v)
inject_css()

with st.container(key="topbar"):
    a, b, c = st.columns([2.8, 5.4, 2.6], vertical_alignment="center")
    H('<div class="logo"><div class="lg">DC</div><div><b>DC Copilot</b><small>AI Project Monitoring for Data Centre Construction</small></div></div>', a)
    with b, st.container(key="topnav"):
        for col, p in zip(st.columns(len(PAGES)), PAGES):
            on = st.session_state.page == p
            col.button(f"{NAV[p]}  {p}", key=f"nav_{p}_{'on' if on else 'off'}", on_click=go, args=(p,), use_container_width=True)
    H('<div class="who"><span><span class="dot"></span>&nbsp; Project: DC Alpha ⌄</span><div class="av">AS</div><b>Arya Jadhav</b> ⌄</div>', c)

with st.sidebar:
    H('<div class="sh">🗂️ Project Level</div>')
    st.radio("Level", LEVELS, horizontal=True, key="level", label_visibility="collapsed")
    H('<div class="sh">🛡️ Tier</div>')
    st.radio("Tier", ["III", "IV"], horizontal=True, key="tier", label_visibility="collapsed")
    H('<div class="sh">▦ System Filter</div>')
    st.radio("System", ["Power", "Cooling", "All"], horizontal=True, key="system", label_visibility="collapsed")
    H('<div style="height:10px"></div>')
    with st.container(key="panel_sim"):
        H('<div class="sht">⚙️ Simulate change</div><div class="shs">Delay chiller delivery (days)</div>')
        x = st.columns([3.6, 1.4], vertical_alignment="center")
        x[0].slider("Delay", 0, 30, key="delay", label_visibility="collapsed")
        H(f'<div class="badge">+{st.session_state.delay}</div>', x[1])
        H('<div class="note">ⓘ This will update related nodes in the graph and test timelines.</div>')
    H('<div style="height:10px"></div>')
    st.button("⟳  Reset demo", key="reset", on_click=reset, use_container_width=True)
    st.toggle("🌙 Dark mode", key="dark")

{"Overview": overview, "Insights": insights, "Graph": graph, "Tests": tests, "Photos": photos, "Ask": ask}[st.session_state.page]()
