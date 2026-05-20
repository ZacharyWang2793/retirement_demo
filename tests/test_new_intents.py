"""End-to-end graph walks for the intents added in the multi-PR expansion.

Each test follows the pattern in tests/test_intents.py:
1. Build a fresh graph with a seeded DB
2. Stream a user message, walk through each paused card
3. Resume with Command(resume=...) data
4. Assert final state + DB rows

Tests use unique thread_ids so the checkpointer doesn't leak across them, and
each test scopes its DB writes to a specific demo customer where reasonable.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from langgraph.types import Command

TEST_DIR = Path(__file__).resolve().parents[1] / "data"
os.environ["RETIREMENT_DB_PATH"] = str(TEST_DIR / "test_new_retirement.db")
os.environ["CHECKPOINT_DB_PATH"] = str(TEST_DIR / "test_new_checkpoints.db")

from agents.graph import build_graph  # noqa: E402
from data.seed import main as seed_main  # noqa: E402
from db.connection import get_db, reset_db  # noqa: E402
from db.repository import Repository  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db_per_test():
    """Wipe the DB before each test — these flows mutate domain rows and we want
    deterministic starting state for every assertion."""
    for p in (TEST_DIR / "test_new_retirement.db", TEST_DIR / "test_new_checkpoints.db"):
        if p.exists():
            p.unlink()
    reset_db()
    seed_main()
    yield


def _tid() -> str:
    return str(uuid.uuid4())


def _walk(graph, payload, config):
    """Stream events until the graph pauses or ends. Returns the latest snapshot."""
    for _ in graph.stream(payload, config, stream_mode="values"):
        pass
    return graph.get_state(config)


def _is_paused(snap) -> bool:
    return bool(snap.next) and bool(snap.values.get("pending_card"))


def _new_graph_and_config():
    repo = Repository(get_db())
    g = build_graph(repo)
    tid = _tid()
    return g, repo, {"configurable": {"thread_id": tid}}, tid


def _verify_otp(g, config, customer):
    """Walk through the verify+otp pair using the seeded credentials."""
    snap = _walk(g, Command(resume={"dob": customer["dob"], "ssn_last4": customer["ssn_last4"]}), config)
    assert _is_paused(snap)
    assert snap.values["pending_card"].card_type == "otp"
    snap = _walk(g, Command(resume={"otp": "123456"}), config)
    return snap


# ------------------------------------------------------------------
# Read-only / status
# ------------------------------------------------------------------

def test_check_request_status_shows_pending_seed():
    g, repo, config, tid = _new_graph_and_config()
    snap = _walk(g, {
        "customer_id": "demo-001", "thread_id": tid,
        "intent": "check_request_status",
        "messages": [{"role": "user", "content": "what's the status of my requests?"}],
        "verified": False, "collected_data": {},
    }, config)
    assert snap.values["intent"] == "check_request_status"
    final = snap.values.get("final_card")
    assert final is not None and final.card_type == "request_list"
    # Seeded pending request should appear
    assert any(r["status"] == "pending" for r in final.requests)


def test_cancel_request_full_flow():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-001")
    pending_before = [r for r in repo.list_requests("demo-001") if r["status"] == "pending"]
    assert pending_before, "seed should produce a pending request"

    snap = _walk(g, {
        "customer_id": "demo-001", "thread_id": tid,
        "intent": "cancel_request",
        "messages": [{"role": "user", "content": "cancel a request"}],
        "verified": False, "collected_data": {},
    }, config)
    assert snap.values["intent"] == "cancel_request"
    assert _is_paused(snap)
    assert snap.values["pending_card"].card_type == "identity_verification"

    snap = _verify_otp(g, config, customer)
    assert _is_paused(snap)
    assert snap.values["pending_card"].card_type == "request_list"

    target_id = pending_before[0]["id"]
    snap = _walk(g, Command(resume={"request_id": target_id}), config)
    assert _is_paused(snap)
    assert snap.values["pending_card"].card_type == "confirmation"

    snap = _walk(g, Command(resume={"_confirmed": True}), config)
    final = snap.values.get("final_card")
    assert final is not None and final.card_type == "success"

    assert repo.get_request(target_id)["status"] == "cancelled"


# ------------------------------------------------------------------
# Contact updates
# ------------------------------------------------------------------

def test_change_email_full_flow():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-001")
    snap = _walk(g, {
        "customer_id": "demo-001", "thread_id": tid,
        "intent": "change_email",
        "messages": [{"role": "user", "content": "change my email"}],
        "verified": False, "collected_data": {},
    }, config)
    snap = _verify_otp(g, config, customer)
    assert _is_paused(snap)
    assert snap.values["pending_card"].card_type == "email_form"

    snap = _walk(g, Command(resume={"email": "margaret.chen+new@example.com"}), config)
    assert _is_paused(snap) and snap.values["pending_card"].card_type == "confirmation"
    snap = _walk(g, Command(resume={"_confirmed": True}), config)
    assert snap.values.get("final_card").card_type == "success"
    assert repo.get_customer("demo-001")["email"] == "margaret.chen+new@example.com"


def test_change_name_full_flow_writes_doc():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-002")
    snap = _walk(g, {
        "customer_id": "demo-002", "thread_id": tid,
        "intent": "change_name",
        "messages": [{"role": "user", "content": "change my legal name"}],
        "verified": False, "collected_data": {},
    }, config)
    snap = _verify_otp(g, config, customer)
    assert _is_paused(snap) and snap.values["pending_card"].card_type == "name_form"

    snap = _walk(g, Command(resume={
        "first_name": "Tyler",
        "last_name": "Rodriguez-Smith",
        "doc_kind": "marriage_certificate",
        "doc_file_name": "marriage-2026.pdf",
    }), config)
    snap = _walk(g, Command(resume={"_confirmed": True}), config)
    assert snap.values.get("final_card").card_type == "success"
    after = repo.get_customer("demo-002")
    assert after["last_name"] == "Rodriguez-Smith"
    # The supporting doc should be on file
    docs = repo.list_documents("demo-002")
    assert any("name_change_" in d["kind"] for d in docs)


def test_update_beneficiary_edit_path():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-001")
    before = repo.get_beneficiaries("demo-001")
    target = before[0]

    snap = _walk(g, {
        "customer_id": "demo-001", "thread_id": tid,
        "intent": "update_beneficiary",
        "messages": [{"role": "user", "content": "update my beneficiaries"}],
        "verified": False, "collected_data": {},
    }, config)
    assert snap.values["intent"] == "update_beneficiary"
    snap = _verify_otp(g, config, customer)
    assert _is_paused(snap) and snap.values["pending_card"].card_type == "beneficiary_picker"

    snap = _walk(g, Command(resume={"action": "edit", "beneficiary_id": target["id"]}), config)
    assert _is_paused(snap) and snap.values["pending_card"].card_type == "beneficiary_form"
    assert snap.values["pending_card"].mode == "edit"

    snap = _walk(g, Command(resume={
        "account_id": target["account_id"],
        "type": target["type"],
        "name": target["name"],
        "relationship": "spouse",
        "dob": target["dob"],
        "ssn_last4": target["ssn_last4"],
        "allocation_pct": 75.0,
        "mode": "edit",
        "target_beneficiary_id": target["id"],
    }), config)
    snap = _walk(g, Command(resume={"_confirmed": True}), config)
    assert snap.values.get("final_card").card_type == "success"
    after = next(b for b in repo.get_beneficiaries("demo-001") if b["id"] == target["id"])
    assert after["allocation_pct"] == 75.0


def test_update_beneficiary_remove_path_skips_edit_form():
    """Skip_if branching: remove path bypasses the edit form/confirm/persist/success."""
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-001")
    before = repo.get_beneficiaries("demo-001")
    target = next(b for b in before if b["type"] == "contingent")

    snap = _walk(g, {
        "customer_id": "demo-001", "thread_id": tid,
        "intent": "update_beneficiary",
        "messages": [{"role": "user", "content": "remove a beneficiary"}],
        "verified": False, "collected_data": {},
    }, config)
    snap = _verify_otp(g, config, customer)
    snap = _walk(g, Command(resume={"action": "remove", "beneficiary_id": target["id"]}), config)
    # Should pause directly on the removal confirmation (skipping edit form)
    assert _is_paused(snap)
    assert snap.values["pending_card"].card_type == "confirmation"
    assert "removal" in snap.values["pending_card"].title.lower() or "remove" in snap.values["pending_card"].title.lower()

    snap = _walk(g, Command(resume={"_confirmed": True}), config)
    assert snap.values.get("final_card").card_type == "success"
    after = [b for b in repo.get_beneficiaries("demo-001") if b["id"] == target["id"]]
    assert after == []


# ------------------------------------------------------------------
# Tax / banking
# ------------------------------------------------------------------

def test_update_tax_withholding_full_flow():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-001")
    snap = _walk(g, {
        "customer_id": "demo-001", "thread_id": tid,
        "intent": "update_tax_withholding",
        "messages": [{"role": "user", "content": "update my federal tax withholding"}],
        "verified": False, "collected_data": {},
    }, config)
    snap = _verify_otp(g, config, customer)
    assert _is_paused(snap) and snap.values["pending_card"].card_type == "tax_withholding_form"
    acct = snap.values["pending_card"].accounts[0]["id"]
    snap = _walk(g, Command(resume={
        "account_id": acct, "tax_year": 2026,
        "federal_pct": 25.0, "state_code": "CA", "state_pct": 8.0,
    }), config)
    snap = _walk(g, Command(resume={"_confirmed": True}), config)
    assert snap.values.get("final_card").card_type == "success"
    tw = repo.get_tax_withholding(acct, 2026)
    assert tw["federal_pct"] == 25.0


def test_update_direct_deposit_microdeposit_happy_path():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-001")
    snap = _walk(g, {
        "customer_id": "demo-001", "thread_id": tid,
        "intent": "update_direct_deposit",
        "messages": [{"role": "user", "content": "update my direct deposit"}],
        "verified": False, "collected_data": {},
    }, config)
    snap = _verify_otp(g, config, customer)
    assert _is_paused(snap) and snap.values["pending_card"].card_type == "bank_account_form"
    snap = _walk(g, Command(resume={
        "nickname": "Citi Checking", "routing_last4": "5678",
        "account_last4": "1234", "account_type": "checking", "set_default": True,
    }), config)
    # Microdeposit step
    assert _is_paused(snap) and snap.values["pending_card"].card_type == "microdeposit"
    snap = _walk(g, Command(resume={"deposit_1": 0.12, "deposit_2": 0.34}), config)
    assert _is_paused(snap) and snap.values["pending_card"].card_type == "confirmation"
    snap = _walk(g, Command(resume={"_confirmed": True}), config)
    assert snap.values.get("final_card").card_type == "success"
    banks = repo.list_bank_accounts("demo-001")
    assert any(b["nickname"] == "Citi Checking" and b["verified_at"] for b in banks)


def test_microdeposit_wrong_amounts_re_renders():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-001")
    snap = _walk(g, {
        "customer_id": "demo-001", "thread_id": tid,
        "intent": "update_direct_deposit",
        "messages": [{"role": "user", "content": "update my direct deposit"}],
        "verified": False, "collected_data": {},
    }, config)
    snap = _verify_otp(g, config, customer)
    snap = _walk(g, Command(resume={
        "nickname": "Test Bank", "routing_last4": "0000",
        "account_last4": "1111", "account_type": "checking", "set_default": False,
    }), config)
    assert snap.values["pending_card"].card_type == "microdeposit"
    snap = _walk(g, Command(resume={"deposit_1": 0.99, "deposit_2": 0.88}), config)
    # Should re-render microdeposit with an error
    assert _is_paused(snap)
    assert snap.values["pending_card"].card_type == "microdeposit"
    assert snap.values["pending_card"].error is not None


# ------------------------------------------------------------------
# Investments
# ------------------------------------------------------------------

def test_change_allocation_must_sum_100_rejects():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-001")
    snap = _walk(g, {
        "customer_id": "demo-001", "thread_id": tid,
        "intent": "change_allocation",
        "messages": [{"role": "user", "content": "change my allocation"}],
        "verified": False, "collected_data": {},
    }, config)
    snap = _verify_otp(g, config, customer)
    assert snap.values["pending_card"].card_type == "allocation_form"
    funds = snap.values["pending_card"].funds
    bad = [{"ticker": f["ticker"], "target_pct": 30.0} for f in funds]  # won't sum to 100
    snap = _walk(g, Command(resume={
        "account_id": snap.values["pending_card"].account_id,
        "allocations": bad,
    }), config)
    assert snap.values["pending_card"].card_type == "allocation_form"
    assert snap.values["pending_card"].error and "100" in snap.values["pending_card"].error


def test_change_allocation_full_flow():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-001")
    snap = _walk(g, {
        "customer_id": "demo-001", "thread_id": tid,
        "intent": "change_allocation",
        "messages": [{"role": "user", "content": "change my allocation"}],
        "verified": False, "collected_data": {},
    }, config)
    snap = _verify_otp(g, config, customer)
    funds = snap.values["pending_card"].funds
    n = len(funds)
    even = 100.0 / n
    submission = [{"ticker": f["ticker"], "target_pct": even} for f in funds]
    snap = _walk(g, Command(resume={
        "account_id": snap.values["pending_card"].account_id,
        "allocations": submission,
    }), config)
    snap = _walk(g, Command(resume={"_confirmed": True}), config)
    assert snap.values.get("final_card").card_type == "success"


def test_rebalance_full_flow():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-001")
    snap = _walk(g, {
        "customer_id": "demo-001", "thread_id": tid,
        "intent": "rebalance",
        "messages": [{"role": "user", "content": "rebalance my portfolio"}],
        "verified": False, "collected_data": {},
    }, config)
    snap = _verify_otp(g, config, customer)
    # After verify+otp, we run the drift-snapshot persist, then render the drift view
    assert _is_paused(snap)
    assert snap.values["pending_card"].card_type == "drift_view"
    snap = _walk(g, Command(resume={"_confirmed": True}), config)
    assert snap.values.get("final_card").card_type == "success"
    assert any(r["type"] == "rebalance" for r in repo.list_requests("demo-001"))


# ------------------------------------------------------------------
# Distributions
# ------------------------------------------------------------------

def test_take_rmd_full_flow():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-001")
    snap = _walk(g, {
        "customer_id": "demo-001", "thread_id": tid,
        "intent": "take_rmd",
        "messages": [{"role": "user", "content": "I need to take my RMD"}],
        "verified": False, "collected_data": {},
    }, config)
    snap = _verify_otp(g, config, customer)
    assert snap.values["pending_card"].card_type == "rmd_amount"
    snap = _walk(g, Command(resume={"_acknowledged": True}), config)
    assert snap.values["pending_card"].card_type == "distribution_method"
    banks = snap.values["pending_card"].bank_accounts
    snap = _walk(g, Command(resume={
        "method": "bank_transfer", "bank_account_id": banks[0]["id"],
    }), config)
    snap = _walk(g, Command(resume={"_confirmed": True}), config)
    assert snap.values.get("final_card").card_type == "success"


def test_qualified_distribution_full_flow():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-001")
    snap = _walk(g, {
        "customer_id": "demo-001", "thread_id": tid,
        "intent": "qualified_distribution",
        "messages": [{"role": "user", "content": "qualified distribution"}],
        "verified": False, "collected_data": {},
    }, config)
    snap = _verify_otp(g, config, customer)
    assert snap.values["pending_card"].card_type == "distribution_request_form"
    accts = snap.values["pending_card"].accounts
    snap = _walk(g, Command(resume={
        "account_id": accts[0]["id"], "amount": 2500.0,
        "method": "mailed_check", "federal_pct": 10.0,
    }), config)
    snap = _walk(g, Command(resume={"_confirmed": True}), config)
    assert snap.values.get("final_card").card_type == "success"


# ------------------------------------------------------------------
# Tier 3 — specialist routing
# ------------------------------------------------------------------

def test_hardship_specialist_routing():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-002")
    snap = _walk(g, {
        "customer_id": "demo-002", "thread_id": tid,
        "intent": "hardship_withdrawal",
        "messages": [{"role": "user", "content": "hardship withdrawal"}],
        "verified": False, "collected_data": {},
    }, config)
    snap = _verify_otp(g, config, customer)
    assert snap.values["pending_card"].card_type == "hardship_form"
    acct = snap.values["pending_card"].accounts[0]["id"]
    snap = _walk(g, Command(resume={
        "account_id": acct, "reason": "medical_expense",
        "amount": 5000.0, "doc_file_name": "medical-2026.pdf",
    }), config)
    final = snap.values.get("final_card")
    assert final is not None and final.card_type == "specialist_routing"
    routed = [r for r in repo.list_requests("demo-002") if r["type"] == "hardship_withdrawal"]
    assert routed and routed[0]["routing_target"] == "specialist_review"
    assert routed[0]["status"] == "pending"


def test_rollover_out_specialist_routing():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-002")
    snap = _walk(g, {
        "customer_id": "demo-002", "thread_id": tid,
        "intent": "rollover_out",
        "messages": [{"role": "user", "content": "roll over my 401k to another plan"}],
        "verified": False, "collected_data": {},
    }, config)
    snap = _verify_otp(g, config, customer)
    assert snap.values["pending_card"].card_type == "rollover_out_form"
    acct = snap.values["pending_card"].accounts[0]["id"]
    snap = _walk(g, Command(resume={
        "from_account_id": acct,
        "destination_plan_name": "Fidelity IRA",
        "destination_account_last4": "1234",
        "amount": 20000.0,
        "method": "direct",
    }), config)
    snap = _walk(g, Command(resume={"_confirmed": True}), config)
    final = snap.values.get("final_card")
    assert final is not None and final.card_type == "specialist_routing"


def test_rollover_in_no_verify():
    g, repo, config, tid = _new_graph_and_config()
    snap = _walk(g, {
        "customer_id": "demo-002", "thread_id": tid,
        "intent": "rollover_in",
        "messages": [{"role": "user", "content": "roll over funds in from another plan"}],
        "verified": False, "collected_data": {},
    }, config)
    # rollover_in skips identity verification
    assert _is_paused(snap)
    assert snap.values["pending_card"].card_type == "rollover_in_form"
    acct = snap.values["pending_card"].accounts[0]["id"]
    snap = _walk(g, Command(resume={
        "target_account_id": acct,
        "source_plan_name": "Vanguard Solo 401k",
        "source_ein": None,
        "amount_estimate": 12000.0,
    }), config)
    final = snap.values.get("final_card")
    assert final is not None and final.card_type == "specialist_routing"


def test_qdro_specialist_routing():
    g, repo, config, tid = _new_graph_and_config()
    customer = repo.get_customer("demo-002")
    snap = _walk(g, {
        "customer_id": "demo-002", "thread_id": tid,
        "intent": "qdro",
        "messages": [{"role": "user", "content": "qdro intake"}],
        "verified": False, "collected_data": {},
    }, config)
    snap = _verify_otp(g, config, customer)
    assert snap.values["pending_card"].card_type == "qdro_form"
    snap = _walk(g, Command(resume={
        "case_number": "2026-FAM-001",
        "court": "San Francisco Superior",
        "doc_file_name": "qdro.pdf",
    }), config)
    final = snap.values.get("final_card")
    assert final is not None and final.card_type == "specialist_routing"


# ------------------------------------------------------------------
# Cross-cutting
# ------------------------------------------------------------------

def test_idempotency_replay_email_change():
    """Calling the same persister twice with the same idempotency key returns duplicate=True."""
    repo = Repository(get_db())
    key = "test-idempotency-replay-001"
    r1 = repo.update_email(
        customer_id="demo-001", thread_id="tid-1",
        new_email="newer@example.com", idempotency_key=key,
    )
    assert not r1.duplicate
    r2 = repo.update_email(
        customer_id="demo-001", thread_id="tid-1",
        new_email="newer@example.com", idempotency_key=key,
    )
    assert r2.duplicate
    assert r1.request_id == r2.request_id


def test_cancel_request_only_pending():
    """Completed requests cannot be cancelled."""
    repo = Repository(get_db())
    # Mark the seeded pending request as completed first
    repo.conn.execute(
        "UPDATE requests SET status = 'completed' WHERE customer_id = 'demo-001' AND status = 'pending'"
    )
    repo.conn.commit()
    completed = [r for r in repo.list_requests("demo-001") if r["status"] == "completed"]
    assert completed
    with pytest.raises(ValueError, match="not cancellable"):
        repo.cancel_request(
            customer_id="demo-001", thread_id=None,
            request_id=completed[0]["id"], idempotency_key="test-cancel-completed",
        )
