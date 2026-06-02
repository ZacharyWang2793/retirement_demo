"""Per-category subagent subgraph factory.

``build_category_agent(spec, repo)`` returns a compiled subgraph (no checkpointer of
its own — it inherits the parent graph's saver when nested) that owns one domain's
intents. The deterministic spine (present → await → validate → persist), lifted from
the original node logic, drives every form flow; an LLM "brain" is consulted only
when the member types free text while a card is up — to answer an in-domain question,
switch to a sibling task, hand off to another category, or cancel. Every data write
still goes through the reused validators/persisters, so mutations stay deterministic.

State machine (inside the subgraph):

    cat_init → step_gate ─(skip)→ step_gate
                        ├─(input)→ present_step → await_card ─(form)→ validate_apply → step_gate
                        │                                   ├─(text)→ brain ─→ present_step / step_gate / finalize
                        │                                   └─(cancel)→ finalize
                        ├─(persist)→ run_persist → step_gate
                        └─(inform / done)→ finalize → END
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agents.categories import INTENT_TO_CATEGORY, CategorySpec
from agents.category_state import CategoryAgentState
from agents.intents import INTENT_LABELS, INTENT_PLANS, INTENT_SUCCESS_MESSAGES
from db.repository import Repository

# Reused helpers from the supervisor module (LLM client + message conversion + step counter).
from agents.nodes import _get_openai_client, _to_openai_dicts, step_progress

# Hard cap on consecutive brain turns without forward progress (non-termination guard).
_MAX_BRAIN_TURNS = 6


# ---------- brain tool surface (constrained action catalog) ----------

def _brain_tools() -> list[dict]:
    intent_enum = list(INTENT_PLANS.keys())
    return [
        {
            "type": "function",
            "function": {
                "name": "answer_question",
                "description": (
                    "Answer the member's in-domain question warmly in 1-3 sentences. "
                    "The current form stays on screen so they can continue."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                    "required": ["answer"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "switch_task",
                "description": (
                    "The member wants to do a DIFFERENT task. Provide its intent id. "
                    "If it belongs to this category the switch happens here; otherwise "
                    "it is handed off to the right team."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"intent_id": {"type": "string", "enum": intent_enum}},
                    "required": ["intent_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "continue_task",
                "description": "The member wants to proceed with the current task. Re-show the current form.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "cancel_task",
                "description": "The member wants to stop the current task.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]


def _brain_system_prompt(spec: CategorySpec, state: CategoryAgentState) -> str:
    intent = state.get("active_intent")
    card = state.get("pending_card")
    card_title = getattr(card, "title", None) or "the current form"
    members = ", ".join(f"`{i}` ({INTENT_LABELS.get(i, i)})" for i in spec.member_intents)
    return (
        f"You are the {spec.label} specialist on a retirement-account support team. The member "
        f"is verified and currently working on: {INTENT_LABELS.get(intent, intent)}. "
        f'The form "{card_title}" is on screen, and the member typed a message instead of '
        f"submitting it. Decide how to respond.\n\n"
        f"{spec.system_prompt}\n\n"
        f"Tasks you personally handle: {members}.\n\n"
        "Guidance:\n"
        "- A question you can answer from the knowledge above -> answer_question (warm, brief). "
        "The form stays up so they can finish.\n"
        "- They want a different task -> switch_task with its intent id.\n"
        "- They're telling you to go ahead -> continue_task.\n"
        "- They want to stop -> cancel_task.\n"
        "Never invent account data or fill the form yourself. Never use em dashes."
    )


# ---------- plan helpers ----------

def _plan(spec: CategorySpec, state: CategoryAgentState) -> list[dict[str, Any]]:
    intent = state.get("active_intent")
    return spec.members.get(intent, []) if intent else []


def _is_skippable(step: dict, state: CategoryAgentState) -> bool:
    if step["kind"] == "verify" and state.get("verified"):
        return True
    skip_if = step.get("skip_if")
    return bool(skip_if and skip_if(state))


# ---------- nodes ----------

def _cat_init(state: CategoryAgentState, *, spec: CategorySpec) -> dict[str, Any]:
    """Seed working state for a fresh task, or rehydrate a resumed parked task."""
    rp = state.get("resume_payload") or {}
    updates: dict[str, Any] = {
        "category_id": spec.category_id,
        "brain_turns": 0,
        "last_error": None,
        "last_submission": None,
        "assistant_say": None,
        "current_step_idx": rp.get("current_step_idx", 0),
        "collected_data": dict(rp.get("collected_data") or {}),
    }
    if rp:
        updates["resume_payload"] = None
    return updates


def _step_gate(state: CategoryAgentState, *, spec: CategorySpec) -> dict[str, Any]:
    """Advance past one skippable step (verify-when-verified or skip_if). The router
    loops back here until the current step is actionable."""
    plan = _plan(spec, state)
    idx = state.get("current_step_idx", 0)
    if idx < len(plan) and _is_skippable(plan[idx], state):
        return {"current_step_idx": idx + 1}
    return {}


def _present_step(state: CategoryAgentState, *, repo: Repository, spec: CategorySpec) -> dict[str, Any]:
    """Build the card for the current (actionable) step. Reuses the step's card_factory."""
    plan = _plan(spec, state)
    idx = state.get("current_step_idx", 0)
    step = plan[idx]
    card = step["card_factory"](state, repo) if step.get("card_factory") else None
    updates: dict[str, Any] = {}
    if state.get("last_error"):
        updates["error"] = state["last_error"]
    prog = step_progress(plan, state, idx)
    if prog:
        updates["current_step"], updates["total_steps"] = prog
    if card is not None and updates:
        try:
            card = card.model_copy(update=updates)
        except Exception:
            pass
    return {"pending_card": card, "assistant_say": None}


