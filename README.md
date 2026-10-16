# DC-EPC Copilot

AI Knowledge Graph for Data Centre EPC project delivery.
One connected graph links spec clauses, equipment, POs, submittals, tests and schedule tasks.
On top of it: a Spec-to-Test Compiler, Change Blast-Radius with delay estimate,
and Reality Delta (photo vs approved design). All AI output is a draft for engineer approval.

## Quick start (Ubuntu / WSL)

    git clone git@github.com:<owner>/dc-epc-copilot.git
    cd dc-epc-copilot
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env        # then add your ANTHROPIC_API_KEY
    streamlit run app.py

## Folder ownership

| Folder | Owner | Branch |
|---|---|---|
| data/, src/graph/, tests/ | Member A (Data and Graph) | feature/graph |
| src/ai/, src/reports/, rules/ | Member B (AI pipeline) | feature/ai |
| src/vision/, src/common/, app.py | Member C (Vision and App) | feature/app |

## Notes
- The project data is synthetic, with deliberately planted errors.
- AI results are cached in data/cache/ so the demo runs without live API calls.
- Shared data format: see docs/schema.md
