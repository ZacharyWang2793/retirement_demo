"""Graph state for the orchestrator."""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages

from ui.card_models import Card


class AgentState(TypedDict, total=False):
    customer_id: str
    thread_id: str
    # Canonical chat log. add_messages handles BaseMessage and dict inputs and merges by id.
    messages: Annotated[list, add_messages]
    intent: str | None
    intent_confidence: float | None
    routed_via: str | None                   # 'regex' | 'agent'
    routing_announcement: str | None         # one-shot message app.py mirrors into chat history
    current_step_idx: int                    # index into INTENT_PLANS[intent]
    plan_complete: bool                      # True when graph fell off the end (no plan)
    collected_data: dict[str, Any]
    verified: bool
    verified_at: str | None
    pending_card: Card | None
    last_submission: dict[str, Any] | None
    last_error: str | None
    final_message: str | None
    final_card: Card | None
    proposed_intent: str | None       # intent proposed but not yet confirmed by user
