"""Graph state for the supervisor orchestrator.

Two TypedDicts model the two altitudes of the system:

- ``OrchestratorState`` — the top-level graph. Owns the user-facing conversation,
  the task ledger, the overall ask, and routing. This is what ``app.py`` and the
  checkpointer see at the parent level.
- ``CategoryAgentState`` (in ``agents/category_state.py``) — the per-category
  subagent subgraph. It SHARES a handful of channels with the parent (by using the
  same key name) so a card raised inside a subagent surfaces upward, while keeping
  its own private scratchpad (``cat_messages``) and working state.

The shared-by-name channels are the contract between the two altitudes; keep their
names identical in both TypedDicts.
"""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages

from ui.card_models import Card


# ---------- task ledger ----------

class TaskLedgerEntry(TypedDict, total=False):
    task_id: str
    intent: str
    label: str
    status: str                  # 'active' | 'completed' | 'parked' | 'cancelled'
    summary: str                 # subagent-written one-liner on completion/park
    resume_step_idx: int         # saved step position for a parked task
    collected_data: dict[str, Any]   # saved working data for a parked task
    request_id: str | None       # populated if the task persisted a mutation


def _ledger_reducer(existing: list | None, update: Any) -> list:
    """Upsert ledger entries by task_id (append new, merge existing).

    Only the supervisor writes the ledger, but using an upsert reducer keeps it
    robust if a node returns a single entry or a partial update for an existing one.
    """
    out = list(existing or [])
    if not update:
        return out
    entries = update if isinstance(update, list) else [update]
    index = {e.get("task_id"): i for i, e in enumerate(out) if isinstance(e, dict)}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        tid = entry.get("task_id")
        if tid in index:
            out[index[tid]] = {**out[index[tid]], **entry}
        else:
            out.append(entry)
            index[tid] = len(out) - 1
    return out


# ---------- top-level orchestrator state ----------

class OrchestratorState(TypedDict, total=False):
    customer_id: str
    thread_id: str
    # Canonical user<->orchestrator chat log (subagent reasoning is NOT merged here).
    messages: Annotated[list, add_messages]

    verified: bool
    verified_at: str | None

    # ----- routing / task tracking -----
    intent: str | None                       # input alias: a pre-set intent (tests / fast-path)
    intent_confidence: float | None
    routed_via: str | None                   # 'agent' | 'confirmed' | 'preset'
    active_category: str | None              # category_id currently delegated, else None
    active_intent: str | None                # SHARED with subagent — the live intent
    overall_goal: str | None                 # supervisor's running description of the ask
    task_ledger: Annotated[list[TaskLedgerEntry], _ledger_reducer]
    parked_task: TaskLedgerEntry | None      # most-recent parked task offered for resume
    route_to: str | None                     # one-shot: which cat_<id> node to enter, or None
    resume_payload: dict[str, Any] | None    # SHARED — rehydrates a resumed parked task

    # ----- bridge / one-shot channels (SHARED by name with CategoryAgentState) -----
    pending_card: Card | None
    final_card: Card | None
    final_message: str | None
    routing_announcement: str | None         # mirrored into chat history by app.py
    assistant_say: str | None                # inline subagent reply mirrored into chat history
    proposed_intent: str | None              # intent proposed but not yet confirmed
    last_handback: dict[str, Any] | None     # SHARED — subagent → supervisor return signal

    last_error: str | None


# Backwards-compatible alias for any lingering imports.
AgentState = OrchestratorState
