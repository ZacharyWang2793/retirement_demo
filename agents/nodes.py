"""LangGraph nodes.

The graph:
    agent_node ─→ (text reply) ─→ END
                ─→ (tool call)  ─→ plan_steps ─→ render_step ─→ await_input ─→ validate_step
                                                                              ─→ persist_step
                                                                              ─→ END (with success card)

`agent_node` is the conversational entry point: a ChatOpenAI(gpt-4o) with one
tool (`start_workflow`). For unambiguous transaction phrasings the agent_node
short-circuits via a regex prefilter, skipping the LLM entirely. Everything from
`plan_steps` onward is unchanged from the original router-first design.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.types import interrupt

load_dotenv()

from agents.intents import (
    INTENT_LABELS,
    INTENT_PLANS,
    INTENT_SUCCESS_MESSAGES,
    INTENTS,
    regex_classify,
)
from agents.prompts import AGENT_SYSTEM_PROMPT
from agents.state import AgentState
from db.repository import Repository


# ---------- the one tool the agent has ----------

@tool
def start_workflow(intent_id: str, brief_reason: str) -> str:
    """Begin a structured retirement-account workflow.

    Use this when the user wants to perform a specific transaction
    (change address, add beneficiary, check balance, etc.).
    Do NOT use it for greetings, off-topic questions, or when the
    user is still figuring out what they want.

    Args:
        intent_id: One of the registered intent ids (e.g. "change_address",
            "check_balance", "add_beneficiary"). Must match the catalog exactly.
        brief_reason: One short, warm sentence shown to the user as the agent's
            framing for the workflow, e.g. "I'll get you set up to update your address."
    """
    return f"workflow_started:{intent_id}"


# ---------- agent LLM (gpt-4o) ----------

_agent_llm_singleton: Optional[Any] = None


def _get_agent_llm():
    """Lazy-build ChatOpenAI bound with the start_workflow tool."""
    global _agent_llm_singleton
    if _agent_llm_singleton is not None:
        return _agent_llm_singleton
    from langchain_openai import ChatOpenAI
    model_id = os.environ.get("MODEL", "gpt-4o")
    llm = ChatOpenAI(model=model_id, temperature=0.3)
    _agent_llm_singleton = llm.bind_tools([start_workflow])
    return _agent_llm_singleton


# ---------- helpers ----------

def _last_user_text(messages: list) -> str:
    """Extract the most recent user message's text, regardless of dict/BaseMessage form."""
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage):
            return m.content if isinstance(m.content, str) else str(m.content)
        if isinstance(m, dict) and m.get("role") == "user":
            return str(m.get("content", ""))
    return ""


def _coerce_messages(messages: list) -> list[BaseMessage]:
    """Convert mixed dicts and BaseMessages into BaseMessage objects for LLM input."""
    out: list[BaseMessage] = []
    for m in messages or []:
        if isinstance(m, BaseMessage):
            out.append(m)
        elif isinstance(m, dict):
            role = m.get("role")
            content = m.get("content", "")
            if role == "user":
                out.append(HumanMessage(content=content))
            elif role == "assistant":
                out.append(AIMessage(content=content))
            elif role == "system":
                out.append(SystemMessage(content=content))
    return out


def _announcement(intent: str, routed_via: str, confidence: float | None, *, reason: str = "") -> str:
    label = INTENT_LABELS.get(intent, intent)
    plan = INTENT_PLANS.get(intent, [])
    n_steps = len(plan)
    if routed_via == "regex":
        provenance = "matched via keyword pattern (no LLM call)"
    else:
        model_id = os.environ.get("MODEL", "gpt-4o")
        if confidence is None:
            provenance = f"routed by `{model_id}`"
        else:
            provenance = f"classified by `{model_id}` (confidence {confidence:.0%})"

    if reason:
        head = f"{reason}\n\n_{provenance}._"
    else:
        head = f"Understood — **{label}**. _{provenance}._"
    return f"{head}\n\nI've drafted a {n_steps}-step plan. Walking you through it now."


# ---------- agent_node (replaces route_intent) ----------

