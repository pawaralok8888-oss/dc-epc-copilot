# Hours saved

_Generated 2026-10-22 18:00. System times are the median of 20 runs on a laptop, using cached AI results._

| Task | Manual (our estimate) | With our system (measured) | Hours saved | Speed-up |
| --- | --- | --- | --- | --- |
| Draft a test package and traceability matrix for one system | 16.0 h to 24.0 h | 123 ms | 20.0 h | over 10,000x |
| Find everything a spec or delivery change affects | 2.0 h to 4.0 h | 5 ms | 3.0 h | over 10,000x |
| Cross-check all submittals against spec values | 4.0 h to 6.0 h | under 1 ms | 5.0 h | over 10,000x |
| Compare nameplate photos with the approved submittals | 30 min to 1.0 h | 1 ms | 0.7 h | over 10,000x |
| **Total (one pass of each task)** | | | **28.7 h** | |

**Read this honestly**

- Manual times are **our own estimates** (basis in `docs/manual_estimates.json`), not measured data.
- Hours saved uses the midpoint of the manual range.
- System times come from cached AI results. Where live Claude time was logged, it is included in the test-package row.
- The nameplate check is mainly about catching errors earlier, before equipment is installed, so hours saved understates its value.

**What each system time covers**

- Draft a test package and traceability matrix for one system: from cached AI results
- Find everything a spec or delivery change affects: blast radius + 1,000-run delay simulation
- Cross-check all submittals against spec values: all submittals vs all clauses
- Compare nameplate photos with the approved submittals: from cached vision results
