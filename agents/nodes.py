"""Supervisor (orchestrator) node + shared helpers.

The supervisor's only jobs are: classify the user's intent (or chat / clarify /
decline), route the resolved intent to the OWNING category subagent, and track the
task ledger as subagents hand control back. It never executes workflow steps — that
lives in ``agents/category_agent.py``.

For unambiguous programmatic entry (tests), a pre-set ``intent`` short-circuits the
LLM and routes straight to its category. The OpenAI client + message helpers + the
step-progress counter here are also reused by the category agent.
"""
from __future__ import annotations

import json
import os
import re as _re
import sys
import uuid
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

load_dotenv()

from agents.categories import INTENT_TO_CATEGORY, category_node_name
from agents.intents import INTENT_LABELS, INTENT_PLANS
from agents.prompts import AGENT_SYSTEM_PROMPT
from agents.state import OrchestratorState


# ---------- confirmation detection helpers ----------

_CONFIRM_RE = _re.compile(
    r"\b(yes|yeah|yep|sure|ok|okay|go\s+ahead|proceed|start|do\s+it|absolutely|please)\b|"
    r"let'?s\s+(do|start|go)",
    _re.I,
)
_REJECT_RE = _re.compile(
    r'\b(no|nope|not\s+now|cancel|skip|never\s+mind|nevermind)\b',
    _re.I,
)


def _is_confirmation(text: str) -> bool:
    if "?" in text:
        return False
    return bool(_CONFIRM_RE.search(text)) and not bool(_REJECT_RE.search(text))


def _is_rejection(text: str) -> bool:
    return bool(_REJECT_RE.search(text))


# ---------- LLM tool definitions (OpenAI function schema) ----------

START_WORKFLOW_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "start_workflow",
        "description": (
            "Begin a structured retirement-account workflow. "
            "Use this when the user wants to perform a specific transaction "
            "(change address, add beneficiary, check balance, etc.). "
            "Do NOT use it for greetings, off-topic questions, or when the "
            "user is still figuring out what they want."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "intent_id": {
                    "type": "string",
                    "description": "The registered intent id. Must be exactly one of: "
                    + ", ".join(INTENT_PLANS.keys()),
                },
                "brief_reason": {
                    "type": "string",
                    "description": (
                        "One short, warm sentence shown to the user, e.g. "
                        "'I'll get you set up to update your address.'"
                    ),
                },
            },
            "required": ["intent_id", "brief_reason"],
        },
    },
}

PROPOSE_WORKFLOW_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "propose_workflow",
        "description": (
            "Use when the user asked a question AND implied a transaction intent. "
            "Answer their question first, then propose starting the workflow. "
            "Do NOT use for clear direct commands — use start_workflow instead. "
            "Never use for read-only intents (check_balance, view_transactions, check_request_status)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "intent_id": {
                    "type": "string",
                    "description": "The registered intent id. Must be exactly one of: "
                    + ", ".join(INTENT_PLANS.keys()),
                },
                "answer": {"type": "string", "description": "1–3 sentence answer to the user's question."},
                "proposal": {
                    "type": "string",
                    "description": (
                        "Short sentence proposing the action, e.g. "
                        "'Would you like me to start adding a beneficiary now?'"
                    ),
                },
            },
            "required": ["intent_id", "answer", "proposal"],
        },
    },
}


# ---------- Azure AI Foundry OpenAI client ----------

_openai_client_singleton: Optional[Any] = None


def _get_openai_client():
    """Lazy-build an OpenAI client pointed at the Azure AI Foundry endpoint."""
    global _openai_client_singleton
    if _openai_client_singleton is not None:
        return _openai_client_singleton
    from openai import OpenAI
    _openai_client_singleton = OpenAI(
        base_url=os.environ["AZURE_OPENAI_BASE_URL"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )
    return _openai_client_singleton


# ---------- message helpers ----------

def _last_user_text(messages: list) -> str:
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage):
            return m.content if isinstance(m.content, str) else str(m.content)
        if isinstance(m, dict) and m.get("role") == "user":
            return str(m.get("content", ""))
    return ""


