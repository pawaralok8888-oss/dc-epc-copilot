# Pitch slides (draft)

## Slide 1: The problem
- Commissioning a data centre means checking hundreds of requirements against specs, drawings and test reports.
- Most of that work is manual: reading the spec, writing test steps, building traceability spreadsheets.
- Gaps are found late, when changing them is expensive.

## Slide 2: The vision
- The engineer keeps the decisions. The software does the reading, drafting and checking.
- Every requirement, test and result stays linked, so any answer can be traced back to its clause.

## Slide 3: What we built
- Extracts requirements from the spec into structured records (25 clauses from our sample spec).
- Drafts one test per requirement, checks each against level rules, and keeps the ones that pass (15 of 25 in this run).
- Exports an Excel traceability matrix and a Word test package from the same data.
- Answers questions with citations to clause and test IDs.
- Shows the results in a five-tab app, with a graph for deviations and schedule impact.

## Slide 4: How it stays honest
- The AI proposes; the rules and the engineer decide.
- Gaps are shown, not hidden: 10 clauses are listed as having no accepted test.
- Results are checked against a ground-truth answer key. Current result: all clause IDs and values match, and 18 of 25 clauses match on every field. Level labels are judgment calls, accepted within one step.

## Slide 5: Next steps
- Connect the live graph to every answer in the Q and A tab.
- Add engineer approval for each test and deviation, with a dated record.
- Test on a second, unseen spec before claiming general accuracy.
