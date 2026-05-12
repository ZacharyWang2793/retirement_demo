"""Streamlit renderers — one per card type.

Each render function returns:
- dict: the user submitted the form (data to resume the graph with)
- None: the user hasn't submitted yet (Streamlit will rerun on next interaction)

A "Cancel" button on every card returns {"_cancelled": True} which the orchestrator
treats as a request to drop the current plan.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

# Streamlit's date_input defaults to a ±10-year window. Override for DOB inputs.
DOB_MIN = date(1900, 1, 1)
DOB_MAX = date.today()

from ui.card_models import (
    AddressFormCard,
    BalanceViewCard,
    BeneficiaryFormCard,
    Card,
    ConfirmationCard,
    ContributionFormCard,
    IdentityVerificationCard,
    NotImplementedCard,
    OtpCard,
    PhoneFormCard,
    SuccessCard,
    TransactionHistoryCard,
    US_STATES,
)


def _card_header(card: Card) -> None:
    st.markdown(f"### {card.title}")
    if card.subtitle:
        st.caption(card.subtitle)
    if card.helper_text:
        st.info(card.helper_text)
    if card.error:
        st.error(card.error)


def render_card(card: Card, key: str) -> dict[str, Any] | None:
    """Dispatch to the right per-card renderer."""
    dispatch = {
        "identity_verification": _render_identity,
        "otp": _render_otp,
        "address_form": _render_address,
        "phone_form": _render_phone,
        "beneficiary_form": _render_beneficiary,
        "contribution_form": _render_contribution,
        "balance_view": _render_balance,
        "transaction_history": _render_transaction_history,
        "confirmation": _render_confirmation,
        "success": _render_success,
        "not_implemented": _render_not_implemented,
    }
    return dispatch[card.card_type](card, key)


def _render_identity(card: IdentityVerificationCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            st.write(f"Verifying identity for **{card.customer_name}**.")
            with st.form(key, clear_on_submit=False):
                dob = st.date_input(
                    "Date of birth",
                    value=None,
                    min_value=DOB_MIN,
                    max_value=DOB_MAX,
                    format="YYYY-MM-DD",
                )
                ssn = st.text_input("Last 4 of SSN", max_chars=4, type="password")
                col1, col2 = st.columns([1, 1])
                with col1:
                    submitted = st.form_submit_button(card.submit_label, type="primary")
                with col2:
                    cancelled = st.form_submit_button("Cancel")
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                if dob is None or len(ssn) != 4:
                    st.warning("DOB and last-4 of SSN are both required.")
                    return None
                return {"dob": dob.isoformat(), "ssn_last4": ssn}
    return None


def _render_otp(card: OtpCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            st.write(card.delivery_hint)
            st.caption("(Demo: any value works as long as the code is `123456`.)")
            with st.form(key, clear_on_submit=False):
                code = st.text_input("6-digit code", max_chars=6)
                col1, col2 = st.columns([1, 1])
                with col1:
                    submitted = st.form_submit_button(card.submit_label, type="primary")
                with col2:
                    cancelled = st.form_submit_button("Cancel")
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                if not code:
                    st.warning("Enter the 6-digit code.")
                    return None
                return {"otp": code}
    return None


def _render_address(card: AddressFormCard, key: str) -> dict[str, Any] | None:
    p = card.prefilled
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                line1 = st.text_input("Street address", value=p.get("address_line1", ""))
                line2 = st.text_input("Apt / unit (optional)", value=p.get("address_line2") or "")
                col_city, col_state, col_zip = st.columns([2, 1, 1])
                with col_city:
                    city = st.text_input("City", value=p.get("address_city", ""))
                with col_state:
                    default_state = p.get("address_state", "CA")
                    state_idx = US_STATES.index(default_state) if default_state in US_STATES else 0
                    state = st.selectbox("State", US_STATES, index=state_idx)
                with col_zip:
                    postal = st.text_input("ZIP", value=p.get("address_postal", ""), max_chars=10)
                col1, col2 = st.columns([1, 1])
                with col1:
                    submitted = st.form_submit_button(card.submit_label, type="primary")
                with col2:
                    cancelled = st.form_submit_button("Cancel")
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                missing = [n for n, v in [("street", line1), ("city", city), ("ZIP", postal)] if not v.strip()]
                if missing:
                    st.warning(f"Required: {', '.join(missing)}")
                    return None
                return {
                    "address_line1": line1.strip(),
                    "address_line2": line2.strip() or None,
                    "address_city": city.strip(),
                    "address_state": state,
                    "address_postal": postal.strip(),
                    "address_country": "US",
                }
    return None


def _render_phone(card: PhoneFormCard, key: str) -> dict[str, Any] | None:
    p = card.prefilled
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                phone = st.text_input("Phone number", value=p.get("phone", ""), placeholder="555-555-5555")
                col1, col2 = st.columns([1, 1])
                with col1:
                    submitted = st.form_submit_button(card.submit_label, type="primary")
                with col2:
                    cancelled = st.form_submit_button("Cancel")
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                digits = "".join(c for c in phone if c.isdigit())
                if len(digits) != 10:
                    st.warning("Enter a valid 10-digit US phone number.")
                    return None
                return {"phone": phone.strip()}
    return None


def _render_beneficiary(card: BeneficiaryFormCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                if not card.accounts:
                    st.warning("No accounts available.")
                    return None
                acct = st.selectbox(
                    "Account",
                    options=[a["id"] for a in card.accounts],
                    format_func=lambda aid: next(a["label"] for a in card.accounts if a["id"] == aid),
                )
                btype = st.selectbox("Beneficiary type", ["primary", "contingent"])
                name = st.text_input("Full legal name")
                relationship = st.selectbox(
                    "Relationship",
                    ["spouse", "child", "parent", "sibling", "trust", "other"],
                )
                dob = st.date_input(
                    "Date of birth",
                    value=None,
                    min_value=DOB_MIN,
                    max_value=DOB_MAX,
                    format="YYYY-MM-DD",
                )
                ssn4 = st.text_input("Last 4 of SSN", max_chars=4, type="password")
                pct = st.slider("Allocation %", 1, 100, 100)
                col1, col2 = st.columns([1, 1])
                with col1:
                    submitted = st.form_submit_button(card.submit_label, type="primary")
                with col2:
                    cancelled = st.form_submit_button("Cancel")
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                if not name.strip() or len(ssn4) != 4 or dob is None:
                    st.warning("Name, DOB, and last-4 of SSN are required.")
                    return None
                return {
                    "account_id": acct,
                    "type": btype,
                    "name": name.strip(),
                    "relationship": relationship,
                    "dob": dob.isoformat(),
                    "ssn_last4": ssn4,
                    "allocation_pct": float(pct),
                }
    return None


def _render_contribution(card: ContributionFormCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                if not card.accounts:
                    st.warning("No accounts available.")
                    return None
                acct = st.selectbox(
                    "Account",
                    options=[a["id"] for a in card.accounts],
                    format_func=lambda aid: next(a["label"] for a in card.accounts if a["id"] == aid),
                )
                current = next((a["current_pct"] for a in card.accounts if a["id"] == acct), 0.0)
                st.caption(f"Current contribution: **{current:.1f}%**")
                new_pct = st.slider("New contribution %", 0.0, 100.0, float(current), 0.5)
                col1, col2 = st.columns([1, 1])
                with col1:
                    submitted = st.form_submit_button(card.submit_label, type="primary")
                with col2:
                    cancelled = st.form_submit_button("Cancel")
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {"account_id": acct, "contribution_pct": float(new_pct)}
    return None


def _render_balance(card: BalanceViewCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            col1, col2 = st.columns(2)
            col1.metric("Total balance", f"${card.total_balance:,.2f}")
            col2.metric("Vested balance", f"${card.vested_balance:,.2f}")
            st.divider()
            for a in card.accounts:
                st.write(
                    f"**{a['plan_name']}** — {a['type']}  \n"
                    f"Balance ${a['balance']:,.2f} • Vested ${a['vested_balance']:,.2f}"
                )
            if st.button(card.submit_label, key=f"{key}-done", type="primary"):
                return {"_acknowledged": True}
    return None


def _render_transaction_history(card: TransactionHistoryCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            if not card.transactions:
                st.write("No recent transactions.")
            else:
                rows = [
                    {
                        "Date": t["txn_date"],
                        "Type": t["txn_type"],
                        "Amount": f"${t['amount']:,.2f}",
                        "Fund": t.get("fund_ticker") or "-",
                        "Description": t.get("description") or "",
                    }
                    for t in card.transactions
                ]
                st.dataframe(rows, use_container_width=True, hide_index=True)
            if st.button(card.submit_label, key=f"{key}-done", type="primary"):
                return {"_acknowledged": True}
    return None


def _render_confirmation(card: ConfirmationCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            for line in card.summary_lines:
                st.write(line)
            if card.diff:
                rows = [{"Field": d["field"], "Before": d["before"], "After": d["after"]} for d in card.diff]
                st.dataframe(rows, use_container_width=True, hide_index=True)
            with st.form(key, clear_on_submit=False):
                col1, col2 = st.columns([1, 1])
                with col1:
                    submitted = st.form_submit_button(card.submit_label, type="primary")
                with col2:
                    cancelled = st.form_submit_button("Cancel")
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {"_confirmed": True}
    return None


def _render_success(card: SuccessCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            st.success(card.title)
            if card.subtitle:
                st.write(card.subtitle)
            for line in card.summary_lines:
                st.write(line)
            if card.request_id:
                st.caption(f"Confirmation #{card.request_id}")
            if st.button(card.submit_label, key=f"{key}-done", type="primary"):
                return {"_acknowledged": True}
    return None


def _render_not_implemented(card: NotImplementedCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            st.warning(
                f"**{card.intent}** is registered in the intent catalog but the form for it "
                "isn't built in this prototype. In a real product this is where the agent would "
                "render the matching workflow."
            )
            if card.next_steps:
                st.write("**Typical steps for this transaction:**")
                for step in card.next_steps:
                    st.write(f"- {step}")
            if st.button(card.submit_label, key=f"{key}-done"):
                return {"_acknowledged": True}
    return None
