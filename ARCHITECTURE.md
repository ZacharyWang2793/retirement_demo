# Architecture — Supervisor + Per-Category Subagents

The retirement-account assistant is a **hybrid multi-agent system** built on LangGraph.
A thin **supervisor** classifies intent and routes; **six category subagents** (one per
retirement-account domain) own the conversation and carry each task to completion. An LLM
drives the conversation, but every data mutation runs through the original validated,
idempotent building blocks — so money operations stay deterministic.

- **Supervisor (orchestrator)** — classify intent / chat / clarify / decline, route to the
  owning category agent, and track a task ledger + the overall ask.
- **Category agent** — owns its domain's intents and domain knowledge; walks each workflow's
  validated steps, answers in-domain questions, switches between sibling tasks, and hands
  back to the supervisor on a cross-category pivot.
- **Bridge** — Streamlit renders the interactive cards a subagent raises via `interrupt()`,
  and resumes the graph with the member's submission (or typed text).

## 1. System topology

```mermaid
flowchart TB
    User([Member]) <--> App["app.py — Streamlit bridge<br/>renders cards · resumes graph<br/>get_state(subgraphs=True)"]

    App <-->|"stream / Command(resume=…)"| SUP

    subgraph Graph["LangGraph state graph (SqliteSaver checkpoint)"]
        direction TB
        SUP{{"supervisor<br/>classify · route · track ledger"}}

        SUP -->|"route_to = cat_&lt;category&gt;"| PC["cat_profile_contact<br/>address · phone · email · name"]
        SUP --> BEN["cat_beneficiaries<br/>add · update/remove"]
        SUP --> AS["cat_account_status<br/>balance · transactions<br/>request status · cancel"]
        SUP --> INV["cat_investments<br/>contribution · allocation · rebalance"]
        SUP --> DIST["cat_distributions<br/>RMD · hardship · qualified<br/>rollover out/in · QDRO"]
        SUP --> TB["cat_tax_banking<br/>tax withholding · direct deposit"]

        PC -.->|"hand back (done / pivot)"| SUP
        BEN -.-> SUP
        AS -.-> SUP
        INV -.-> SUP
        DIST -.-> SUP
        TB -.-> SUP
    end

    SUP -->|"greet / answer / decline"| End([end turn])

    Repo[("db/repository.py<br/>only place mutating SQL lives<br/>idempotent writes")]
    PC & BEN & AS & INV & DIST & TB --> Repo
```

The supervisor resolves the **specific** intent (reusing the original `start_workflow` /
`propose_workflow` classification) and routes it to the agent that owns it via
`INTENT_TO_CATEGORY`. Each category agent is one reusable subgraph (`build_category_agent`)
parameterized by a `CategorySpec` — 6 specs, 21 intents.

## 2. Inside a category agent (the subgraph)

The deterministic spine (`present → await → validate → persist`, reused verbatim from the
original node logic) drives every form flow. The LLM **brain** is consulted only when the
member types free text while a card is showing — to answer, switch tasks, or cancel.

```mermaid
flowchart TB
    Start((start)) --> Init["cat_init<br/>seed / rehydrate task"]
    Init --> Gate{{"step_gate<br/>skip verified/skip_if steps"}}

    Gate -->|"input step"| Present["present_step<br/>build card (card_factory)"]
    Gate -->|"persist step"| Persist["run_persist<br/>persister → repository"]
    Gate -->|"inform / done"| Final["finalize<br/>success card + ledger handback"]

    Present --> Await["await_card<br/>interrupt() → card to UI"]
    Await -->|"form submission"| Validate["validate_apply<br/>validator → collector"]
    Await -->|"member typed text"| Brain{{"brain (LLM)<br/>answer · switch · cancel"}}
    Await -->|"cancel"| Final

    Validate -->|"valid"| Gate
    Validate -->|"error"| Present

    Persist --> Gate

    Brain -->|"answer / continue"| Present
    Brain -->|"switch to sibling intent"| Gate
    Brain -->|"pivot to other category / cancel"| Final

    Final --> Done((end → supervisor))
```

**Constraints that keep it safe:** the brain's action space is closed (answer / switch_task /
continue / cancel); it cannot fabricate or skip a validated write — `run_persist` is only
reached by the deterministic spine. A per-task **brain-turn budget** stops any runaway loop.
Validation errors re-render the same card deterministically (the brain is never asked to "fix"
form data).

## 3. A turn with a mid-flow question and a cross-category pivot

```mermaid
sequenceDiagram
    actor M as Member
    participant UI as app.py (Streamlit)
    participant S as supervisor
    participant PC as cat_profile_contact
    participant AS as cat_account_status
    participant DB as repository

    M->>UI: "change my address"
    UI->>S: classify
    S->>PC: route (active_intent=change_address)
    PC-->>UI: interrupt → address form
    M->>UI: (types) "what happens to my old address?"
    UI->>PC: resume {_user_text}
    Note over PC: brain → answer_question
    PC-->>UI: inline answer + re-show form
    M->>UI: (types) "actually, what's my balance?"
    UI->>PC: resume {_user_text}
    Note over PC: brain → switch_task(check_balance)<br/>cross-category → hand back (park)
    PC-->>S: handback {pivot, parked: change_address}
    S->>AS: route (active_intent=check_balance)
    AS->>DB: read balance
    AS-->>S: handback {completed}
    S-->>UI: balance card + "resume change address?"
    M->>UI: Resume
    UI->>S: re-open change_address (resume_payload)
    S->>PC: route (rehydrate step + data)
    PC-->>UI: interrupt → address form (where they left off)
```

## 4. Key design decisions

| Decision | Why |
|---|---|
| **Hybrid execution** (LLM drives, tools execute) | The LLM owns conversation/decisions; mutations go through the original validators + persisters + `repository`, so idempotency and validation are preserved byte-for-byte. |
| **6 category agents, not 21 per-workflow** | Fewer, smarter agents; domain knowledge grouped per domain; common in-domain follow-ups (address → phone) handled by one agent. |
| **Shared vs. private state channels** | `pending_card` / `final_card` / `verified` / `last_handback` are shared (same key name in both state schemas) so cards surface to the bridge; each agent's `cat_messages` scratchpad stays private, keeping the top-level conversation clean. |
| **Context at the right altitude** | Supervisor holds the user conversation + task ledger + overall ask; each subagent holds only its own task context. |
| **Nested-interrupt bridge** | While suspended inside a subgraph, the pending card is read from `snap.tasks` (it has not yet surfaced to the parent); `Command(resume=…)` is delivered to the interrupted subgraph node. |

## File map

| File | Role |
|---|---|
| `agents/graph.py` | Wires the supervisor + 6 category subgraph nodes; shared `SqliteSaver`. |
| `agents/nodes.py` | `supervisor_node` (classify · route · ledger) + shared LLM/message helpers. |
| `agents/categories.py` | The 6 `CategorySpec`s (domain prompts + member intents) + `INTENT_TO_CATEGORY`. |
| `agents/category_agent.py` | `build_category_agent` — the reusable subagent subgraph + brain. |
| `agents/state.py` / `agents/category_state.py` | `OrchestratorState` / `CategoryAgentState` (shared + private channels). |
| `agents/intents.py` | Per-intent step plans + card factories / validators / collectors / persisters (reused). |
| `app.py` | Streamlit ↔ LangGraph bridge (subgraph-aware reads, resume, parked-task resume). |
| `ui/`, `db/`, `data/` | Card models + renderers, SQLite repository, schema + seed. |
```