def _await_card(state: CategoryAgentState) -> dict[str, Any]:
    """Pause until app.py supplies a Command(resume=...). The resume value is either a
    form submission dict, {'_user_text': ...} (typed in chat), or {'_cancelled': True}."""
    card = state.get("pending_card")
    payload = card.model_dump() if hasattr(card, "model_dump") else card
    submission = interrupt(payload)
    return {"last_submission": submission}


def _validate_apply(state: CategoryAgentState, *, repo: Repository, spec: CategorySpec) -> dict[str, Any]:
    """Run the step validator (error -> re-render same card, deterministically), then the
    collector, then advance. The brain is never consulted to fix form data."""
    plan = _plan(spec, state)
    idx = state.get("current_step_idx", 0)
    step = plan[idx]
    submission = state.get("last_submission") or {}

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
        merged = dict(state.get("collected_data") or {})
        merged.update(collector(submission, state))
        updates["collected_data"] = merged
    updates["current_step_idx"] = idx + 1
    updates["last_error"] = None
    updates["last_submission"] = None
    return updates


def _run_persist(state: CategoryAgentState, *, repo: Repository, spec: CategorySpec) -> dict[str, Any]:
    """Run the step persister (the sole, idempotent mutation path) and advance."""
    plan = _plan(spec, state)
    idx = state.get("current_step_idx", 0)
    step = plan[idx]
    updates: dict[str, Any] = {"current_step_idx": idx + 1}
    persister = step.get("persister")
    if persister:
        merged = dict(state.get("collected_data") or {})
        merged.update(persister(state, repo))
        updates["collected_data"] = merged
    return updates


