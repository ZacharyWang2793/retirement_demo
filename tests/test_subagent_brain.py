"""Tests for the NEW category-agent behaviors (free-text handling mid-flow):

- in-domain Q&A answer-and-continue
- intra-category follow-up (switch to a sibling task in the same agent)
- cross-category hand-back (pivot parks the task; orchestrator routes the new one)
- resume a parked task
- non-termination guard (too many brain turns parks the flow)

The brain only runs when the member types free text while a card is up, so each
test pauses on a card then resumes with Command(resume={"_user_text": ...}). The
brain LLM is mocked with a scripted sequence of tool calls.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from langgraph.types import Command

TEST_DIR = Path(__file__).resolve().parents[1] / "data"
os.environ["RETIREMENT_DB_PATH"] = str(TEST_DIR / "test_brain_retirement.db")
os.environ["CHECKPOINT_DB_PATH"] = str(TEST_DIR / "test_brain_checkpoints.db")

from agents.graph import build_graph  # noqa: E402
from data.seed import main as seed_main  # noqa: E402
from db.connection import get_db, reset_db  # noqa: E402
from db.repository import Repository  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db_per_test():
    for p in (TEST_DIR / "test_brain_retirement.db", TEST_DIR / "test_brain_checkpoints.db"):
        if p.exists():
            p.unlink()
    reset_db()
    seed_main()
    yield


@pytest.fixture(autouse=True)
def fake_azure(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fake-key")
    monkeypatch.setenv("AZURE_OPENAI_BASE_URL", "https://fake.services.ai.azure.com/openai/v1")
    monkeypatch.setenv("AZURE_MODEL_DEPLOYMENT", "gpt-test")


def _scripted_brain(script):
    """Mock OpenAI client whose create() returns scripted (tool_name, args) in order."""
    calls = iter(script)

    class _Completions:
        def create(self, **_kwargs):
            try:
                name, args = next(calls)
            except StopIteration:
                name, args = "continue_task", {}
            tc = SimpleNamespace(id="call", type="function",
                                 function=SimpleNamespace(name=name, arguments=json.dumps(args)))
            return SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(content="", tool_calls=[tc]))])

    return SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))


def _tid():
    return str(uuid.uuid4())


def _view(graph, config):
    snap = graph.get_state(config, subgraphs=True)
    values = dict(snap.values or {})
    pending = None
    child_intent = None
    stack = list(snap.tasks or [])
    while stack:
        t = stack.pop()
        cs = getattr(t, "state", None)
        cv = getattr(cs, "values", None) if cs is not None else None
        if cv is not None:
            if cv.get("pending_card") is not None:
                pending = cv["pending_card"]
            if cv.get("active_intent"):
                child_intent = cv["active_intent"]
            stack.extend(getattr(cs, "tasks", []) or [])
        if getattr(t, "interrupts", None) and pending is None:
            pending = t.interrupts[0].value
    if pending is not None:
        values["pending_card"] = pending
    # During a suspend, the subagent's active_intent hasn't surfaced to the parent yet.
    if child_intent:
        values["active_intent"] = child_intent
    return SimpleNamespace(values=values, next=snap.next)


def _stream_collect(graph, payload, config):
    """Stream (descending into subgraphs); collect assistant_say values seen, return view."""
    says = []
    for ev in graph.stream(payload, config, stream_mode="values", subgraphs=True):
        state = ev[1] if isinstance(ev, tuple) else ev
        if isinstance(state, dict) and state.get("assistant_say"):
            says.append(state["assistant_say"])
    return _view(graph, config), says


def _ctype(card):
    return getattr(card, "card_type", None) or (card.get("card_type") if isinstance(card, dict) else None)


def _open_address(graph, config):
    """Open change_address (verified -> straight to the address form)."""
    payload = {"customer_id": "demo-001", "thread_id": config["configurable"]["thread_id"],
               "verified": True, "intent": "change_address", "messages": []}
    view, _ = _stream_collect(graph, payload, config)
    assert _ctype(view.values["pending_card"]) == "address_form"
    return view


# ------------------------------------------------------------------

def test_in_domain_question_answers_and_re_presents(monkeypatch):
    from agents import category_agent
    monkeypatch.setattr(category_agent, "_get_openai_client",
                        lambda: _scripted_brain([("answer_question",
                            {"answer": "Your old address is replaced as the address of record."})]))
    g = build_graph(Repository(get_db()))
    config = {"configurable": {"thread_id": _tid()}}
    _open_address(g, config)

    # Member types a question instead of submitting the form.
    view, says = _stream_collect(g, Command(resume={"_user_text": "what happens to my old address?"}), config)
    # The brain answered, and the same form is re-presented so they can continue.
    assert any("address of record" in s for s in says), says
    assert _ctype(view.values["pending_card"]) == "address_form"

    # They can still complete the flow normally.
    view = _view(g, config)  # paused at address_form
    for _ in g.stream(Command(resume={"address_line1": "1 Main St", "address_line2": "",
                                       "address_city": "Reno", "address_state": "NV",
                                       "address_postal": "89501"}),
                      config, stream_mode="values", subgraphs=True):
        pass
    view = _view(g, config)
    assert _ctype(view.values["pending_card"]) == "confirmation"


def test_intra_category_switch_stays_in_same_agent(monkeypatch):
    from agents import category_agent
    monkeypatch.setattr(category_agent, "_get_openai_client",
                        lambda: _scripted_brain([("switch_task", {"intent_id": "change_phone"})]))
    g = build_graph(Repository(get_db()))
    config = {"configurable": {"thread_id": _tid()}}
    _open_address(g, config)

    # "actually, change my phone instead" — same category (profile_contact)
    view, _ = _stream_collect(g, Command(resume={"_user_text": "actually change my phone instead"}), config)
    # Same agent switched to the sibling task and presents its first form.
    assert _ctype(view.values["pending_card"]) == "phone_form"
    assert view.values.get("active_intent") == "change_phone"


def test_cross_category_pivot_parks_and_routes(monkeypatch):
    from agents import category_agent
    monkeypatch.setattr(category_agent, "_get_openai_client",
                        lambda: _scripted_brain([("switch_task", {"intent_id": "check_balance"})]))
    g = build_graph(Repository(get_db()))
    config = {"configurable": {"thread_id": _tid()}}
    _open_address(g, config)

    # "wait, what's my balance?" — different category -> hand back + park
    view, _ = _stream_collect(g, Command(resume={"_user_text": "wait what's my balance?"}), config)
    # The new (read-only) task completed and the address task is parked for resume.
    assert not view.next, "turn should end after the read-only balance view"
    assert _ctype(view.values.get("final_card")) == "balance_view"
    parked = view.values.get("parked_task")
    assert parked and parked["intent"] == "change_address"
    ledger = view.values.get("task_ledger", [])
    assert any(e["intent"] == "change_address" and e["status"] == "parked" for e in ledger)
    assert any(e["intent"] == "check_balance" and e["status"] == "completed" for e in ledger)


def test_resume_parked_task(monkeypatch):
    from agents import category_agent
    monkeypatch.setattr(category_agent, "_get_openai_client",
                        lambda: _scripted_brain([("switch_task", {"intent_id": "check_balance"})]))
    g = build_graph(Repository(get_db()))
    config = {"configurable": {"thread_id": _tid()}}
    _open_address(g, config)
    view, _ = _stream_collect(g, Command(resume={"_user_text": "what's my balance?"}), config)
    parked = view.values.get("parked_task")
    assert parked

    # Simulate the resume chip: re-open with the saved progress.
    payload = {"customer_id": "demo-001", "thread_id": config["configurable"]["thread_id"],
               "verified": True, "intent": parked["intent"],
               "resume_payload": {"current_step_idx": parked.get("resume_step_idx", 0),
                                  "collected_data": parked.get("collected_data", {})},
               "messages": []}
    view, _ = _stream_collect(g, payload, config)
    # Back on the parked address task at its form.
    assert _ctype(view.values["pending_card"]) == "address_form"
    assert view.values.get("active_intent") == "change_address"


def test_non_termination_guard_parks_after_many_turns(monkeypatch):
    from agents import category_agent
    # Brain always answers — never lets the form get submitted.
    monkeypatch.setattr(category_agent, "_get_openai_client",
                        lambda: _scripted_brain([("answer_question", {"answer": "Sure."})] * 20))
    g = build_graph(Repository(get_db()))
    config = {"configurable": {"thread_id": _tid()}}
    _open_address(g, config)

    last = None
    for i in range(8):  # _MAX_BRAIN_TURNS is 6; the 7th brain turn forces a park
        last, _ = _stream_collect(g, Command(resume={"_user_text": f"another question {i}"}), config)
        if not last.next:
            break
    # The guard eventually ends the runaway loop instead of hanging forever.
    assert not last.next, "guard should have terminated the loop"
