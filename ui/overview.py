"""Account overview page — read-only snapshot of balance, accounts, activity,
beneficiaries, pending requests, and security. No graph interaction; this is
the at-a-glance view. Transactions happen on the Chat page.
"""
from __future__ import annotations

import html
from typing import Any, Callable

import streamlit as st

from db.repository import Repository
from ui.styles import icon_html


def _section_header(title: str, icon: str, action_label: str | None = None,
                    action_cb: Callable[[], None] | None = None, key: str = "") -> None:
    cols = st.columns([4, 1])
    with cols[0]:
        st.markdown(
            f"""
            <div class="rs-section-head">
              <span class="rs-section-icon">{icon_html(icon, size=18)}</span>
              <span class="rs-section-title">{html.escape(title)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    if action_label and action_cb:
        with cols[1]:
            if st.button(action_label, key=f"sect-{key}", use_container_width=True):
                action_cb()


def _hero(balance: dict[str, Any], customer: dict[str, Any]) -> None:
    pills_html = "".join(
        f'<span class="rs-snap-pill alt">{html.escape(a["plan_name"])}</span>'
        for a in balance["accounts"]
    )
    st.markdown(
        f"""
        <div class="rs-overview-hero">
          <div class="rs-overview-hero-left">
            <div class="rs-hero-label">Portfolio balance</div>
            <div class="rs-overview-metric">${balance["total_balance"]:,.2f}</div>
            <div class="rs-hero-sub">${balance["vested_balance"]:,.2f} vested across {len(balance["accounts"])} account{"s" if len(balance["accounts"]) != 1 else ""}</div>
            <div class="rs-overview-pills">{pills_html}</div>
          </div>
          <div class="rs-overview-hero-right">
            <div class="rs-overview-hero-chip">{icon_html("trending_up", 14)} +0.34% today</div>
            <div class="rs-overview-hero-chip">{icon_html("verified_user", 14)} secured</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _accounts_grid(balance: dict[str, Any]) -> None:
    cards_html = "".join(
        (
            '<div class="rs-account-card">'
            f'<div class="rs-account-plan">{html.escape(a["plan_name"])}</div>'
            f'<div class="rs-account-tag">{html.escape(a["type"])}</div>'
            f'<div class="rs-account-balance">${a["balance"]:,.2f}</div>'
            f'<div class="rs-account-vested">${a["vested_balance"]:,.2f} vested</div>'
            "</div>"
        )
        for a in balance["accounts"]
    )
    st.markdown(f'<div class="rs-account-grid">{cards_html}</div>', unsafe_allow_html=True)


def _activity(repo: Repository, customer_id: str) -> None:
    txns = repo.get_transactions(customer_id, limit=6)
    if not txns:
        st.markdown(
            '<div class="rs-empty">No recent transactions on file.</div>',
            unsafe_allow_html=True,
        )
        return
    rows_html = ""
    for t in txns:
        amt = float(t["amount"])
        sign = "+" if amt > 0 else ""
        cls = "rs-txn-amt-pos" if amt > 0 else ("rs-txn-amt-neg" if amt < 0 else "rs-txn-amt-neu")
        rows_html += (
            '<div class="rs-txn-row">'
            f'<div class="rs-txn-date">{html.escape(t["txn_date"])}</div>'
            f'<div class="rs-txn-body"><span class="rs-txn-type">{html.escape(t["txn_type"].replace("_", " "))}</span>'
            f'<span class="rs-txn-desc">{html.escape(t.get("description") or "")}</span></div>'
            f'<div class="rs-txn-amt {cls}">{sign}${abs(amt):,.2f}</div>'
            "</div>"
        )
    st.markdown(f'<div class="rs-overview-card"><div class="rs-txn-list">{rows_html}</div></div>',
                unsafe_allow_html=True)


def _requests(repo: Repository, customer_id: str) -> None:
    rows = repo.list_requests(customer_id, limit=5)
    if not rows:
        st.markdown(
            '<div class="rs-empty">No requests in flight. You\'re all caught up.</div>',
            unsafe_allow_html=True,
        )
        return
    body = ""
    for r in rows:
        body += (
            '<div class="rs-list-row">'
            f'<div><div class="rs-list-title">{html.escape(r["type"].replace("_", " ").title())}</div>'
            f'<div class="rs-list-meta">#{html.escape(r["id"])} · {html.escape(r["created_at"][:10])}</div></div>'
            f'<span class="rs-status-pill rs-status-{html.escape(r["status"])}">{html.escape(r["status"])}</span>'
            "</div>"
        )
    st.markdown(f'<div class="rs-overview-card">{body}</div>', unsafe_allow_html=True)


def _beneficiaries(repo: Repository, customer_id: str) -> None:
    bens = repo.get_beneficiaries(customer_id)
    if not bens:
        st.markdown(
            '<div class="rs-empty">No beneficiaries on file. Add one on the Chat page.</div>',
            unsafe_allow_html=True,
        )
        return
    body = ""
    for b in bens:
        body += (
            '<div class="rs-list-row">'
            f'<div><div class="rs-list-title">{html.escape(b["name"])}</div>'
            f'<div class="rs-list-meta">{html.escape(b["relationship"].title())} · {html.escape(b["type"])} · {html.escape(b["plan_name"])}</div></div>'
            f'<span class="rs-status-pill rs-status-completed">{b["allocation_pct"]:.0f}%</span>'
            "</div>"
        )
    st.markdown(f'<div class="rs-overview-card">{body}</div>', unsafe_allow_html=True)


def _loans_and_contributions(repo: Repository, customer_id: str) -> None:
    loans = repo.list_loans(customer_id)
    accounts = repo.get_accounts(customer_id)
    contrib_rows = []
    for a in accounts:
        if a["account_type"] not in ("401k", "roth_401k"):
            continue
        c = repo.get_contribution(a["id"])
        if c:
            contrib_rows.append({
                "plan": a["plan_name"], "pct": c["contribution_pct"],
                "match": c["employer_match_pct"],
            })

    cols = st.columns(2)
    with cols[0]:
        st.markdown('<div class="rs-mini-label">Loans</div>', unsafe_allow_html=True)
        if not loans:
            st.markdown('<div class="rs-empty rs-empty-sm">No active loans.</div>',
                        unsafe_allow_html=True)
        else:
            for l in loans:
                st.markdown(
                    f"""
                    <div class="rs-mini-card">
                      <div class="rs-mini-title">{html.escape(l["plan_name"])}</div>
                      <div class="rs-mini-metric">${l["outstanding"]:,.2f}</div>
                      <div class="rs-mini-sub">{l["interest_rate"]:.2f}% · {l["term_months"]} mo · next {html.escape(l.get("next_payment_due") or "—")}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    with cols[1]:
        st.markdown('<div class="rs-mini-label">Contributions</div>', unsafe_allow_html=True)
        if not contrib_rows:
            st.markdown('<div class="rs-empty rs-empty-sm">No contribution election on file.</div>',
                        unsafe_allow_html=True)
        else:
            for r in contrib_rows:
                st.markdown(
                    f"""
                    <div class="rs-mini-card">
                      <div class="rs-mini-title">{html.escape(r["plan"])}</div>
                      <div class="rs-mini-metric">{r["pct"]:.1f}%</div>
                      <div class="rs-mini-sub">Employer match {r["match"]:.1f}%</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def _security(repo: Repository, customer_id: str) -> None:
    devices = repo.list_mfa_devices(customer_id)
    delivery = repo.get_delivery_prefs(customer_id) or {}
    parts = []
    parts.append(
        f'<span class="rs-pill rs-pill-mint">{icon_html("security", 12)} {len(devices)} MFA device{"s" if len(devices) != 1 else ""}</span>'
    )
    if delivery.get("paperless_statements"):
        parts.append(f'<span class="rs-pill rs-pill-violet">{icon_html("mail_lock", 12)} Paperless statements</span>')
    if delivery.get("paperless_tax"):
        parts.append(f'<span class="rs-pill rs-pill-sky">{icon_html("receipt", 12)} Paperless tax</span>')
    parts.append(f'<span class="rs-pill rs-pill-cream">{icon_html("lock", 12)} TLS 1.3</span>')
    st.markdown(
        f'<div class="rs-overview-card rs-pill-row">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def render_overview(repo: Repository, customer_id: str, on_go_chat: Callable[[], None]) -> None:
    """Render the read-only account overview. `on_go_chat` is invoked when the
    user clicks the 'Make a change' CTA — caller should switch to the chat page
    and trigger st.rerun()."""
    customer = repo.get_customer(customer_id)
    balance = repo.get_balance_summary(customer_id)

    _hero(balance, customer)

    _section_header("Your accounts", "account_balance", key="accounts")
    _accounts_grid(balance)

    _section_header("Recent activity", "receipt_long", key="activity")
    _activity(repo, customer_id)

    _section_header("Pending requests", "list_alt", key="requests")
    _requests(repo, customer_id)

    _section_header("Beneficiaries", "family_restroom", key="beneficiaries")
    _beneficiaries(repo, customer_id)

    st.markdown('<div class="rs-section-divider"></div>', unsafe_allow_html=True)
    _loans_and_contributions(repo, customer_id)

    st.markdown('<div class="rs-section-divider"></div>', unsafe_allow_html=True)
    _section_header("Security & delivery", "shield", key="security")
    _security(repo, customer_id)

    # Footer CTA — entry point into the chat
    st.markdown(
        """
        <div class="rs-overview-cta">
          <div>
            <div class="rs-cta-title">Need to make a change?</div>
            <div class="rs-cta-sub">Update your beneficiaries, take a distribution, or roll over funds — all from one chat.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open the support chat →", key="overview-go-chat", type="primary", use_container_width=True):
        on_go_chat()
        st.rerun()