def _brain(state: CategoryAgentState, *, spec: CategorySpec) -> dict[str, Any]:
    """LLM turn — only reached when the member typed free text mid-flow. Decides
    answer / switch_task / continue / cancel via a constrained tool surface."""
    sub = state.get("last_submission") or {}
    user_text = sub.get("_user_text", "") if isinstance(sub, dict) else ""
    turns = state.get("brain_turns", 0) + 1

    # Non-termination guard: too many brain turns without progress -> stop the task.
    if turns > _MAX_BRAIN_TURNS:
        return {"brain_turns": turns, "_brain_action": "cancel",
                "last_submission": None,
                "last_handback": {"kind": "cancelled", "reason": "too_many_turns"}}

    convo = list(state.get("cat_messages") or []) + [HumanMessage(content=user_text)]

    # Fallback when no LLM is configured: keep the member moving, don't lose the task.
    if not os.environ.get("AZURE_OPENAI_API_KEY"):
        return {
            "brain_turns": turns,
            "cat_messages": [HumanMessage(content=user_text),
                             AIMessage(content="Let me bring that form back up for you.")],
            "assistant_say": "Let me bring that form back up for you.",
            "last_submission": None,
            "_brain_action": "continue",
        }

    try:
        completion = _get_openai_client().chat.completions.create(
            model=spec.model or os.environ["AZURE_MODEL_DEPLOYMENT"],
            messages=[{"role": "system", "content": _brain_system_prompt(spec, state)}]
            + _to_openai_dicts(convo),
            tools=_brain_tools(),
            tool_choice="auto",
            temperature=0.3,
        )
    except Exception as e:  # pragma: no cover - network failure path
        print(f"[category_agent.brain] LLM call failed: {type(e).__name__}: {e}", file=sys.stderr)
        return {
            "brain_turns": turns,
            "assistant_say": "Sorry, I had trouble there. Let me bring the form back up.",
            "last_submission": None,
            "_brain_action": "continue",
        }

    msg = completion.choices[0].message
    name, args = "continue_task", {}
    if msg.tool_calls:
        call = msg.tool_calls[0]
        name = call.function.name
        try:
            args = json.loads(call.function.arguments)
        except (json.JSONDecodeError, AttributeError, TypeError):
            args = {}
    elif (msg.content or "").strip():
        # Plain text reply -> treat as an answer.
        name, args = "answer_question", {"answer": msg.content.strip()}

    base = {"brain_turns": turns, "last_submission": None,
            "cat_messages": [HumanMessage(content=user_text)]}

    if name == "answer_question":
        ans = args.get("answer") or "Happy to help with that."
        return {**base, "assistant_say": ans, "cat_messages": base["cat_messages"] + [AIMessage(content=ans)],
                "_brain_action": "continue"}

    if name == "switch_task":
        target = args.get("intent_id", "")
        if target in spec.member_intents:
            # intra-category: start the sibling task here
            return {**base, "active_intent": target, "current_step_idx": 0,
                    "collected_data": {}, "last_error": None, "_brain_action": "switch_sibling"}
        if target in INTENT_TO_CATEGORY:
            # cross-category: hand back to the orchestrator
            return {**base, "last_handback": {
                "kind": "pivot", "new_intent": target,
                "from_intent": state.get("active_intent"),
                "resume_step_idx": state.get("current_step_idx", 0),
                "collected_data": dict(state.get("collected_data") or {}),
            }, "_brain_action": "pivot"}
        # unknown -> stay put
        return {**base, "assistant_say": "I'm not able to do that one. Want to keep going here?",
                "_brain_action": "continue"}

    if name == "cancel_task":
        return {**base, "last_handback": {"kind": "cancelled"}, "_brain_action": "cancel"}

    # continue_task / default
    return {**base, "_brain_action": "continue"}