def _to_openai_dicts(messages: list) -> list[dict]:
    """Convert state messages (mix of dicts and BaseMessages) to plain OpenAI API dicts."""
    out: list[dict] = []
    for m in messages or []:
        if isinstance(m, HumanMessage):
            out.append({"role": "user", "content": m.content or ""})
        elif isinstance(m, AIMessage):
            d: dict = {"role": "assistant", "content": m.content or ""}
            tc = m.additional_kwargs.get("tool_calls")
            if tc:
                d["tool_calls"] = tc
            out.append(d)
        elif isinstance(m, ToolMessage):
            out.append({"role": "tool", "content": m.content or "", "tool_call_id": m.tool_call_id})
        elif isinstance(m, SystemMessage):
            out.append({"role": "system", "content": m.content or ""})
        elif isinstance(m, dict):
            role = m.get("role")
            if role in ("user", "assistant", "system", "tool"):
                out.append({"role": role, "content": m.get("content", "")})
    return out


def _announcement(intent: str, *, reason: str = "") -> str:
    if reason:
        return reason
    label = INTENT_LABELS.get(intent, intent)
    return f"Sure, I'd be glad to help. Let's get started with {label.lower()}."


# ---------- step-progress counter (reused by the category agent) ----------

_INPUT_KINDS = {"verify", "collect", "confirm"}


def step_progress(plan: list[dict], state: dict, idx: int) -> tuple[int, int] | None:
    """(position, total) over the input-bearing, non-skipped steps of the active plan."""
    verified = state.get("verified")

    def visible(step: dict) -> bool:
        if step["kind"] not in _INPUT_KINDS:
            return False
        if step["kind"] == "verify" and verified:
            return False
        skip_if = step.get("skip_if")
        return not (skip_if and skip_if(state))

    visible_idxs = [i for i, s in enumerate(plan) if visible(s)]
    if idx not in visible_idxs or len(visible_idxs) < 2:
        return None
    return visible_idxs.index(idx) + 1, len(visible_idxs)


# ---------- supervisor task helpers ----------

def _open_task(intent: str, *, via: str, announce: str | None) -> dict[str, Any]:
    """Return state updates that open a task and route to its category agent."""
    cat = INTENT_TO_CATEGORY[intent]
    entry = {"task_id": uuid.uuid4().hex[:12], "intent": intent,
             "label": INTENT_LABELS.get(intent, intent), "status": "active"}
    return {
        "intent": None,
        "active_category": cat,
        "active_intent": intent,
        "route_to": category_node_name(cat),
        "task_ledger": [entry],
        "routing_announcement": announce,
        "routed_via": via,
        "proposed_intent": None,
        "last_handback": None,
    }


def _consume_handback(state: OrchestratorState, hb: dict) -> dict[str, Any]:
    """A subagent returned control. Update the ledger and decide what's next."""
    kind = hb.get("kind")
    ledger = state.get("task_ledger") or []
    active = next((e for e in ledger if e.get("status") == "active"), None)
    updates: dict[str, Any] = {
        "last_handback": None, "route_to": None,
        "active_category": None, "active_intent": None,
    }

    if kind == "pivot":
        new_intent = hb.get("new_intent")
        parked = {
            **(active or {}), "status": "parked",
            "resume_step_idx": hb.get("resume_step_idx", 0),
            "collected_data": hb.get("collected_data", {}),
            "label": hb.get("label") or (active or {}).get("label", ""),
        }
        opened = _open_task(new_intent, via="pivot", announce=(
            f"Sure, let's switch to {INTENT_LABELS.get(new_intent, new_intent).lower()}. "
            f"We can come back to {parked['label'].lower()} after."
        ))
        # ledger: upsert the parked entry + append the new active entry
        updates.update(opened)
        updates["task_ledger"] = [parked] + opened["task_ledger"]
        updates["parked_task"] = parked
        return updates

    if kind == "cancelled":
        if active:
            updates["task_ledger"] = [{**active, "status": "cancelled"}]
        return updates

    # completed
    if active:
        updates["task_ledger"] = [{**active, "status": "completed",
                                   "request_id": hb.get("request_id"),
                                   "summary": hb.get("label")}]
    parked = state.get("parked_task")
    if parked:
        updates["routing_announcement"] = (
            f"You still have {parked.get('label', 'a task').lower()} in progress. "
            "Want to pick it back up?"
        )
    return updates


# ---------- supervisor node ----------