def agent_node(state: AgentState) -> dict[str, Any]:
    """Conversational LLM agent.

    Outcomes:
    - regex fast-path hit → set state.intent, route to plan_steps
    - LLM tool call       → set state.intent + framing, route to plan_steps
    - LLM text reply      → append to messages + final_message, route to END
    """
    msgs = state.get("messages", []) or []
    last_user = _last_user_text(msgs)

    # ----- Tier 1: regex fast-path for unambiguous phrasings -----
    fast = regex_classify(last_user)
    if fast and fast in INTENT_PLANS:
        return {
            "intent": fast,
            "intent_confidence": 1.0,
            "routed_via": "regex",
            "routing_announcement": _announcement(fast, "regex", 1.0),
        }

    # ----- Tier 2: ChatOpenAI(gpt-4o).bind_tools([start_workflow]) -----
    if not os.environ.get("OPENAI_API_KEY"):
        # No key configured — fall back to a polite static reply.
        msg = AIMessage(content=(
            "I can help with retirement-account tasks like checking balance, changing "
            "address, or adding a beneficiary. What would you like to do?"
        ))
        return {"messages": [msg], "final_message": msg.content}

    chat_input: list[BaseMessage] = [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + _coerce_messages(msgs)

    try:
        response: AIMessage = _get_agent_llm().invoke(chat_input)
    except Exception as e:
        import sys
        print(f"[agent_node] LLM call failed: {type(e).__name__}: {e}", file=sys.stderr)
        msg = AIMessage(content="Sorry, I'm having trouble connecting right now. Please try again.")
        return {
            "messages": [msg],
            "final_message": msg.content,
            "last_error": f"{type(e).__name__}: {e}",
        }

    # ----- Tool call branch -----
    tool_calls = getattr(response, "tool_calls", None) or []
    if tool_calls:
        call = tool_calls[0]
        args = call.get("args", {}) or {}
        intent_id = args.get("intent_id")
        reason = args.get("brief_reason", "") or ""
        tool_call_id = call.get("id", "")

        if intent_id not in INTENT_PLANS:
            # LLM hallucinated an unknown intent. Acknowledge the tool, ask user to clarify.
            tool_msg = ToolMessage(content="error: unknown intent_id", tool_call_id=tool_call_id)
            apology = AIMessage(content=(
                "Hmm, I'm not sure how to do that. Could you tell me a bit more about what you'd like to update?"
            ))
            return {
                "messages": [response, tool_msg, apology],
                "final_message": apology.content,
            }

        tool_msg = ToolMessage(content=f"workflow_started:{intent_id}", tool_call_id=tool_call_id)
        return {
            "messages": [response, tool_msg],
            "intent": intent_id,
            "intent_confidence": None,
            "routed_via": "agent",
            "routing_announcement": _announcement(intent_id, "agent", None, reason=reason),
        }

    # ----- Plain text reply branch -----
    return {
        "messages": [response],
        "final_message": response.content,
    }


# ---------- plan_steps ----------

def plan_steps(state: AgentState) -> dict[str, Any]:
    intent = state.get("intent")
    if not intent or intent not in INTENT_PLANS:
        # Should never happen — agent_node only routes here when intent is set + valid.
        return {"plan_complete": True}
    return {
        "intent": intent,
        "current_step_idx": 0,
        "collected_data": {},
        "last_error": None,
        "plan_complete": False,
    }


def _current_plan(state: AgentState):
    intent = state.get("intent")
    if not intent or intent not in INTENT_PLANS:
        return []
    return INTENT_PLANS[intent]


# ---------- workflow loop nodes (unchanged) ----------

def render_step(state: AgentState, repo: Repository) -> dict[str, Any]:
    """Build the card for the current step and stash it in state.

    Skips steps that are already verified (when requires_verified=False but step is a verify-step
    and state.verified is True).
    """
    plan = _current_plan(state)
    idx = state.get("current_step_idx", 0)
    if idx >= len(plan):
        return {"plan_complete": True, "pending_card": None}
    step = plan[idx]

    # If we've already verified earlier in this session, skip verify steps
    if step["kind"] == "verify" and state.get("verified"):
        return {"current_step_idx": idx + 1, "pending_card": None}

    # Inform-only steps with a card factory: render and end (no interrupt below).
    if step["kind"] == "inform":
        card = step["card_factory"](state, repo) if step["card_factory"] else None
        return {
            "pending_card": card,
            "final_message": INTENT_SUCCESS_MESSAGES.get(state.get("intent", ""), ""),
            "final_card": card,
        }

    # Collect/confirm/verify steps: build card, will be interrupted in await_input.
    factory = step["card_factory"]
    card = factory(state, repo) if factory else None
    if card is None:
        # Persist step has no card; route to persist.
        return {"pending_card": None}

    if state.get("last_error"):
        try:
            card = card.model_copy(update={"error": state["last_error"]})
        except Exception:
            pass

    return {"pending_card": card, "last_error": None}


def await_input(state: AgentState) -> dict[str, Any]:
    """Pause the graph until app.py supplies a Command(resume=...)."""
    payload = state.get("pending_card")
    if payload is None:
        return {"last_submission": {}}
    payload_dump = payload.model_dump() if hasattr(payload, "model_dump") else payload
    submission = interrupt(payload_dump)
    return {"last_submission": submission}


def validate_step(state: AgentState, repo: Repository) -> dict[str, Any]:
    """Run the current step's validator. On failure, set last_error so render_step re-renders the same card.
    On success, run the collector and advance current_step_idx."""
    plan = _current_plan(state)
    idx = state.get("current_step_idx", 0)
    step = plan[idx]
    submission = state.get("last_submission") or {}

    if submission.get("_cancelled"):
        return {
            "intent": None,
            "current_step_idx": 0,
            "plan_complete": True,
            "pending_card": None,
            "final_message": "Got it — I've cancelled that. What would you like to do instead?",
            "final_card": None,
            "last_error": None,
        }

    validator = step.get("validator")
    if validator:
        err = validator(submission, state, repo)
        if err:
            return {"last_error": err, "last_submission": None}

    updates: dict[str, Any] = {}
    if step["kind"] == "verify" and step["name"] == "otp":
        updates["verified"] = True

    collector = step.get("collector")
    if collector:
        new_data = collector(submission, state)
        merged = dict(state.get("collected_data") or {})
        merged.update(new_data)
        updates["collected_data"] = merged

    updates["current_step_idx"] = idx + 1
    updates["pending_card"] = None
    updates["last_error"] = None
    updates["last_submission"] = None
    return updates


def persist_step(state: AgentState, repo: Repository) -> dict[str, Any]:
    """Run the current step's persister, advance idx."""
    plan = _current_plan(state)
    idx = state.get("current_step_idx", 0)
    step = plan[idx]
    persister = step.get("persister")
    updates: dict[str, Any] = {"current_step_idx": idx + 1}
    if persister:
        result = persister(state, repo)
        merged = dict(state.get("collected_data") or {})
        merged.update(result)
        updates["collected_data"] = merged
    return updates


# ---------- routing edges ----------

def route_after_agent(state: AgentState) -> str:
    return "plan_steps" if state.get("intent") else "end"


def route_after_render(state: AgentState) -> str:
    plan = _current_plan(state)
    idx = state.get("current_step_idx", 0)
    if idx >= len(plan) or state.get("plan_complete"):
        return "end"
    step = plan[idx]
    if step["kind"] == "inform":
        return "end"
    if step["kind"] == "persist":
        return "persist_step"
    if state.get("pending_card") is None:
        return "render_step"
    return "await_input"


def route_after_validate(state: AgentState) -> str:
    if state.get("last_error"):
        return "render_step"
    if state.get("plan_complete"):
        return "end"
    plan = _current_plan(state)
    idx = state.get("current_step_idx", 0)
    if idx >= len(plan):
        return "end"
    return "render_step"


def route_after_persist(state: AgentState) -> str:
    plan = _current_plan(state)
    idx = state.get("current_step_idx", 0)
    if idx >= len(plan):
        return "end"
    return "render_step"