def _finalize(state: CategoryAgentState, *, repo: Repository, spec: CategorySpec) -> dict[str, Any]:
    """Terminal node: build the success/inform card (completed), or set the handback
    signal (cancelled / pivot), and write last_handback for the supervisor."""
    intent = state.get("active_intent")
    plan = _plan(spec, state)
    idx = state.get("current_step_idx", 0)
    sub = state.get("last_submission") or {}
    pend = state.get("last_handback") or {}

    if pend.get("kind") == "pivot":
        # parked for a cross-category pivot; handback already carries resume data
        return {"pending_card": None, "last_submission": None,
                "last_handback": {**pend, "label": INTENT_LABELS.get(pend.get("from_intent"), "")}}

    if sub.get("_cancelled") or pend.get("kind") == "cancelled":
        return {
            "pending_card": None, "final_card": None, "last_submission": None,
            "final_message": "Got it, I've stopped that. What else can I help you with?",
            "last_handback": {"kind": "cancelled", "intent": intent,
                              "label": INTENT_LABELS.get(intent, "")},
        }

    # completed: render the inform/success card for the active intent
    card = None
    if idx < len(plan) and plan[idx]["kind"] == "inform" and plan[idx].get("card_factory"):
        card = plan[idx]["card_factory"](state, repo)
    request_id = (state.get("collected_data") or {}).get("request_id")
    return {
        "pending_card": None, "last_submission": None,
        "final_card": card,
        "final_message": INTENT_SUCCESS_MESSAGES.get(intent, ""),
        "last_handback": {"kind": "completed", "intent": intent,
                          "label": INTENT_LABELS.get(intent, ""), "request_id": request_id},
    }


# ---------- routers ----------

def _route_from_gate(state: CategoryAgentState, *, spec: CategorySpec) -> str:
    plan = _plan(spec, state)
    idx = state.get("current_step_idx", 0)
    if idx >= len(plan):
        return "finalize"
    step = plan[idx]
    if _is_skippable(step, state):
        return "step_gate"          # loop: _step_gate will advance one, then re-check
    if step["kind"] == "inform":
        return "finalize"
    if step["kind"] == "persist":
        return "run_persist"
    return "present_step"


def _route_after_await(state: CategoryAgentState) -> str:
    sub = state.get("last_submission") or {}
    if isinstance(sub, dict) and sub.get("_cancelled"):
        return "finalize"
    if isinstance(sub, dict) and "_user_text" in sub:
        return "brain"
    return "validate_apply"


def _route_after_validate(state: CategoryAgentState) -> str:
    return "present_step" if state.get("last_error") else "step_gate"


def _route_after_brain(state: CategoryAgentState) -> str:
    action = state.get("_brain_action")
    if action == "pivot" or action == "cancel":
        return "finalize"
    if action == "switch_sibling":
        return "step_gate"
    return "present_step"           # answer / continue: re-show current card


# ---------- factory ----------

def build_category_agent(spec: CategorySpec, repo: Repository):
    """Compile the subgraph for one category. No checkpointer — inherits the parent's."""
    from functools import partial

    g = StateGraph(CategoryAgentState)
    g.add_node("cat_init", partial(_cat_init, spec=spec))
    g.add_node("step_gate", partial(_step_gate, spec=spec))
    g.add_node("present_step", partial(_present_step, repo=repo, spec=spec))
    g.add_node("await_card", _await_card)
    g.add_node("validate_apply", partial(_validate_apply, repo=repo, spec=spec))
    g.add_node("run_persist", partial(_run_persist, repo=repo, spec=spec))
    g.add_node("brain", partial(_brain, spec=spec))
    g.add_node("finalize", partial(_finalize, repo=repo, spec=spec))

    g.add_edge(START, "cat_init")
    g.add_edge("cat_init", "step_gate")
    g.add_conditional_edges("step_gate", partial(_route_from_gate, spec=spec),
                            {"step_gate": "step_gate", "present_step": "present_step",
                             "run_persist": "run_persist", "finalize": "finalize"})
    g.add_edge("present_step", "await_card")
    g.add_conditional_edges("await_card", _route_after_await,
                            {"validate_apply": "validate_apply", "brain": "brain", "finalize": "finalize"})
    g.add_conditional_edges("validate_apply", _route_after_validate,
                            {"present_step": "present_step", "step_gate": "step_gate"})
    g.add_edge("run_persist", "step_gate")
    g.add_conditional_edges("brain", _route_after_brain,
                            {"present_step": "present_step", "step_gate": "step_gate", "finalize": "finalize"})
    g.add_edge("finalize", END)
    return g.compile()
