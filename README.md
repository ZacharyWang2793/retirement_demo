# Retirement Account Support — Agent Prototype

An agent-powered customer support experience for a retirement account. The orchestrator classifies the user's intent, generates a step plan, and emits interactive cards (forms, confirmations, read-only views) for the user to fill in.

Two frontends live in this repo:
- **`app.py`** — the original Streamlit chat (single-column message timeline)
- **`frontend/`** — a Next.js canvas where the LLM spawns draggable, grid-snapped cards in response to a small bottom chat bar (the canvas paradigm). Backed by **`backend/`** — a FastAPI service that wraps the same LangGraph

## Quickstart (Streamlit chat — original)

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

## Quickstart (Next.js canvas)

Two terminals — backend and frontend:

```bash
# Terminal 1 — FastAPI backend on :8000
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — Next.js frontend on :3000
cd frontend
npm install     # one-time
npm run dev
```

Then open http://localhost:3000. The frontend proxies `/api/*` to `localhost:8000`.

Requires Node 18+ for the frontend.

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

See [the plan file](../.claude/plans/i-want-to-build-encapsulated-aho.md) for the full design.

```
chat input  →  LangGraph orchestrator  →  card spec  →  Streamlit renders inline
                       ↑                                        ↓
                       └──────  Command(resume=form_data)  ─────┘
```

- `app.py` — Streamlit ↔ LangGraph interrupt bridge
- `agents/` — graph, nodes, intent registry, prompts
- `ui/` — card models (Pydantic) + per-card Streamlit renderers
- `backend/` — FastAPI service exposing the LangGraph as JSON + SSE endpoints
- `frontend/` — Next.js + React canvas (Phase 1: chat bar, balance view, allocation form, confirmation, success)
- `db/` — SQLite repository (only place mutating SQL lives); includes `canvas_sessions` table for saved canvases
- `data/` — schema and seed script
