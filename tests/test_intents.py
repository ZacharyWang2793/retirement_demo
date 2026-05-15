"""Programmatic graph walks. No Streamlit, no LLM.

These tests exercise the graph by:
1. Seeding a fresh DB
2. Invoking the graph with a user message (regex-classified, so no API key needed)
3. Reading state.values["pending_card"] to see what card is awaiting input
4. Resuming with Command(resume=...) per step
5. Asserting final DB state and final state.values

Each test uses a unique thread_id so checkpointer state doesn't bleed across tests.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from langgraph.types import Command

# Use isolated DB paths for tests
TEST_DIR = Path(__file__).resolve().parents[1] / "data"
os.environ["RETIREMENT_DB_PATH"] = str(TEST_DIR / "test_retirement.db")
os.environ["CHECKPOINT_DB_PATH"] = str(TEST_DIR / "test_checkpoints.db")

from agents.graph import build_graph  # noqa: E402
from data.seed import main as seed_main  # noqa: E402
from db.connection import get_db, reset_db  # noqa: E402
from db.repository import Repository  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def fresh_db():
    # Wipe DBs so tests are deterministic
    for p in (TEST_DIR / "test_retirement.db", TEST_DIR / "test_checkpoints.db"):
        if p.exists():
            p.unlink()
    reset_db()
    seed_main()
    yield
    for p in (TEST_DIR / "test_retirement.db", TEST_DIR / "test_checkpoints.db"):
        if p.exists():
            p.unlink()


def _new_thread_id() -> str:
    return str(uuid.uuid4())


def _run_until_pause_or_end(graph, payload_or_command, config):
    """Stream events; return the last (i.e. current) state snapshot."""
    for _ in graph.stream(payload_or_command, config, stream_mode="values"):
        pass
    return graph.get_state(config)


def _is_paused(snap) -> bool:
    return bool(snap.next) and bool(snap.values.get("pending_card"))


# ------------------------------------------------------------------
# Read-only flow: check_balance
# ------------------------------------------------------------------

def test_check_balance_read_only():
    repo = Repository(get_db())
    g = build_graph(repo)
    tid = _new_thread_id()
    config = {"configurable": {"thread_id": tid}}

    snap = _run_until_pause_or_end(
        g,
        {
            "customer_id": "demo-001",
            "thread_id": tid,
            "messages": [{"role": "user", "content": "what's my balance?"}],
            "verified": False,
            "collected_data": {},
        },
        config,
    )

    assert snap.values.get("intent") == "check_balance"
    final_card = snap.values.get("final_card")
    assert final_card is not None
    assert final_card.card_type == "balance_view"
    assert final_card.total_balance == pytest.approx(796650.50)


# ------------------------------------------------------------------
# Multi-step mutating flow: change_address
# ------------------------------------------------------------------

def test_change_address_full_flow():
    repo = Repository(get_db())
    g = build_graph(repo)
    tid = _new_thread_id()
    config = {"configurable": {"thread_id": tid}}

    # Snapshot the customer's address before
    before = repo.get_customer("demo-001")
    assert before["address_city"] == "San Francisco"

    # 1. Initial invoke — should pause on IdentityVerification
    snap = _run_until_pause_or_end(
        g,
        {
            "customer_id": "demo-001",
            "thread_id": tid,
            "messages": [{"role": "user", "content": "I want to change my address"}],
            "verified": False,
            "collected_data": {},
        },
        config,
    )
    assert _is_paused(snap)
    assert snap.values["intent"] == "change_address"
    assert snap.values["pending_card"].card_type == "identity_verification"

    # 2. Submit identity → should pause on OTP
    snap = _run_until_pause_or_end(
        g, Command(resume={"dob": "1965-04-12", "ssn_last4": "6789"}), config
    )
    assert _is_paused(snap)
    assert snap.values["pending_card"].card_type == "otp"

    # 3. Submit OTP → should pause on AddressForm
    snap = _run_until_pause_or_end(g, Command(resume={"otp": "123456"}), config)
    assert _is_paused(snap)
    assert snap.values["pending_card"].card_type == "address_form"
    assert snap.values["pending_card"].prefilled["address_city"] == "San Francisco"

    # 4. Submit new address → should pause on Confirmation
    new_addr = {
        "address_line1": "500 Market St",
        "address_line2": None,
        "address_city": "Oakland",
        "address_state": "CA",
        "address_postal": "94607",
        "address_country": "US",
    }
    snap = _run_until_pause_or_end(g, Command(resume=new_addr), config)
    assert _is_paused(snap)
    assert snap.values["pending_card"].card_type == "confirmation"
    diff = snap.values["pending_card"].diff
    cities = {d["field"]: (d["before"], d["after"]) for d in diff if d["field"].lower() == "city"}
    assert "City" in cities and cities["City"] == ("San Francisco", "Oakland")

    # 5. Confirm → graph runs persist + success → end
    snap = _run_until_pause_or_end(g, Command(resume={"_confirmed": True}), config)
    final_card = snap.values.get("final_card")
    assert final_card is not None
    assert final_card.card_type == "success"
    assert final_card.request_id is not None

    # DB state changed
    after = repo.get_customer("demo-001")
    assert after["address_city"] == "Oakland"
    assert after["address_postal"] == "94607"

    # Audit log + request rows
    requests = repo.list_requests("demo-001")
    assert any(r["type"] == "address_change" and r["status"] == "completed" for r in requests)


# ------------------------------------------------------------------
# Negative path: bad SSN
# ------------------------------------------------------------------

def test_change_address_bad_identity_re_renders():
    repo = Repository(get_db())
    g = build_graph(repo)
    tid = _new_thread_id()
    config = {"configurable": {"thread_id": tid}}

    snap = _run_until_pause_or_end(
        g,
        {
            "customer_id": "demo-002",
            "thread_id": tid,
            "messages": [{"role": "user", "content": "change my address"}],
            "verified": False,
            "collected_data": {},
        },
        config,
    )
    assert snap.values["pending_card"].card_type == "identity_verification"

    snap = _run_until_pause_or_end(
        g, Command(resume={"dob": "1989-08-23", "ssn_last4": "0000"}), config
    )
    # Should re-render IdentityVerification with an error
    assert _is_paused(snap)
    assert snap.values["pending_card"].card_type == "identity_verification"
    assert snap.values["pending_card"].error is not None


# ------------------------------------------------------------------
# Add beneficiary flow
# ------------------------------------------------------------------

def test_add_beneficiary_full_flow():
    repo = Repository(get_db())
    g = build_graph(repo)
    tid = _new_thread_id()
    config = {"configurable": {"thread_id": tid}}

    before_count = len(repo.get_beneficiaries("demo-003"))

    snap = _run_until_pause_or_end(
        g,
        {
            "customer_id": "demo-003",
            "thread_id": tid,
            "messages": [{"role": "user", "content": "Add a beneficiary"}],
            "verified": False,
            "collected_data": {},
        },
        config,
    )
    assert snap.values["pending_card"].card_type == "identity_verification"

    snap = _run_until_pause_or_end(
        g, Command(resume={"dob": "1996-11-04", "ssn_last4": "1122"}), config
    )
    assert snap.values["pending_card"].card_type == "otp"

    snap = _run_until_pause_or_end(g, Command(resume={"otp": "123456"}), config)
    assert snap.values["pending_card"].card_type == "beneficiary_form"
    accounts = snap.values["pending_card"].accounts
    assert len(accounts) >= 1

    snap = _run_until_pause_or_end(
        g,
        Command(resume={
            "account_id": accounts[0]["id"],
            "type": "primary",
            "name": "Anil Patel",
            "relationship": "parent",
            "dob": "1968-03-15",
            "ssn_last4": "0099",
            "allocation_pct": 100.0,
        }),
        config,
    )
    assert snap.values["pending_card"].card_type == "confirmation"

    snap = _run_until_pause_or_end(g, Command(resume={"_confirmed": True}), config)
    final_card = snap.values.get("final_card")
    assert final_card is not None
    assert final_card.card_type == "success"

    after_count = len(repo.get_beneficiaries("demo-003"))
    assert after_count == before_count + 1


# ------------------------------------------------------------------
# Stub intent (rollover_out) renders NotImplementedCard
# ------------------------------------------------------------------

def test_stub_intent_renders_not_implemented():
    repo = Repository(get_db())
    g = build_graph(repo)
    tid = _new_thread_id()
    config = {"configurable": {"thread_id": tid}}

    snap = _run_until_pause_or_end(
        g,
        {
            "customer_id": "demo-002",
            "thread_id": tid,
            "messages": [{"role": "user", "content": "I want to roll over my 401k to another plan"}],
            "verified": False,
            "collected_data": {},
        },
        config,
    )
    final_card = snap.values.get("final_card")
    assert final_card is not None
    assert final_card.card_type == "not_implemented"
    assert final_card.intent.lower().startswith("roll")


# ------------------------------------------------------------------
# Cancel mid-flow
# ------------------------------------------------------------------

def test_back_to_back_flows_same_thread():
    """After a flow terminates cleanly, re-invoking with new input restarts from the top."""
    repo = Repository(get_db())
    g = build_graph(repo)
    tid = _new_thread_id()
    config = {"configurable": {"thread_id": tid}}

    # Flow 1: check balance (read-only, terminates)
    snap = _run_until_pause_or_end(
        g,
        {
            "customer_id": "demo-002",
            "thread_id": tid,
            "messages": [{"role": "user", "content": "what's my balance?"}],
            "verified": False,
            "collected_data": {},
        },
        config,
    )
    assert snap.values.get("intent") == "check_balance"
    assert snap.values.get("final_card") is not None
    assert snap.values["final_card"].card_type == "balance_view"

    # Flow 2 on the SAME thread: change phone (mutating)
    snap = _run_until_pause_or_end(
        g,
        {
            "customer_id": "demo-002",
            "thread_id": tid,
            "messages": [{"role": "user", "content": "change my phone number"}],
            "verified": False,
            "collected_data": {},
            "current_step_idx": 0,
            "plan_complete": False,
            "pending_card": None,
            "final_card": None,
            "final_message": None,
            "last_error": None,
            "last_submission": None,
        },
        config,
    )
    assert snap.values["intent"] == "change_phone"
    assert _is_paused(snap)
    assert snap.values["pending_card"].card_type == "identity_verification"


def test_agent_node_text_reply_for_greeting(monkeypatch):
    """Casual greetings get a conversational reply, not a card."""
    from langchain_core.messages import AIMessage
    from agents import nodes

    class _FakeLLM:
        def invoke(self, _msgs):
            return AIMessage(content="Hi! I'm here to help with your retirement account. What can I do for you today?")

    monkeypatch.setattr(nodes, "_get_agent_llm", lambda: _FakeLLM())
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com/")

    repo = Repository(get_db())
    g = build_graph(repo)
    tid = _new_thread_id()
    config = {"configurable": {"thread_id": tid}}

    snap = _run_until_pause_or_end(
        g,
        {
            "customer_id": "demo-001",
            "thread_id": tid,
            "messages": [{"role": "user", "content": "hi how are you"}],
            "verified": False,
            "collected_data": {},
        },
        config,
    )
    assert snap.values.get("pending_card") is None
    assert snap.values.get("final_card") is None
    assert snap.values.get("intent") in (None, "")
    assert "retirement account" in snap.values.get("final_message", "").lower()


def test_agent_node_tool_call_routes_to_workflow(monkeypatch):
    """Agent emitting a start_workflow tool call kicks off the workflow loop."""
    from langchain_core.messages import AIMessage
    from agents import nodes

    class _FakeLLM:
        def invoke(self, _msgs):
            msg = AIMessage(content="I'll get your legal name updated on file.")
            msg.tool_calls = [{
                "name": "start_workflow",
                "args": {"intent_id": "change_name", "brief_reason": "I'll get your legal name updated on file."},
                "id": "call_123",
            }]
            return msg

    monkeypatch.setattr(nodes, "_get_agent_llm", lambda: _FakeLLM())
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com/")

    repo = Repository(get_db())
    g = build_graph(repo)
    tid = _new_thread_id()
    config = {"configurable": {"thread_id": tid}}

    snap = _run_until_pause_or_end(
        g,
        {
            "customer_id": "demo-001",
            "thread_id": tid,
            "messages": [{"role": "user", "content": "I just got married and have a different last name"}],
            "verified": False,
            "collected_data": {},
        },
        config,
    )
    assert snap.values.get("intent") == "change_name"
    assert snap.values.get("routed_via") == "agent"
    assert snap.values.get("final_card") is not None
    assert snap.values["final_card"].card_type == "not_implemented"
    ann = snap.values.get("routing_announcement", "")
    assert "legal name" in ann.lower()


def test_agent_node_unknown_intent_falls_back(monkeypatch):
    """If the LLM hallucinates an unknown intent, we apologize and end the turn."""
    from langchain_core.messages import AIMessage
    from agents import nodes

    class _FakeLLM:
        def invoke(self, _msgs):
            msg = AIMessage(content="")
            msg.tool_calls = [{
                "name": "start_workflow",
                "args": {"intent_id": "buy_lottery_tickets", "brief_reason": ""},
                "id": "call_xyz",
            }]
            return msg

    monkeypatch.setattr(nodes, "_get_agent_llm", lambda: _FakeLLM())
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com/")

    repo = Repository(get_db())
    g = build_graph(repo)
    tid = _new_thread_id()
    config = {"configurable": {"thread_id": tid}}

    snap = _run_until_pause_or_end(
        g,
        {
            "customer_id": "demo-001",
            "thread_id": tid,
            "messages": [{"role": "user", "content": "I'd like to do something weird"}],
            "verified": False,
            "collected_data": {},
        },
        config,
    )
    assert snap.values.get("intent") in (None, "")
    assert snap.values.get("final_card") is None
    assert "not sure" in snap.values.get("final_message", "").lower() or "tell me" in snap.values.get("final_message", "").lower()


def test_cancel_during_address_change():
    repo = Repository(get_db())
    g = build_graph(repo)
    tid = _new_thread_id()
    config = {"configurable": {"thread_id": tid}}

    snap = _run_until_pause_or_end(
        g,
        {
            "customer_id": "demo-001",
            "thread_id": tid,
            "messages": [{"role": "user", "content": "change my address"}],
            "verified": False,
            "collected_data": {},
        },
        config,
    )
    assert snap.values["pending_card"].card_type == "identity_verification"

    # User clicks Cancel
    snap = _run_until_pause_or_end(g, Command(resume={"_cancelled": True}), config)
    assert not _is_paused(snap)
    assert snap.values.get("plan_complete") is True
    assert snap.values.get("intent") is None
    assert snap.values.get("final_message", "").lower().startswith("got it")
