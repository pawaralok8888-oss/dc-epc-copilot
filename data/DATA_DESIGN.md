# Data design for Member A (Day 1)

Files already provided in this folder:
- `spec.pdf`  the synthetic spec (25 clauses, power and cooling). Member B extracts requirements from this.
- `spec_ground_truth.csv`  the correct answer for every clause. Use it to build your submittals and to check Member B's extraction later.

Files YOU write (via `make_data.py`): `equipment.csv`, `pos.csv`, `submittals.csv`, `tasks.csv`, and `expected_results.txt`.

## 1. Equipment (11 items, IDs match the spec)

| equipment_id | type | system |
|---|---|---|
| EQ-SWG-01 | Main LV switchgear | power |
| EQ-UPS-02 | UPS module | power |
| EQ-BAT-02 | UPS battery system | power |
| EQ-GEN-01 | Standby diesel generator | power |
| EQ-ATS-01 | Automatic transfer switch | power |
| EQ-BRK-05 | Main feeder circuit breaker | power |
| EQ-PDU-01 | Power distribution unit | power |
| EQ-CHL-01 | Water-cooled chiller | cooling |
| EQ-PMP-01 | Chilled water pump | cooling |
| EQ-CT-01 | Cooling tower | cooling |
| EQ-CRAH-01 | CRAH unit | cooling |

## 2. The three planted errors (exact numbers to build in)

1. **Wrong UPS rating.** Clause CL-4.2 requires UPS-02 >= 500 kW. Its submittal must say **400 kW**. Expected detection: deviation, 100 kW (20 %) below spec.
2. **Late chiller delivery.** TASK-010 (chiller delivery) needs the chiller by **2027-04-15**. The chiller PO (PO for EQ-CHL-01) must have `promised_date` **2027-06-01**. Expected detection: delivery is **47 days late**, and every task that depends on TASK-010 slips by up to 47 days.
3. **Wrong breaker in a photo (Member C's part).** CL-4.10 requires BRK-05 = 630 A. Your BRK-05 submittal must correctly say **630 A**. Member C makes the nameplate photo for BRK-05 show **400 A**. Tell Member C this number.

All other submittals should meet or beat the spec value (for ">=" clauses use the spec value or higher, for "<=" clauses the spec value or lower).

## 3. Suggested CSV columns

| File | Columns |
|---|---|
| equipment.csv | equipment_id, type, system |
| pos.csv | po_id, equipment_id, vendor, order_date, promised_date, lead_time_days |
| submittals.csv | submittal_id, equipment_id, clause_id, model, rating_value, unit |
| tasks.csv | task_id, name, duration_days, depends_on, linked_id, need_by_date |

- Use `;` between several IDs in `depends_on` (for example `TASK-011;TASK-012`).
- `linked_id` is the PO or equipment the task waits for (for example `PO-003` on a delivery task).
- IDs: `PO-001`, `SUB-001`, `TASK-001` and so on, as in docs/schema.md.
- Make up vendor and model names (Faker or by hand). Keep dates in 2027, format `YYYY-MM-DD`.

## 4. Example task chain (so the delay can flow through)

```
TASK-010 Chiller delivery        (linked_id = PO of EQ-CHL-01, need_by 2027-04-15)
  -> TASK-011 Chiller installation
  -> TASK-012 Chilled water piping connection
  -> TASK-013 Chiller start-up (L3)
  -> TASK-014 Cooling functional test (L4)
  -> TASK-015 Integrated systems test (L5)
```

Do a similar (shorter) chain for the UPS, and a few independent chains (generator, switchgear, CRAH) plus shared tasks such as "Integrated systems test", which should depend on both the cooling chain and the power chain. Aim for about 30 to 40 tasks in total.

## 5. Two schema additions to agree with Members B and C today

1. **Clause: add `operator`** (`>=`, `<=`, `=`). The deviation check needs it, because "not less than" and "not more than" compare in opposite directions. It is already in spec_ground_truth.csv.
2. **Submittal: add `clause_id`**, the clause its rating answers. Without it, the check cannot tell which clause a rating belongs to.

Update docs/schema.md once all three agree.

## 6. Your Day 1 checklist

- [ ] Put spec.pdf, spec_ground_truth.csv and this file into `data/`
- [ ] Agree the two schema additions above with B and C, and update docs/schema.md
- [ ] Write `data/make_data.py` that creates the four CSVs
- [ ] Plant errors 1 and 2 (and tell Member C the BRK-05 number for error 3)
- [ ] Write `data/expected_results.txt` listing what the system must detect for each error
- [ ] Commit, push, open a Pull Request, tag day-1
