# Architecture: what we built (AI pipeline and reports)

```mermaid
flowchart LR
    PDF[Spec PDF<br/>data/spec.pdf] --> EXT[Requirement extraction<br/>Gemini · src/ai/extract.py]
    EXT --> REQ[(requirements.json<br/>25 clauses)]
    REQ --> DRAFT[Test drafting<br/>Gemini · src/ai/run_tests.py]
    DRAFT --> RULES[Level rules check<br/>rules/level_rules.json]
    RULES --> TESTS[(tests.json<br/>15 accepted)]
    REQ --> GRAPH[Graph and deviation checks<br/>src/graph/]
    TESTS --> GRAPH
    REQ --> XLS[Excel traceability matrix<br/>src/reports/traceability.py]
    TESTS --> XLS
    TESTS --> DOCX[Word test package<br/>src/reports/test_package.py]
    GRAPH --> QA[Cited Q and A<br/>src/ai/qa.py]
    REQ --> QA
    TESTS --> QA
    GRAPH --> APP[Streamlit app<br/>app.py]
    QA --> APP
    XLS --> APP
    DOCX --> APP
```

**Reading the diagram**

- Gemini is used in two places: reading the spec into structured requirements, and drafting one test per clause in batches.
- The level rules are plain code, not AI. A test is rejected if its lower-level test is missing for the same equipment or system.
- Every answer in Q and A names the clause or test IDs it came from. If the model cites an ID that isn't in the context, the cite list drops it.
- Cached results let the demo run without the live API.
