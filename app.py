"""Streamlit chat for the retirement-account agent.

Bridges Streamlit's per-rerun loop with LangGraph's interrupt/resume model:
- @st.cache_resource keeps the compiled graph alive across reruns
- thread_id stays stable in session_state
- The graph is the source of truth for orchestration state; session_state holds only the chat history.
"""
from __future__ import annotations

import html
import os
import uuid
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

from agents.graph import build_graph
from db.connection import get_db
from db.repository import Repository
from ui.cards import render_card
from ui.chat import render_chat_history, render_quick_actions
from ui.styles import icon_html, inject_global_css

load_dotenv()


# ---------- page setup ----------

st.set_page_config(
    page_title="RetireSafe — Account Support",
    page_icon=":material/savings:",
    layout="centered",
)
inject_global_css()


# ---------- cached resources ----------

@st.cache_resource
def _repo() -> Repository:
    return Repository(get_db())


@st.cache_resource
def _graph():
    return build_graph(_repo())


repo = _repo()
graph = _graph()


# ---------- session state ----------

def _new_session() -> None:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.history = []
    st.session_state.pending_prompt = None


if "thread_id" not in st.session_state:
    _new_session()
if "customer_id" not in st.session_state:
    st.session_state.customer_id = "demo-001"
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None


# ---------- customer (fetched once, shared across sidebar + main) ----------

c = repo.get_customer(st.session_state.customer_id)


# ---------- sidebar ----------

