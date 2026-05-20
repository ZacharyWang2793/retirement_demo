"""LangGraph nodes.

The graph:
    agent_node ─→ (text reply) ─→ END
                ─→ (tool call)  ─→ plan_steps ─→ render_step ─→ await_input ─→ validate_step
                                                                              ─→ persist_step
                                                                              ─→ END (with success card)

`agent_node` is the conversational entry point. It uses the Azure AI Foundry
OpenAI client (via DefaultAzureCredential — no API key required) with a single
`start_workflow` function tool. For unambiguous transaction phrasings the
agent_node short-circuits via a regex prefilter, skipping the LLM entirely.
Everything from `plan_steps` onward is unchanged.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import interrupt

load_dotenv()

import re as _re

from agents.intents import (
    INTENT_LABELS,
    INTENT_PLANS,
    INTENT_SUCCESS_MESSAGES,
    INTENTS,
)
from agents.prompts import AGENT_SYSTEM_PROMPT
from agents.state import AgentState
from db.repository import Repository


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
    return bool(_CONFIRM_RE.search(text)) and not bool(_REJECT_RE.search(text))


def _is_rejection(text: str) -> bool:
    return bool(_REJECT_RE.search(text))


# ---------- start_workflow tool definition (OpenAI function schema) ----------

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
                    "description": (
                        "The registered intent id. Must be exactly one of: "
                        + ", ".join(INTENT_PLANS.keys())
                    ),
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
                    "description": (
                        "The registered intent id. Must be exactly one of: "
                        + ", ".join(INTENT_PLANS.keys())
                    ),
                },
                "answer": {
                    "type": "string",
                    "description": "1–3 sentence answer to the user's question.",
                },
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


# ---------- helpers ----------

def _last_user_text(messages: list) -> str:
    """Extract the most recent user message's text, regardless of dict/BaseMessage form."""
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


def _announcement(intent: str, routed_via: str, confidence: float | None, *, reason: str = "") -> str:
    """Return the assistant's intro message for a workflow start."""
    if reason:
        return reason
    label = INTENT_LABELS.get(intent, intent)
    return f"I'll help you with that — starting {label.lower()} now."


# ---------- agent_node ----------

def agent_node(state: AgentState) -> dict[str, Any]:
    """Conversational LLM agent.

    Outcomes:
    - proposed_intent + confirmation → set intent, route to plan_steps
    - LLM start_workflow tool call   → set intent, route to plan_steps
    - LLM propose_workflow tool call → set proposed_intent, route to END
    - LLM plain text reply           → append to messages + final_message, route to END
    """
    msgs = state.get("messages", []) or []
    last_user = _last_user_text(msgs)

    # ----- Step 0: proposed-intent pending — check if user is confirming or rejecting -----
    proposed = state.get("proposed_intent")
    if proposed:
        if _is_confirmation(last_user):
            label = INTENT_LABELS.get(proposed, proposed)
            return {
                "intent": proposed,
                "proposed_intent": None,
                "intent_confidence": 1.0,
                "routed_via": "confirmed",
                "routing_announcement": f"Great — starting {label.lower()} now.",
            }
        elif _is_rejection(last_user):
            msg = AIMessage(content="No problem! Let me know if there's anything else I can help with.")
            return {"messages": [msg], "final_message": msg.content, "proposed_intent": None}
        # User pivoted to something new — clear the proposal and re-classify normally.

    # ----- LLM classification -----
    if not os.environ.get("AZURE_OPENAI_API_KEY"):
        msg = AIMessage(content=(
            "I can help with retirement-account tasks like checking balance, changing "
            "address, or adding a beneficiary. What would you like to do?"
        ))
        return {"messages": [msg], "final_message": msg.content}

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
        print(f"[agent_node] LLM call failed: {type(e).__name__}: {e}", file=sys.stderr)
        msg = AIMessage(content="Sorry, I'm having trouble connecting right now. Please try again.")
        return {
            "messages": [msg],
            "final_message": msg.content,
            "last_error": f"{type(e).__name__}: {e}",
        }

    choice = completion.choices[0]
    raw_msg = choice.message

    # ----- Tool call branch -----
    if choice.finish_reason == "tool_calls" and raw_msg.tool_calls:
        call = raw_msg.tool_calls[0]
        try:
            args = json.loads(call.function.arguments)
        except (json.JSONDecodeError, AttributeError):
            args = {}
        tool_call_id = call.id

        tool_calls_meta = [
            {"id": call.id, "type": "function",
             "function": {"name": call.function.name, "arguments": call.function.arguments}}
        ]

        # ----- propose_workflow branch -----
        if call.function.name == "propose_workflow":
            intent_id = args.get("intent_id", "")
            answer = args.get("answer", "")
            proposal = args.get("proposal", "")
            combined = f"{answer}\n\n{proposal}"
            ai_msg = AIMessage(
                content=combined,
                additional_kwargs={"tool_calls": tool_calls_meta},
            )
            if intent_id not in INTENT_PLANS:
                tool_err = ToolMessage(content="error: unknown intent_id", tool_call_id=tool_call_id)
                return {"messages": [ai_msg, tool_err], "final_message": combined, "proposed_intent": None}
            tool_msg = ToolMessage(content=f"workflow_proposed:{intent_id}", tool_call_id=tool_call_id)
            return {
                "messages": [ai_msg, tool_msg],
                "final_message": combined,
                "proposed_intent": intent_id,
            }

        # ----- start_workflow branch -----
        intent_id = args.get("intent_id", "")
        reason = args.get("brief_reason", "") or ""

        # Store the assistant turn with its tool_calls metadata for future context.
        ai_msg = AIMessage(
            content=raw_msg.content or "",
            additional_kwargs={"tool_calls": tool_calls_meta},
        )

        if intent_id not in INTENT_PLANS:
            tool_err = ToolMessage(content="error: unknown intent_id", tool_call_id=tool_call_id)
            apology = AIMessage(content=(
                "Hmm, I'm not sure how to do that. Could you tell me a bit more about what you'd like to update?"
            ))
            return {
                "messages": [ai_msg, tool_err, apology],
                "final_message": apology.content,
                "proposed_intent": None,
            }

        tool_msg = ToolMessage(content=f"workflow_started:{intent_id}", tool_call_id=tool_call_id)
        return {
            "messages": [ai_msg, tool_msg],
            "intent": intent_id,
            "proposed_intent": None,
            "intent_confidence": None,
            "routed_via": "agent",
            "routing_announcement": _announcement(intent_id, "agent", None, reason=reason),
        }

    # ----- Plain text reply branch -----
    ai_msg = AIMessage(content=raw_msg.content or "")
    return {
        "messages": [ai_msg],
        "final_message": ai_msg.content,
        "proposed_intent": None,
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

    # Conditional skip — any step can declare a skip_if(state) predicate.
    skip_if = step.get("skip_if")
    if skip_if and skip_if(state):
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

def route_from_start(state: AgentState) -> str:
    """If the caller pre-set an intent (e.g. in tests), skip agent_node entirely."""
    return "plan_steps" if state.get("intent") else "agent_node"


def route_after_agent(state: AgentState) -> str:
    return "plan_steps" if state.get("intent") else "end"


def route_after_render(state: AgentState) -> str:
    plan = _current_plan(state)
    idx = state.get("current_step_idx", 0)
    if idx >= len(plan) or state.get("plan_complete"):
        return "end"
    step = plan[idx]
    # Conditional skip — loop back to render_step to advance past this step.
    skip_if = step.get("skip_if")
    if skip_if and skip_if(state):
        return "render_step"
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
