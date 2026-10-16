# Shared schema (agree on this on Day 1, then code against it)

## Node types and ID style

| Node | ID style | Key fields |
|---|---|---|
| Clause | CL-4.2 | text, value, unit, system, level, tier |
| Equipment | EQ-UPS-02 | type, system |
| PO | PO-017 | equipment_id, vendor, promised_date, lead_time_days |
| Submittal | SUB-009 | equipment_id, model, rating_value, unit |
| Test | T-L4-017 | clause_id, level, tier, steps, acceptance, reason, status |
| Task | TASK-031 | name, duration_days, depends_on, linked_ids |
| Photo | PH-03 | equipment_id, file, extracted_fields, confidence |

## Relationships

- Clause -REQUIRES-> Equipment
- Equipment -ORDERED_VIA-> PO
- Equipment -SUBMITTED_AS-> Submittal
- Clause -VERIFIED_BY-> Test
- Test -SCHEDULED_AS-> Task
- PO -GATES-> Task
- Task -DEPENDS_ON-> Task

## Levels

L1 factory and delivery, L2 installation, L3 start-up, L4 functional performance, L5 integrated systems.
Tier: "III" or "IV".

## Rules for everyone
- Use these exact IDs and field names. If something must change, update this file in a PR first.
- Cached AI outputs go in data/cache/*.json (committed to Git).
