# Retirement Account Support — Agent Prototype

An agent-powered customer support chat for a retirement account. The orchestrator agent classifies the user's intent, generates a step plan, and emits inline interactive cards (forms, confirmations, read-only views) inside the chat thread. The reference flow is *change address* — verify identity → collect new address → confirm diff → persist → success.

## Quickstart

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set AZURE_OPENAI_API_KEY (and AZURE_OPENAI_BASE_URL / AZURE_MODEL_DEPLOYMENT)

python -m data.seed
streamlit run app.py
```

Open the browser link Streamlit prints. Pick a demo customer in the sidebar.

## Demo customers (after `python -m data.seed`)

| ID         | Name             | DOB         | SSN last-4 | OTP      |
|------------|------------------|-------------|------------|----------|
| demo-001   | Margaret Chen    | 1965-04-12  | 6789       | `123456` |
| demo-002   | Tyler Rodriguez  | 1989-08-23  | 4321       | `123456` |
| demo-003   | Nina Patel       | 1996-11-04  | 1122       | `123456` |

## Demo prompts

- "I want to change my address" — full multi-step flow with verification
- "What's my balance?" — read-only, no verification
- "Add a beneficiary" — array-shaped data, multi-step
- "Update my contribution" — bounded numeric change
- "I want to roll over my 401k" — registered intent, stub card

## Architecture

A **supervisor + per-category-subagent** design on LangGraph. The supervisor classifies
intent and routes to one of **six category subagents** (one per retirement-account domain);
each subagent owns its domain knowledge, drives the workflow's validated steps, answers
in-domain questions, and hands back to the supervisor on a cross-category pivot. The LLM
drives the conversation; every mutation still runs through the deterministic, idempotent
repository. See **[ARCHITECTURE.md](ARCHITECTURE.md)** for diagrams and the full design.

```
chat input → supervisor → cat_<category> subagent → card spec → Streamlit renders inline
                  ↑               (interrupt)                          ↓
                  └────── hand back (ledger) ──── Command(resume=submission) ──────┘
```

- `app.py` — Streamlit ↔ LangGraph interrupt bridge (subgraph-aware)
- `agents/` — supervisor (`nodes.py`), category agents (`category_agent.py`), category
  registry (`categories.py`), graph wiring, intent step plans, prompts, state
- `ui/` — card models (Pydantic) + per-card Streamlit renderers
- `db/` — SQLite repository (only place mutating SQL lives)
- `data/` — schema and seed script
