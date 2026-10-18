"""Generate the synthetic project data for DC-EPC Copilot (Member A, Day 1).

Run from the project root:   python3 data/make_data.py
Reads:   data/spec_ground_truth.csv
Writes:  data/equipment.csv, data/pos.csv, data/submittals.csv, data/tasks.csv
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent
random.seed(42)  # same data every run

# ---------------------------------------------------------------- equipment
EQUIPMENT = [
    ("EQ-SWG-01", "Main LV switchgear", "power"),
    ("EQ-UPS-02", "UPS module", "power"),
    ("EQ-BAT-02", "UPS battery system", "power"),
    ("EQ-GEN-01", "Standby diesel generator", "power"),
    ("EQ-ATS-01", "Automatic transfer switch", "power"),
    ("EQ-BRK-05", "Main feeder circuit breaker", "power"),
    ("EQ-PDU-01", "Power distribution unit", "power"),
    ("EQ-CHL-01", "Water-cooled chiller", "cooling"),
    ("EQ-PMP-01", "Chilled water pump", "cooling"),
    ("EQ-CT-01", "Cooling tower", "cooling"),
    ("EQ-CRAH-01", "CRAH unit", "cooling"),
]
SYSTEM_OF = {e[0]: e[2] for e in EQUIPMENT}
VENDORS = {
    "power": ["VoltEdge Power", "GridSafe Electric", "AmpCore Systems"],
    "cooling": ["ThermoCore Systems", "CoolFlow Industries", "ChillTech India"],
}

# ------------------------------------------------- delivery tasks and POs
# (task_id, task name, equipment_id, po_id, need-by date on site)
DELIVERIES = [
    ("TASK-003", "Switchgear delivery", "EQ-SWG-01", "PO-001", "2027-03-15"),
    ("TASK-009", "UPS delivery", "EQ-UPS-02", "PO-002", "2027-04-10"),
    ("TASK-016", "Battery delivery", "EQ-BAT-02", "PO-003", "2027-04-10"),
    ("TASK-005", "Generator delivery", "EQ-GEN-01", "PO-004", "2027-03-31"),
    ("TASK-007", "ATS delivery", "EQ-ATS-01", "PO-005", "2027-04-01"),
    ("TASK-018", "Breaker delivery", "EQ-BRK-05", "PO-006", "2027-03-20"),
    ("TASK-020", "PDU delivery", "EQ-PDU-01", "PO-007", "2027-04-20"),
    ("TASK-010", "Chiller delivery", "EQ-CHL-01", "PO-008", "2027-04-15"),
    ("TASK-022", "Pump delivery", "EQ-PMP-01", "PO-009", "2027-04-10"),
    ("TASK-024", "Cooling tower delivery", "EQ-CT-01", "PO-010", "2027-04-05"),
    ("TASK-026", "CRAH delivery", "EQ-CRAH-01", "PO-011", "2027-05-01"),
]

# ------------------------------------------------ all other schedule tasks
# (task_id, name, duration_days, depends_on)
OTHER_TASKS = [
    ("TASK-001", "Site mobilisation", 10, []),
    ("TASK-002", "Civil and structural works", 40, ["TASK-001"]),
    ("TASK-004", "Switchgear installation", 15, ["TASK-002", "TASK-003"]),
    ("TASK-006", "Generator installation", 15, ["TASK-002", "TASK-005"]),
    ("TASK-008", "ATS installation", 7, ["TASK-004", "TASK-007"]),
    ("TASK-011", "Chiller installation", 20, ["TASK-002", "TASK-010"]),
    ("TASK-012", "Chilled water piping connection", 12, ["TASK-011", "TASK-023", "TASK-025"]),
    ("TASK-013", "Chiller start-up (L3)", 5, ["TASK-012"]),
    ("TASK-014", "Cooling functional test (L4)", 7, ["TASK-013", "TASK-027"]),
    ("TASK-015", "Integrated systems test (L5)", 10, ["TASK-014", "TASK-030"]),
    ("TASK-017", "UPS and battery installation", 12, ["TASK-004", "TASK-009", "TASK-016"]),
    ("TASK-019", "Breaker installation", 5, ["TASK-004", "TASK-018"]),
    ("TASK-021", "PDU installation", 8, ["TASK-019", "TASK-020"]),
    ("TASK-023", "Pump installation", 8, ["TASK-002", "TASK-022"]),
    ("TASK-025", "Cooling tower installation", 15, ["TASK-002", "TASK-024"]),
    ("TASK-027", "CRAH installation", 10, ["TASK-002", "TASK-026"]),
    ("TASK-028", "UPS start-up (L3)", 5, ["TASK-017", "TASK-021"]),
    ("TASK-029", "Generator start-up (L3)", 5, ["TASK-006", "TASK-008"]),
    ("TASK-030", "Power functional tests (L4)", 7, ["TASK-028", "TASK-029"]),
    ("TASK-031", "Documentation and handover", 14, ["TASK-015"]),
]

# ---------------------------------------------------------------- planted errors
CHILLER_PROMISED = "2027-06-01"     # error 2: chiller PO is late (need-by 2027-04-15)
UPS_BAD_RATING = 400                # error 1: spec says 500 kW

# clauses that get a vendor submittal (rating the vendor declares)
SUBMITTAL_CLAUSES = ["CL-4.1", "CL-4.2", "CL-4.4", "CL-4.5", "CL-4.9", "CL-4.10",
                     "CL-4.11", "CL-5.1", "CL-5.4", "CL-5.5", "CL-5.6", "CL-5.7"]


def d(s):
    return date.fromisoformat(s)


def write_csv(name, header, rows):
    with open(DATA / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {name}: {len(rows)} rows")


def main():
    # 1. equipment
    write_csv("equipment.csv", ["equipment_id", "type", "system"], EQUIPMENT)

    # 2. purchase orders (promised date = need-by minus 10 days, except the chiller)
    pos = []
    for _task, _name, eq, po, need_by in DELIVERIES:
        order = d("2027-02-01") if eq == "EQ-CHL-01" else d("2027-01-15")
        promised = d(CHILLER_PROMISED) if eq == "EQ-CHL-01" else d(need_by) - timedelta(days=10)
        vendor = random.choice(VENDORS[SYSTEM_OF[eq]])
        pos.append((po, eq, vendor, order.isoformat(), promised.isoformat(), (promised - order).days))
    write_csv("pos.csv", ["po_id", "equipment_id", "vendor", "order_date", "promised_date", "lead_time_days"], pos)
    vendor_of = {p[1]: p[2] for p in pos}

    # 3. submittals (built from the spec, so they match it, except the planted UPS error)
    with open(DATA / "spec_ground_truth.csv", encoding="utf-8") as f:
        clauses = {r["clause_id"]: r for r in csv.DictReader(f)}
    subs = []
    for i, cid in enumerate(SUBMITTAL_CLAUSES, start=1):
        c = clauses[cid]
        spec_val = float(c["value"])
        if c["operator"] == ">=":
            rating = round(spec_val * random.choice([1.0, 1.0, 1.05, 1.1]), 1)
        else:                         # "=" or "<=": meet the value exactly
            rating = spec_val
        if cid == "CL-4.2":
            rating = UPS_BAD_RATING   # PLANTED ERROR 1
        rating = int(rating) if float(rating).is_integer() else rating
        eq = c["equipment_id"]
        model = f"{vendor_of[eq].split()[0][:4].upper()}-{eq.split('-')[1]}-{rating}"
        subs.append((f"SUB-{i:03d}", eq, cid, model, rating, c["unit"]))
    write_csv("submittals.csv", ["submittal_id", "equipment_id", "clause_id", "model", "rating_value", "unit"], subs)

    # 4. tasks
    po_of = {task: po for task, _n, _e, po, _nb in DELIVERIES}
    tasks = []
    for task, name, eq, po, need_by in DELIVERIES:
        tasks.append((task, name, 5, "TASK-001", po, need_by))
    for task, name, dur, deps in OTHER_TASKS:
        tasks.append((task, name, dur, ";".join(deps), "", ""))
    tasks.sort(key=lambda t: t[0])
    write_csv("tasks.csv", ["task_id", "name", "duration_days", "depends_on", "linked_id", "need_by_date"], tasks)

    # 5. self-check of the planted errors (reads the files back)
    print("\nSelf-check of planted errors:")
    ups = next(s for s in subs if s[2] == "CL-4.2")
    spec = float(clauses["CL-4.2"]["value"])
    print(f"  1. {ups[1]} submittal {ups[4]} kW vs spec {spec:g} kW -> shortfall {spec - ups[4]:g} kW")
    chl = next(p for p in pos if p[1] == "EQ-CHL-01")
    need = d(next(x[4] for x in DELIVERIES if x[2] == "EQ-CHL-01"))
    print(f"  2. {chl[0]} promised {chl[4]} vs need-by {need} -> {(d(chl[4]) - need).days} days late")
    brk = next(s for s in subs if s[2] == "CL-4.10")
    print(f"  3. {brk[1]} submittal says {brk[4]} A (Member C's photo should show 400 A)")


if __name__ == "__main__":
    main()