with st.sidebar:
    st.markdown(
        f"""
        <div class="rs-brand-mark">
          <span class="rs-brand-logo">{icon_html("savings", size=22)}</span>
          <div>
            <div class="rs-brand-name">RetireSafe</div>
            <div class="rs-brand-tag">Secure Account Support</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if c:
        initial = (c["first_name"][:1] or "?").upper()
        st.markdown(
            f"""
            <div class="rs-cust-card">
              <div class="rs-cust-avatar">{html.escape(initial)}</div>
              <div>
                <div class="rs-cust-name">{html.escape(c["first_name"])} {html.escape(c["last_name"])}</div>
                <div class="rs-cust-id">Member · {html.escape(st.session_state.customer_id)}</div>
                <div class="rs-cust-lastlogin">Last sign-in · 2 hours ago</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.button("New conversation", use_container_width=True):
        _new_session()
        st.rerun()

    st.markdown('<div class="rs-section-label">Quick actions</div>', unsafe_allow_html=True)
    quick_actions = [
        ("Check balance", "What's my balance?"),
        ("Recent transactions", "Show my recent transactions"),
        ("Update address", "I want to change my address"),
        ("Add beneficiary", "Add a beneficiary"),
        ("Request status", "What's the status of my requests?"),
    ]
    for label, prompt in quick_actions:
        if st.button(label, key=f"qa-side-{label}", use_container_width=True):
            st.session_state.pending_prompt = prompt
            st.rerun()

    st.markdown('<div class="rs-section-label">Need help?</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="rs-contact-card">
          <div class="rs-contact-line">{icon_html("call", size=16)} 1-800-555-7483</div>
          <div class="rs-contact-line">{icon_html("schedule", size=16)} Mon – Fri · 8 am – 8 pm ET</div>
          <div class="rs-security-badge">{icon_html("lock", size=14)} Encrypted · TLS 1.3</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Sign out", key="signout", use_container_width=True):
        st.toast("Signed out (mock).", icon="🔒")


# ---------- main column ----------

st.title("Account support")
if c:
    st.caption(f"Signed in as **{c['first_name']} {c['last_name']}**")


config = {"configurable": {"thread_id": st.session_state.thread_id}}


# ---------- helpers ----------

def _absorb_run(payload: Any, *, spinner_label: str = "Working...") -> None:
    """Run the graph and absorb assistant messages into history.

    Uses stream_mode='values' so we can spot routing_announcement and final_message
    transitions as nodes execute. Wrapped in a Streamlit spinner so the user sees
    activity during slow nodes (LLM classifier, DB writes).
    """
    seen_announcement = None
    seen_final_message = None
    with st.spinner(spinner_label, show_time=True):
        for ev in graph.stream(payload, config, stream_mode="values"):
            ann = ev.get("routing_announcement")
            if ann and ann != seen_announcement:
                st.session_state.history.append({"role": "assistant", "content": ann})
                seen_announcement = ann
            msg = ev.get("final_message")
            if msg and msg != seen_final_message:
                st.session_state.history.append({"role": "assistant", "content": msg})
                seen_final_message = msg


def _archive_card_summary(card, submission: dict[str, Any]) -> None:
    """Append a short user-visible breadcrumb so submitted cards stay in the chat scroll."""
    if submission.get("_cancelled"):
        st.session_state.history.append({"role": "system", "content": "_Request cancelled._"})
        return
    if submission.get("_confirmed") or submission.get("_acknowledged"):
        return  # the success card itself is the summary; nothing extra needed
    if card.card_type == "identity_verification":
        st.session_state.history.append({"role": "system", "content": "_Identity verified._"})
    elif card.card_type == "otp":
        st.session_state.history.append({"role": "system", "content": "_Verification code submitted._"})
    elif card.card_type == "address_form":
        addr = submission
        st.session_state.history.append({
            "role": "user",
            "content": f"New address: {addr['address_line1']}, {addr['address_city']}, {addr['address_state']} {addr['address_postal']}",
        })
    elif card.card_type == "phone_form":
        st.session_state.history.append({"role": "user", "content": f"New phone: {submission['phone']}"})
    elif card.card_type == "email_form":
        st.session_state.history.append({"role": "user", "content": f"New email: {submission['email']}"})
    elif card.card_type == "name_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"New legal name: {submission['first_name']} {submission['last_name']}",
        })
    elif card.card_type == "beneficiary_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"Beneficiary: {submission['name']} ({submission['relationship']}, {submission['allocation_pct']}%)",
        })
    elif card.card_type == "beneficiary_picker":
        action = submission.get("action", "add")
        st.session_state.history.append({"role": "user", "content": f"_Beneficiary action: {action}_"})
    elif card.card_type == "contribution_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"New contribution: {submission['contribution_pct']:.1f}%",
        })
    elif card.card_type == "allocation_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"_New target allocation submitted ({len(submission.get('allocations', []))} funds)._",
        })
    elif card.card_type == "drift_view":
        st.session_state.history.append({"role": "system", "content": "_Rebalance plan acknowledged._"})
    elif card.card_type == "tax_withholding_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"Withholding: Federal {submission['federal_pct']:.1f}% / {submission['state_code']} {submission['state_pct']:.1f}%",
        })
    elif card.card_type == "bank_account_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"New bank: {submission['nickname']} (…{submission['account_last4']})",
        })
    elif card.card_type == "microdeposit":
        st.session_state.history.append({"role": "system", "content": "_Microdeposit amounts submitted._"})
    elif card.card_type == "loan_request_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"Loan: ${submission['amount']:,.0f} over {submission['term_months']} mo",
        })
    elif card.card_type == "distribution_method":
        st.session_state.history.append({
            "role": "user",
            "content": f"Distribution method: {submission['method'].replace('_', ' ')}",
        })
    elif card.card_type == "distribution_request_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"Distribution: ${submission['amount']:,.0f}",
        })
    elif card.card_type == "mfa_device_list":
        st.session_state.history.append({
            "role": "user",
            "content": f"MFA action: {submission.get('action', 'enroll')}",
        })
    elif card.card_type == "mfa_enroll_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"New MFA device: {submission['label']} ({submission['kind'].upper()})",
        })
    elif card.card_type == "delivery_prefs_form":
        st.session_state.history.append({"role": "user", "content": "_Delivery preferences updated._"})
    elif card.card_type == "hardship_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"Hardship request: ${submission['amount']:,.0f} for {submission['reason'].replace('_', ' ')}",
        })
    elif card.card_type == "rollover_out_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"Rollover out: ${submission['amount']:,.0f} → {submission['destination_plan_name']}",
        })
    elif card.card_type == "rollover_in_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"Rollover in: ${submission['amount_estimate']:,.0f} from {submission['source_plan_name']}",
        })
    elif card.card_type == "qdro_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"QDRO intake: case {submission['case_number']}",
        })
    elif card.card_type == "statement_picker":
        st.session_state.history.append({
            "role": "user",
            "content": f"_Document requested: {submission['kind']} ({submission['period']})_",
        })
    elif card.card_type == "request_list":
        if "request_id" in submission:
            st.session_state.history.append({
                "role": "user",
                "content": f"Cancel request #{submission['request_id']}",
            })


