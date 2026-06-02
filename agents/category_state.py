"""State for a per-category subagent subgraph.

Channels whose key name ALSO appears in ``OrchestratorState`` are SHARED with the
parent graph (langgraph maps same-named keys to the parent's channels when a
compiled subgraph is added directly as a node). Everything else is private to the
subagent and never pollutes the top-level conversation.

Empirically confirmed (langgraph 0.3.34): while the subagent is suspended at an
``interrupt()``, its shared-channel writes are NOT yet visible at the parent —
``app.py`` reads the pending card from ``snap.tasks`` instead. Once the subagent
node completes, its final shared writes (``final_card``/``final_message``/
``last_handback``) surface at the parent.
"""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages

from ui.card_models import Card


class CategoryAgentState(TypedDict, total=False):
    # ----- SHARED with parent (identical key names) -----
    customer_id: str
    thread_id: str
    verified: bool
    active_intent: str | None                # parent seeds it; subagent may switch (intra-category)
    resume_payload: dict[str, Any] | None    # parent injects {current_step_idx, collected_data} on resume
    pending_card: Card | None
    final_card: Card | None
    final_message: str | None
    assistant_say: str | None                # inline answer mirrored to the top-level chat
    last_handback: dict[str, Any] | None     # return signal to the supervisor

    # ----- PRIVATE to the subagent (names absent from OrchestratorState) -----
    cat_messages: Annotated[list, add_messages]   # isolated reasoning/dialogue scratchpad
    category_id: str
    current_step_idx: int
    collected_data: dict[str, Any]
    last_submission: dict[str, Any] | None
    last_error: str | None
    brain_turns: int                              # non-termination guard counter
    _brain_action: str | None                     # transient: brain → router signal
