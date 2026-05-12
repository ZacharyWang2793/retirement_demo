"""Streamlit chat for the retirement-account agent.

Bridges Streamlit's per-rerun loop with LangGraph's interrupt/resume model:
- @st.cache_resource keeps the compiled graph alive across reruns
- thread_id stays stable in session_state
- The graph is the source of truth for orchestration state; session_state holds only the chat history.
"""
from __future__ import annotations

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
from ui.chat import render_chat_history

load_dotenv()


# ---------- page setup ----------

st.set_page_config(
    page_title="Retirement Account Support",
    page_icon=":material/savings:",
    layout="centered",
)

# Streamlit's default chat avatar tints (red for user, orange for assistant) override here.
# Targets every test-id variant Streamlit has used across recent versions so the rule
# applies regardless of minor version drift.
st.markdown(
    """
    <style>
    [data-testid="stChatMessageAvatarUser"],
    [data-testid="chatAvatarIcon-user"] {
        background-color: #2563EB !important;   /* blue-600 — matches primary */
        color: #FFFFFF !important;
    }
    [data-testid="stChatMessageAvatarAssistant"],
    [data-testid="chatAvatarIcon-assistant"] {
        background-color: #0F172A !important;   /* slate-900 — near-black */
        color: #FFFFFF !important;
    }
    [data-testid="stChatMessageAvatarUser"] svg,
    [data-testid="chatAvatarIcon-user"] svg,
    [data-testid="stChatMessageAvatarAssistant"] svg,
    [data-testid="chatAvatarIcon-assistant"] svg {
        fill: #FFFFFF !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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


if "thread_id" not in st.session_state:
    _new_session()
if "customer_id" not in st.session_state:
    st.session_state.customer_id = "demo-001"


# ---------- sidebar ----------

with st.sidebar:
    st.subheader("Demo controls")

    customers = repo.list_customers()
    selected = st.selectbox(
        "Customer",
        options=[c["id"] for c in customers],
        index=[c["id"] for c in customers].index(st.session_state.customer_id),
        format_func=lambda cid: next(
            f"{c['first_name']} {c['last_name']} ({cid})" for c in customers if c["id"] == cid
        ),
    )
    if selected != st.session_state.customer_id:
        st.session_state.customer_id = selected
        _new_session()
        st.rerun()

    if st.button("Reset conversation", use_container_width=True):
        _new_session()
        st.rerun()

    st.divider()
    c = repo.get_customer(st.session_state.customer_id)
    if c:
        st.caption("**Demo identity:**")
        st.caption(f"DOB: `{c['dob']}`")
        st.caption(f"SSN last-4: `{c['ssn_last4']}`")
        st.caption("OTP: `123456`")

    st.divider()
    st.caption("**Try saying:**")
    st.caption("• Change my address")
    st.caption("• What's my balance?")
    st.caption("• Add a beneficiary")
    st.caption("• Update my contribution")
    st.caption("• Roll over my 401k")


# ---------- main column ----------

st.title("Retirement Account Support")
c = repo.get_customer(st.session_state.customer_id)
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
        st.session_state.history.append({"role": "system", "content": "_(cancelled)_"})
        return
    if submission.get("_confirmed") or submission.get("_acknowledged"):
        return  # the success card itself is the summary; nothing extra needed
    if card.card_type == "identity_verification":
        st.session_state.history.append({"role": "user", "content": "_(verified identity)_"})
    elif card.card_type == "otp":
        st.session_state.history.append({"role": "user", "content": "_(submitted verification code)_"})
    elif card.card_type == "address_form":
        addr = submission
        st.session_state.history.append({
            "role": "user",
            "content": f"New address: {addr['address_line1']}, {addr['address_city']}, {addr['address_state']} {addr['address_postal']}",
        })
    elif card.card_type == "phone_form":
        st.session_state.history.append({"role": "user", "content": f"New phone: {submission['phone']}"})
    elif card.card_type == "beneficiary_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"New beneficiary: {submission['name']} ({submission['relationship']}, {submission['allocation_pct']}%)",
        })
    elif card.card_type == "contribution_form":
        st.session_state.history.append({
            "role": "user",
            "content": f"New contribution: {submission['contribution_pct']:.1f}%",
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
    elif card.card_type == "success":
        rid = f" (#{card.request_id})" if card.request_id else ""
        st.session_state.history.append({"role": "assistant", "content": f"{card.title}{rid}"})
    elif card.card_type == "not_implemented":
        st.session_state.history.append({
            "role": "assistant",
            "content": f"Acknowledged — **{card.intent}** isn't implemented in this prototype.",
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


# ---------- chat input ----------

user_text = st.chat_input("How can I help?")
if user_text:
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
    st.rerun()