def supervisor_node(state: OrchestratorState) -> dict[str, Any]:
    """Classify + route + track. See module docstring."""
    # ----- CASE A: a subagent handed control back -----
    hb = state.get("last_handback")
    if hb:
        return _consume_handback(state, hb)

    # ----- CASE B: pre-set intent fast-path (tests / programmatic entry) -----
    preset = state.get("intent")
    if preset and preset in INTENT_PLANS and not state.get("active_category"):
        return _open_task(preset, via="preset", announce=None)

    msgs = state.get("messages", []) or []
    last_user = _last_user_text(msgs)

    # ----- CASE C: a proposal is pending — confirm or reject -----
    proposed = state.get("proposed_intent")
    if proposed:
        if _is_confirmation(last_user):
            label = INTENT_LABELS.get(proposed, proposed)
            return _open_task(proposed, via="confirmed",
                              announce=f"Great, happy to help. Starting {label.lower()} now.")
        if _is_rejection(last_user):
            msg = AIMessage(content="No problem! Let me know if there's anything else I can help with.")
            return {"messages": [msg], "final_message": msg.content,
                    "proposed_intent": None, "route_to": None}
        # otherwise: user pivoted — clear the proposal and re-classify below

    # ----- CASE D: LLM classification -----
    if not os.environ.get("AZURE_OPENAI_API_KEY"):
        msg = AIMessage(content=(
            "I can help with retirement-account tasks like checking balance, changing "
            "address, or adding a beneficiary. What would you like to do?"
        ))
        return {"messages": [msg], "final_message": msg.content, "route_to": None}

    api_messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}] + _to_openai_dicts(msgs)
    try:
        completion = _get_openai_client().chat.completions.create(
            model=os.environ["AZURE_MODEL_DEPLOYMENT"],
            messages=api_messages,
            tools=[START_WORKFLOW_TOOL, PROPOSE_WORKFLOW_TOOL],
            tool_choice="auto",
            temperature=0.3,
        )
    except Exception as e:
        print(f"[supervisor] LLM call failed: {type(e).__name__}: {e}", file=sys.stderr)
        msg = AIMessage(content="Sorry, I'm having trouble connecting right now. Please try again.")
        return {"messages": [msg], "final_message": msg.content,
                "last_error": f"{type(e).__name__}: {e}", "route_to": None}

    choice = completion.choices[0]
    raw_msg = choice.message

    if choice.finish_reason == "tool_calls" and raw_msg.tool_calls:
        call = raw_msg.tool_calls[0]
        try:
            args = json.loads(call.function.arguments)
        except (json.JSONDecodeError, AttributeError, TypeError):
            args = {}
        tool_call_id = call.id
        tool_calls_meta = [{
            "id": call.id, "type": "function",
            "function": {"name": call.function.name, "arguments": call.function.arguments},
        }]

        # ----- propose_workflow -----
        if call.function.name == "propose_workflow":
            intent_id = args.get("intent_id", "")
            combined = f"{args.get('answer', '')}\n\n{args.get('proposal', '')}"
            ai_msg = AIMessage(content=combined, additional_kwargs={"tool_calls": tool_calls_meta})
            if intent_id not in INTENT_PLANS:
                tool_err = ToolMessage(content="error: unknown intent_id", tool_call_id=tool_call_id)
                return {"messages": [ai_msg, tool_err], "final_message": combined,
                        "proposed_intent": None, "route_to": None}
            tool_msg = ToolMessage(content=f"workflow_proposed:{intent_id}", tool_call_id=tool_call_id)
            return {"messages": [ai_msg, tool_msg], "final_message": combined,
                    "proposed_intent": intent_id, "route_to": None}

        # ----- start_workflow -----
        intent_id = args.get("intent_id", "")
        reason = args.get("brief_reason", "") or ""
        ai_msg = AIMessage(content=raw_msg.content or "", additional_kwargs={"tool_calls": tool_calls_meta})
        if intent_id not in INTENT_PLANS:
            tool_err = ToolMessage(content="error: unknown intent_id", tool_call_id=tool_call_id)
            apology = AIMessage(content=(
                "Hmm, I'm not sure how to do that. Could you tell me a bit more about what you'd like to update?"
            ))
            return {"messages": [ai_msg, tool_err, apology], "final_message": apology.content,
                    "proposed_intent": None, "route_to": None}
        tool_msg = ToolMessage(content=f"workflow_started:{intent_id}", tool_call_id=tool_call_id)
        opened = _open_task(intent_id, via="agent", announce=_announcement(intent_id, reason=reason))
        opened["messages"] = [ai_msg, tool_msg]
        opened["intent_confidence"] = None
        return opened

    # ----- plain text reply -----
    ai_msg = AIMessage(content=raw_msg.content or "")
    return {"messages": [ai_msg], "final_message": ai_msg.content,
            "proposed_intent": None, "route_to": None}


# ---------- routing edge ----------

def route_from_supervisor(state: OrchestratorState) -> str:
    return state.get("route_to") or "end"
