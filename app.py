"""Streamlit chat for the retirement-account agent.

Bridges Streamlit's per-rerun loop with LangGraph's interrupt/resume model:
- @st.cache_resource keeps the compiled graph alive across reruns
- thread_id stays stable in session_state
- The graph is the source of truth for orchestration state; session_state holds only the chat history.
- Past conversations live in `st.session_state.conversations` so the sidebar can list them.
"""
from __future__ import annotations

import html
import os
import uuid
from datetime import datetime
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

from agents.graph import build_graph
from agents.intents import INTENT_LABELS
from db.connection import get_db
from db.repository import Repository
from ui.cards import render_card
from ui.chat import render_chat_history, render_quick_actions
from ui.styles import icon_html, inject_global_css

load_dotenv()


# ---------- page setup ----------

st.set_page_config(
    page_title="Meridian Retirement — Account Support",
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

def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _conv_title(history: list[dict[str, Any]]) -> str:
    """Fallback title: first user message truncated."""
    for m in history:
        if m.get("role") == "user":
            txt = (m.get("content") or "").strip()
            if txt:
                return txt[:36] + ("…" if len(txt) > 36 else "")
    return "New conversation"


def _generate_conv_title(history: list[dict[str, Any]]) -> str:
    """Ask the LLM for a 3-5 word sidebar title using the first few exchanges.

    Called on a deferred rerun so it never blocks the first response from rendering.
    Passes up to the first 4 messages (2 user + 2 assistant) so a greeting like
    "hi" resolves into the actual topic that emerged in the conversation.
    """
    # Build a short transcript from the first few meaningful turns
    snippet_msgs = [
        m for m in history[:6]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ][:4]

    if not snippet_msgs:
        return _conv_title(history)

    if not os.environ.get("AZURE_OPENAI_API_KEY"):
        return _conv_title(history)

    transcript = "\n".join(
        f"{m['role'].title()}: {(m['content'] or '')[:200]}"
        for m in snippet_msgs
    )
    try:
        from agents.nodes import _get_openai_client
        completion = _get_openai_client().chat.completions.create(
            model=os.environ["AZURE_MODEL_DEPLOYMENT"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write a sidebar title for a retirement account support conversation. "
                        "Rules: title case noun phrase, 3–6 words, no punctuation, no quotes. "
                        "Be specific — include names, account types, or dollar amounts when present. "
                        "If the conversation opens with a greeting or small talk, look past it to "
                        "the first real request. Never start with 'How', 'What', 'Can', or other "
                        "question words. Examples of good titles: 'Add Sarah Lee Beneficiary', "
                        "'401k Rollover to IRA', 'Change Home Address', 'Required Minimum Distribution'. "
                        "Reply with ONLY the title."
                    ),
                },
                {"role": "user", "content": transcript},
            ],
            temperature=0.3,
            max_tokens=15,
        )
        title = (completion.choices[0].message.content or "").strip().strip("\"'")
        return title[:50] if title else _conv_title(history)
    except Exception:
        return _conv_title(history)