def _archive_terminal_card(card) -> None:
    """Add a one-line breadcrumb for a dismissed terminal card."""
    if card.card_type == "balance_view":
        st.session_state.history.append({
            "role": "assistant",
            "content": f"Total balance: **${card.total_balance:,.2f}** (vested ${card.vested_balance:,.2f})",
        })
    elif card.card_type == "transaction_history":
        st.session_state.history.append({
            "role": "assistant",
            "content": f"Showed {len(card.transactions)} recent transactions.",
        })
    elif card.card_type == "loan_status":
        st.session_state.history.append({
            "role": "assistant",
            "content": f"Showed {len(card.loans)} loan(s).",
        })
    elif card.card_type == "request_list":
        st.session_state.history.append({
            "role": "assistant",
            "content": f"Showed {len(card.requests)} recent request(s).",
        })
    elif card.card_type == "document_link":
        st.session_state.history.append({
            "role": "assistant",
            "content": f"Document ready: {card.kind.replace('_', ' ')} ({card.period}).",
        })
    elif card.card_type == "success":
        rid = f" (#{card.request_id})" if card.request_id else ""
        st.session_state.history.append({"role": "assistant", "content": f"{card.title}{rid}"})
    elif card.card_type == "specialist_routing":
        st.session_state.history.append({
            "role": "assistant",
            "content": f"Routed to specialist (#{card.request_id}) · ETA {card.eta_business_days} business days.",
        })
    elif card.card_type == "password_reset_link":
        st.session_state.history.append({
            "role": "assistant",
            "content": f"Password reset link sent to {card.email_masked}.",
        })
    elif card.card_type == "not_implemented":
        st.session_state.history.append({
            "role": "assistant",
            "content": f"**{card.intent}** is not available through self-service at this time.",
        })


def _clear_terminal_state() -> None:
    """After dismissing a terminal card, wipe orchestration state but keep the thread + verification."""
    graph.update_state(
        config,
        {
            "intent": None,
            "current_step_idx": 0,
            "plan_complete": False,
            "pending_card": None,
            "final_card": None,
            "final_message": None,
            "last_error": None,
            "last_submission": None,
            "collected_data": {},
        },
    )


def _start_turn(user_text: str, is_paused: bool, values: dict[str, Any]) -> None:
    """Push a user message into the thread and run the graph from a fresh turn."""
    st.session_state.history.append({"role": "user", "content": user_text})
    if is_paused:
        # Cancel the in-flight flow first; cancel signal lands cleanly via the validator.
        for _ in graph.stream(Command(resume={"_cancelled": True}), config, stream_mode="values"):
            pass
        # Drop the cancel breadcrumb the validator adds — the user is mid-redirect, not done.
        if st.session_state.history and st.session_state.history[-1].get("role") == "system":
            st.session_state.history.pop()
    payload = {
        "customer_id": st.session_state.customer_id,
        "thread_id": st.session_state.thread_id,
        "messages": [{"role": "user", "content": user_text}],
        "verified": bool(values.get("verified")),
        "collected_data": {},
        "current_step_idx": 0,
        "plan_complete": False,
        "pending_card": None,
        "final_card": None,
        "final_message": None,
        "last_error": None,
        "last_submission": None,
    }
    _absorb_run(payload, spinner_label="Thinking...")


# ---------- render history first ----------

render_chat_history(st.session_state.history)


# ---------- handle the current state of the graph ----------

snap = graph.get_state(config)
values = snap.values or {}
pending_card = values.get("pending_card")
is_paused = bool(snap.next) and pending_card is not None

if is_paused:
    # Mid-flow card: form submission resumes the graph.
    card_key = f"card-{st.session_state.thread_id}-{values.get('current_step_idx', 0)}-{getattr(pending_card, 'card_type', 'x')}"
    submitted = render_card(pending_card, key=card_key)
    if submitted is not None:
        _archive_card_summary(pending_card, submitted)
        label = "Saving your changes..." if pending_card.card_type == "confirmation" else "Working..."
        _absorb_run(Command(resume=submitted), spinner_label=label)
        st.rerun()

elif values.get("final_card") is not None:
    # Terminal inform card (success / balance / not_implemented). Render until dismissed.
    final_card = values["final_card"]
    card_key = f"card-{st.session_state.thread_id}-final-{values.get('intent')}"
    submitted = render_card(final_card, key=card_key)
    if submitted is not None:
        _archive_terminal_card(final_card)
        _clear_terminal_state()
        st.rerun()


# ---------- chip row when chat is empty ----------

if not st.session_state.history and not is_paused and values.get("final_card") is None:
    chip = render_quick_actions()
    if chip:
        st.session_state.pending_prompt = chip
        st.rerun()


# ---------- compliance footer ----------

st.markdown(
    """
    <div class="rs-footer">
      RetireSafe is a fictional demo. Not affiliated with any real plan provider.
      Mocked data for demonstration only. Investments carry risk; consult a licensed
      advisor before taking distributions, loans, or rollovers.
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------- chat input ----------

# Resolve any quick-action pending prompt set by sidebar or chip row.
if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    _start_turn(prompt, is_paused, values)
    st.rerun()

user_text = st.chat_input("How can I help?")
if user_text:
    _start_turn(user_text, is_paused, values)
    st.rerun()