def _group_conversations(convs: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group past conversations by time period (most recent first within each group)."""
    groups: dict[str, list] = {}
    order: list[str] = []
    now = datetime.utcnow()
    for conv in reversed(convs):  # most-recent first
        try:
            ts = datetime.fromisoformat(conv["last_at"].replace("Z", ""))
            delta = now - ts
            if delta.days == 0:
                label = "Today"
            elif delta.days == 1:
                label = "Yesterday"
            elif delta.days < 7:
                label = "Previous 7 days"
            elif delta.days < 30:
                label = "Previous 30 days"
            else:
                label = ts.strftime("%B %Y")
        except Exception:
            label = "Older"
        if label not in groups:
            groups[label] = []
            order.append(label)
        groups[label].append(conv)
    return [(k, groups[k]) for k in order]


def _bust_sidebar_cache() -> None:
    """Drop cached customer/balance so they refresh on the next rerun after a mutation."""
    st.session_state.pop("cached_customer", None)
    st.session_state.pop("cached_balance", None)


def _archive_current_conversation() -> None:
    """Snapshot the active thread into the conversations list (if it has any history)."""
    history = st.session_state.get("history") or []
    if not history:
        return
    tid = st.session_state.thread_id
    convs = st.session_state.conversations
    record = {
        "thread_id": tid,
        "title": st.session_state.get("conv_title") or _conv_title(history),
        "started_at": st.session_state.get("started_at") or _now_iso(),
        "last_at": _now_iso(),
        "history": list(history),
    }
    # If this thread was already archived earlier, replace; else append.
    for i, c in enumerate(convs):
        if c["thread_id"] == tid:
            convs[i] = record
            return
    convs.append(record)


def _new_session(persist: bool = True) -> None:
    """Start a fresh conversation. By default archive the current one first."""
    if persist:
        _archive_current_conversation()
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.history = []
    st.session_state.started_at = _now_iso()
    st.session_state.pending_prompt = None
    st.session_state.proposed_intent = None
    st.session_state.conv_title = None
    st.session_state.pop("_pending_title", None)
    _bust_sidebar_cache()


def _switch_to_conversation(thread_id: str) -> None:
    """Make `thread_id` the active conversation, archiving the current one."""
    if thread_id == st.session_state.thread_id:
        return
    _archive_current_conversation()
    target = next((c for c in st.session_state.conversations if c["thread_id"] == thread_id), None)
    if target is None:
        return
    st.session_state.thread_id = target["thread_id"]
    st.session_state.history = list(target["history"])
    st.session_state.started_at = target["started_at"]
    st.session_state.pending_prompt = None
    st.session_state.conv_title = target.get("title")
    # Remove the now-active conversation from the archived list (it'll be re-archived on next switch).
    st.session_state.conversations = [
        c for c in st.session_state.conversations if c["thread_id"] != thread_id
    ]


if "conversations" not in st.session_state:
    st.session_state.conversations = []
if "thread_id" not in st.session_state:
    _new_session(persist=False)
if "customer_id" not in st.session_state:
    st.session_state.customer_id = "demo-001"
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "started_at" not in st.session_state:
    st.session_state.started_at = _now_iso()
if "proposed_intent" not in st.session_state:
    st.session_state.proposed_intent = None
if "conv_title" not in st.session_state:
    st.session_state.conv_title = None


# ---------- customer + account snapshot (cached per session) ----------

if "cached_customer" not in st.session_state:
    st.session_state.cached_customer = repo.get_customer(st.session_state.customer_id)
if "cached_balance" not in st.session_state:
    _cust = st.session_state.cached_customer
    st.session_state.cached_balance = (
        repo.get_balance_summary(st.session_state.customer_id) if _cust else None
    )
c = st.session_state.cached_customer
balance = st.session_state.cached_balance


# ---------- sidebar ----------

with st.sidebar:
    # Brand mark
    st.markdown(
        f"""
        <div class="rs-brand-mark">
          <span class="rs-brand-logo">{icon_html("savings", size=22)}</span>
          <div>
            <div class="rs-brand-name">Meridian Retirement</div>
            <div class="rs-brand-tag">Plan participant services</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Profile pill
    if c:
        initial = (c["first_name"][:1] or "?").upper()
        st.markdown(
            f"""
            <div class="rs-profile-pill">
              <span class="rs-profile-avatar">{html.escape(initial)}</span>
              <div>
                <div class="rs-profile-name">{html.escape(c["first_name"])} {html.escape(c["last_name"])}</div>
                <div class="rs-profile-id">Member · {html.escape(st.session_state.customer_id)}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Account snapshot (no jargon badges)
    if balance:
        acct_count = len(balance["accounts"])
        primary_type = balance["accounts"][0]["type"] if balance["accounts"] else "active"
        st.markdown(
            f"""
            <div class="rs-snap-card">
              <div class="rs-snap-label">Total balance</div>
              <div class="rs-snap-metric">${balance["total_balance"]:,.0f}</div>
              <div class="rs-snap-sub">${balance["vested_balance"]:,.0f} vested · {acct_count} account{"s" if acct_count != 1 else ""}</div>
              <div class="rs-snap-pills">
                <span class="rs-snap-pill">{html.escape(primary_type)}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # New conversation button — below balance card
    st.markdown('<div class="rs-new-conv-btn">', unsafe_allow_html=True)
    if st.button("✏  New conversation", use_container_width=True, key="new-conv"):
        _new_session(persist=True)
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Conversation history (ChatGPT-style) ──────────────────────────────
    current_history = st.session_state.get("history") or []
    convs = list(st.session_state.conversations)

    # Active conversation — section header + highlighted title
    if current_history:
        active_title = html.escape(
            st.session_state.get("conv_title") or _conv_title(current_history)
        )
        st.markdown(
            f'<div class="rs-section-label">Current</div>'
            f'<div class="rs-conv-active">{active_title}</div>',
            unsafe_allow_html=True,
        )

    # Past conversations grouped by time period
    if convs:
        for group_label, group_convs in _group_conversations(convs):
            st.markdown(
                f'<div class="rs-section-label">{group_label}</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="rs-conv-list">', unsafe_allow_html=True)
            for conv in group_convs:
                if st.button(
                    conv["title"],
                    key=f"conv-{conv['thread_id']}",
                    use_container_width=True,
                ):
                    _switch_to_conversation(conv["thread_id"])
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    elif not current_history:
        st.markdown(
            '<div class="rs-conv-empty">No conversations yet.<br>Ask a question below to start.</div>',
            unsafe_allow_html=True,
        )


# ---------- main column header ----------

if c:
    st.markdown(
        f'<h1 style="margin:0 0 4px 0;text-align:center;">Greetings, {html.escape(c["first_name"])}</h1>',
        unsafe_allow_html=True,
    )
else:
    st.markdown('<h1 style="margin:0 0 4px 0;text-align:center;">Greetings</h1>', unsafe_allow_html=True)


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
    seen_say = None
    # subgraphs=True so we also see announcements/answers emitted inside a category
    # subagent. With it, each event is a (namespace, state) tuple — normalize below.
    with st.spinner(spinner_label, show_time=True):
        for ev in graph.stream(payload, config, stream_mode="values", subgraphs=True):
            state = ev[1] if isinstance(ev, tuple) else ev
            if not isinstance(state, dict):
                continue
            ann = state.get("routing_announcement")
            if ann and ann != seen_announcement:
                st.session_state.history.append({"role": "assistant", "content": ann})
                seen_announcement = ann
            say = state.get("assistant_say")
            if say and say != seen_say:
                st.session_state.history.append({"role": "assistant", "content": say})
                seen_say = say
            msg = state.get("final_message")
            if msg and msg != seen_final_message:
                st.session_state.history.append({"role": "assistant", "content": msg})
                seen_final_message = msg
            if "proposed_intent" in state:
                st.session_state.proposed_intent = state["proposed_intent"]


def _archive_card_summary(card, submission: dict[str, Any]) -> None:
    """Append a short user-visible breadcrumb so submitted cards stay in the chat scroll."""
    if submission.get("_cancelled"):
        st.session_state.history.append({"role": "system", "content": "_Request cancelled._"})
        return
    if submission.get("_confirmed") or submission.get("_acknowledged"):
        return  # the success card itself is the summary; nothing extra needed
    # identity_verification and otp steps are always skipped (verified=True); no cases needed.
    if card.card_type == "address_form":
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


def _store_card_in_history(card) -> None:
    """Persist a dismissed terminal card into session history as a serialised spec.

    The chat-history renderer detects entries with role='card' and re-renders
    them via `render_card_readonly`, so the full card UI stays visible in the
    scroll instead of degrading to a plain-text breadcrumb.
    """
    try:
        card_data = card.model_dump()
    except Exception:
        return  # Graceful fallback: skip cards that can't serialise
    st.session_state.history.append({
        "role": "card",
        "card_type": card.card_type,
        "card_data": card_data,
    })


def _clear_terminal_state() -> None:
    """After dismissing a terminal card, wipe orchestration state but keep the thread + verification."""
    graph.update_state(
        config,
        {
            "intent": None,
            "active_category": None,
            "active_intent": None,
            "route_to": None,
            "last_handback": None,
            "pending_card": None,
            "final_card": None,
            "final_message": None,
            "assistant_say": None,
            "last_error": None,
        },
    )
    _bust_sidebar_cache()  # balance may have changed if a transaction was persisted


def _read_graph_state():
    """Read the current snapshot, surfacing the pending card even when the interrupt
    is suspended INSIDE a category subagent subgraph.

    While a subagent is paused, its (shared) pending_card is not yet committed to the
    parent state — so we walk snap.tasks to the deepest pending task and read its
    card there. Once a subagent completes, final_card surfaces at the parent normally.
    Returns (snap, parent_values, pending_card, step_idx, is_paused).
    """
    snap = graph.get_state(config, subgraphs=True)
    values = snap.values or {}
    pending = None
    step_idx = 0
    stack = list(snap.tasks or [])
    while stack:
        t = stack.pop()
        cs = getattr(t, "state", None)
        cv = getattr(cs, "values", None) if cs is not None else None
        if cv is not None:
            if cv.get("pending_card") is not None:
                pending = cv["pending_card"]
                step_idx = cv.get("current_step_idx", 0)
            stack.extend(getattr(cs, "tasks", []) or [])
        if getattr(t, "interrupts", None) and pending is None:
            pending = t.interrupts[0].value
    if pending is None:
        pending = values.get("pending_card")
    return snap, values, pending, step_idx, bool(snap.next) and pending is not None


def _run_pending_turn(pt: dict[str, Any]) -> None:
    """Execute a deferred graph turn with a typing indicator in the chat thread.

    Called on the rerun *after* the user message has already been appended to
    history and rendered, so the user sees their bubble instantly.  The typing
    indicator is written to an st.empty() placeholder before _absorb_run blocks;
    Streamlit flushes the render tree to the browser when the spinner activates,
    so the dots are visible throughout graph execution.
    """
    user_text = pt["user_text"]
    is_paused = pt["is_paused"]

    # Typing indicator — appears while the graph runs below
    typing_ph = st.empty()
    with typing_ph:
        with st.chat_message("assistant"):
            st.markdown(
                '<div class="rs-typing-indicator">'
                '<div class="rs-typing-dot"></div>'
                '<div class="rs-typing-dot"></div>'
                '<div class="rs-typing-dot"></div>'
                '</div>',
                unsafe_allow_html=True,
            )

    if is_paused:
        # A subagent card is on screen and the member typed instead of submitting it.
        # Route the text INTO the active subagent so its brain can answer an in-domain
        # question, switch tasks, or cancel — rather than dropping the whole flow.
        _absorb_run(Command(resume={"_user_text": user_text}), spinner_label="Thinking...")
    else:
        payload = {
            "customer_id": st.session_state.customer_id,
            "thread_id": st.session_state.thread_id,
            "messages": [{"role": "user", "content": user_text}],
            "verified": True,  # user is already authenticated; skip identity/OTP steps
        }
        _absorb_run(payload, spinner_label="Thinking...")
    typing_ph.empty()

    # Flag that a title is needed — generated on the *next* rerun so it never
    # blocks the first response from appearing.
    if st.session_state.get("conv_title") is None:
        st.session_state._pending_title = True


# ---------- render history first ----------

render_chat_history(st.session_state.history)


# ---------- deferred title generation ----------
# Runs on the rerun *after* the first response renders, so the LLM title call
# never adds latency to showing the first message.

if st.session_state.pop("_pending_title", False) and st.session_state.get("conv_title") is None:
    st.session_state.conv_title = _generate_conv_title(st.session_state.history)


# ---------- deferred turn: user message already rendered; now run the graph ----------
# The chat-input and chip handlers append the user bubble to history and set
# _pending_turn, then rerun immediately so the bubble appears < 5 ms after Enter.
# On *this* rerun we see the bubble in render_chat_history above, then show the
# typing indicator here while the graph executes synchronously below.

if pt := st.session_state.pop("_pending_turn", None):
    _run_pending_turn(pt)
    st.rerun()


# ---------- handle the current state of the graph ----------

snap, values, pending_card, step_idx, is_paused = _read_graph_state()

if is_paused:
    # Mid-flow card (interrupt suspended inside a category subagent): form submission
    # resumes the graph; typing into the chat box routes the text into the subagent.
    card_key = f"card-{st.session_state.thread_id}-{values.get('active_intent', '')}-{step_idx}-{getattr(pending_card, 'card_type', 'x')}"
    submitted = render_card(pending_card, key=card_key)
    if submitted is not None:
        _archive_card_summary(pending_card, submitted)
        label = "Saving your changes..." if pending_card.card_type == "confirmation" else "Working..."
        _absorb_run(Command(resume=submitted), spinner_label=label)
        st.rerun()

elif values.get("final_card") is not None:
    # Terminal card arrived — persist it to history immediately (no "Done" click needed)
    # and reset orchestration state. The card will render read-only via
    # render_chat_history on the very next pass, leaving the chat input free.
    _store_card_in_history(values["final_card"])
    _clear_terminal_state()
    st.rerun()


# ---------- proposed-intent confirmation chips ----------

_pending_pi = st.session_state.get("proposed_intent")
if _pending_pi and not is_paused:
    _pi_label = INTENT_LABELS.get(_pending_pi, _pending_pi)
    _pi_col1, _pi_col2, _ = st.columns([2, 2, 6], gap="small")
    with _pi_col1:
        if st.button("Yes, start now", key="pi-yes", type="primary", use_container_width=True):
            st.session_state.history.append({"role": "user", "content": "Yes, let's do it"})
            st.session_state._pending_turn = {"user_text": "Yes, let's do it", "is_paused": False}
            st.rerun()
    with _pi_col2:
        if st.button("No thanks", key="pi-no", use_container_width=True):
            st.session_state.history.append({"role": "user", "content": "No thanks"})
            st.session_state._pending_turn = {"user_text": "No thanks", "is_paused": False}
            st.rerun()


# ---------- parked-task resume chips ----------
# After a cross-category pivot, the orchestrator parks the prior task. Offer to resume it.

_parked = values.get("parked_task")
if _parked and not is_paused and not _pending_pi:
    _pk_label = _parked.get("label", "your previous task")
    _pk_col1, _pk_col2, _ = st.columns([2, 2, 6], gap="small")
    with _pk_col1:
        if st.button(f"Resume {_pk_label.lower()}", key="pk-yes", type="primary", use_container_width=True):
            st.session_state.history.append({"role": "user", "content": f"Let's resume {_pk_label.lower()}"})
            graph.update_state(config, {"parked_task": None})
            # Re-open the parked task with its saved progress (resume_payload flows into
            # the subagent's cat_init, which rehydrates step + collected data).
            _absorb_run(
                {
                    "customer_id": st.session_state.customer_id,
                    "thread_id": st.session_state.thread_id,
                    "verified": True,
                    "intent": _parked.get("intent"),
                    "resume_payload": {
                        "current_step_idx": _parked.get("resume_step_idx", 0),
                        "collected_data": _parked.get("collected_data", {}),
                    },
                    "messages": [],
                },
                spinner_label="Picking that back up...",
            )
            st.rerun()
    with _pk_col2:
        if st.button("Not now", key="pk-no", use_container_width=True):
            graph.update_state(config, {"parked_task": None})
            st.rerun()


# ---------- chip row when chat is empty ----------

if not st.session_state.history and not is_paused:
    chip = render_quick_actions()
    if chip:
        st.session_state.pending_prompt = chip
        st.rerun()


# ---------- chat input ----------

# Resolve any quick-action pending prompt set by the empty-state chip row.
# Uses the same two-step pattern: append message now so it renders immediately,
# then defer graph execution to the next rerun via _pending_turn.
if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    st.session_state.history.append({"role": "user", "content": prompt})
    st.session_state._pending_turn = {"user_text": prompt, "is_paused": False}
    st.rerun()

user_text = st.chat_input("How can I help?")
if user_text:
    # Store any lingering terminal card before starting a new turn.
    if values.get("final_card") is not None:
        _store_card_in_history(values["final_card"])
        _clear_terminal_state()
    # Append message immediately — it renders on the very next rerun (< 5 ms).
    # Graph execution is deferred to the rerun after that via _pending_turn.
    st.session_state.history.append({"role": "user", "content": user_text})
    st.session_state._pending_turn = {"user_text": user_text, "is_paused": is_paused}
    st.rerun()
