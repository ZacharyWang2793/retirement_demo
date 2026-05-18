"""Streamlit renderers — one per card type.

Each render function returns:
- dict: the user submitted the form (data to resume the graph with)
- None: the user hasn't submitted yet (Streamlit will rerun on next interaction)

A "Cancel" button on every interactive card returns {"_cancelled": True}, which
the orchestrator treats as a request to drop the current plan.
"""
from __future__ import annotations

import html
from datetime import date
from typing import Any

import streamlit as st

from ui.card_models import (
    AddressFormCard,
    BalanceViewCard,
    BankAccountFormCard,
    BeneficiaryFormCard,
    BeneficiaryPickerCard,
    Card,
    ConfirmationCard,
    ContributionFormCard,
    DeliveryPrefsFormCard,
    DistributionMethodCard,
    DistributionRequestFormCard,
    DocumentLinkCard,
    DriftViewCard,
    EmailFormCard,
    HardshipReasonFormCard,
    IdentityVerificationCard,
    LoanQuoteCard,
    LoanRequestFormCard,
    LoanStatusCard,
    MfaDeviceListCard,
    MfaEnrollFormCard,
    MicroDepositCard,
    NameFormCard,
    NotImplementedCard,
    AllocationFormCard,
    OtpCard,
    PasswordResetLinkCard,
    PhoneFormCard,
    QdroIntakeFormCard,
    RequestListCard,
    RmdAmountCard,
    RolloverInFormCard,
    RolloverOutFormCard,
    SpecialistRoutingCard,
    StatementPickerCard,
    SuccessCard,
    TaxWithholdingFormCard,
    TransactionHistoryCard,
    US_STATES,
)
from ui.styles import icon_html

# Streamlit's date_input defaults to a ±10-year window. Override for DOB inputs.
DOB_MIN = date(1900, 1, 1)
DOB_MAX = date.today()

# Per-card-type default Material Symbols name. Overridable via BaseCard.icon.
DEFAULT_ICONS: dict[str, str] = {
    "identity_verification": "verified_user",
    "otp": "password",
    "address_form": "home",
    "phone_form": "call",
    "email_form": "mail",
    "name_form": "badge",
    "beneficiary_form": "family_restroom",
    "beneficiary_picker": "family_restroom",
    "contribution_form": "savings",
    "allocation_form": "pie_chart",
    "drift_view": "balance",
    "balance_view": "account_balance",
    "transaction_history": "receipt_long",
    "confirmation": "check_circle",
    "success": "task_alt",
    "not_implemented": "engineering",
    "tax_withholding_form": "receipt",
    "bank_account_form": "account_balance_wallet",
    "microdeposit": "published_with_changes",
    "loan_quote": "request_quote",
    "loan_request_form": "request_quote",
    "loan_status": "request_quote",
    "rmd_amount": "payments",
    "distribution_method": "payments",
    "distribution_request_form": "payments",
    "mfa_device_list": "security",
    "mfa_enroll_form": "security",
    "delivery_prefs_form": "mail_lock",
    "password_reset_link": "lock_reset",
    "request_list": "list_alt",
    "document_link": "description",
    "statement_picker": "description",
    "hardship_form": "emergency",
    "rollover_out_form": "swap_horiz",
    "rollover_in_form": "swap_horiz",
    "qdro_form": "gavel",
    "specialist_routing": "support_agent",
}


def _resolve_icon(card: Card) -> str:
    return card.icon or DEFAULT_ICONS.get(card.card_type, "circle")


def _card_header(card: Card) -> None:
    """Branded card header: icon + title + subtitle. Error/helper render below."""
    icon = _resolve_icon(card)
    title = html.escape(card.title)
    subtitle_html = (
        f'<div class="rs-card-subtitle">{html.escape(card.subtitle)}</div>'
        if card.subtitle
        else ""
    )
    st.markdown(
        f"""
        <div class="rs-card-head">
          <span class="rs-card-icon">{icon_html(icon, size=22)}</span>
          <span class="rs-card-title-block">
            <span class="rs-card-title">{title}</span>
            {subtitle_html}
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if card.helper_text:
        st.info(card.helper_text)
    if card.error:
        st.error(card.error)


def _submit_cancel_row(submit_label: str) -> tuple[bool, bool]:
    """Return (submitted, cancelled). 2:1 column split (primary wider)."""
    col1, col2 = st.columns([2, 1])
    with col1:
        submitted = st.form_submit_button(submit_label, type="primary", use_container_width=True)
    with col2:
        cancelled = st.form_submit_button("Cancel", use_container_width=True)
    return submitted, cancelled


def render_card(card: Card, key: str) -> dict[str, Any] | None:
    """Dispatch to the right per-card renderer."""
    dispatch = {
        "identity_verification": _render_identity,
        "otp": _render_otp,
        "address_form": _render_address,
        "phone_form": _render_phone,
        "email_form": _render_email,
        "name_form": _render_name,
        "beneficiary_form": _render_beneficiary,
        "beneficiary_picker": _render_beneficiary_picker,
        "contribution_form": _render_contribution,
        "allocation_form": _render_allocation,
        "drift_view": _render_drift,
        "balance_view": _render_balance,
        "transaction_history": _render_transaction_history,
        "confirmation": _render_confirmation,
        "success": _render_success,
        "not_implemented": _render_not_implemented,
        "tax_withholding_form": _render_tax_withholding,
        "bank_account_form": _render_bank_account,
        "microdeposit": _render_microdeposit,
        "loan_quote": _render_loan_quote,
        "loan_request_form": _render_loan_request,
        "loan_status": _render_loan_status,
        "rmd_amount": _render_rmd_amount,
        "distribution_method": _render_distribution_method,
        "distribution_request_form": _render_distribution_request,
        "mfa_device_list": _render_mfa_device_list,
        "mfa_enroll_form": _render_mfa_enroll,
        "delivery_prefs_form": _render_delivery_prefs,
        "password_reset_link": _render_password_reset_link,
        "request_list": _render_request_list,
        "document_link": _render_document_link,
        "statement_picker": _render_statement_picker,
        "hardship_form": _render_hardship,
        "rollover_out_form": _render_rollover_out,
        "rollover_in_form": _render_rollover_in,
        "qdro_form": _render_qdro,
        "specialist_routing": _render_specialist_routing,
    }
    return dispatch[card.card_type](card, key)


# ---------- identity / otp ----------

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
                submitted, cancelled = _submit_cancel_row(card.submit_label)
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
            with st.form(key, clear_on_submit=False):
                code = st.text_input("6-digit code", max_chars=6)
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                if not code:
                    st.warning("Enter the 6-digit code.")
                    return None
                return {"otp": code}
    return None


# ---------- profile / contact ----------

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
                submitted, cancelled = _submit_cancel_row(card.submit_label)
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
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                digits = "".join(c for c in phone if c.isdigit())
                if len(digits) != 10:
                    st.warning("Enter a valid 10-digit US phone number.")
                    return None
                return {"phone": phone.strip()}
    return None


def _render_email(card: EmailFormCard, key: str) -> dict[str, Any] | None:
    p = card.prefilled
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                email = st.text_input("Email address", value=p.get("email", ""), placeholder="you@example.com")
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                if "@" not in email or "." not in email.split("@")[-1]:
                    st.warning("Enter a valid email address.")
                    return None
                return {"email": email.strip()}
    return None


def _render_name(card: NameFormCard, key: str) -> dict[str, Any] | None:
    p = card.prefilled
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                col1, col2 = st.columns(2)
                with col1:
                    first = st.text_input("First name", value=p.get("first_name", ""))
                with col2:
                    last = st.text_input("Last name", value=p.get("last_name", ""))
                doc_kind = st.selectbox(
                    "Supporting document",
                    ["marriage_certificate", "court_order", "passport_or_state_id", "other"],
                )
                # Mock file uploader — Streamlit's file_uploader doesn't work inside
                # st.form well across versions, so we just capture a filename.
                doc_name = st.text_input("Document file name (mocked upload)", placeholder="marriage-cert.pdf")
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                if not first.strip() or not last.strip():
                    st.warning("First and last name are required.")
                    return None
                if not doc_name.strip():
                    st.warning("Attach a supporting document.")
                    return None
                return {
                    "first_name": first.strip(),
                    "last_name": last.strip(),
                    "doc_kind": doc_kind,
                    "doc_file_name": doc_name.strip(),
                }
    return None


# ---------- beneficiaries ----------

def _render_beneficiary(card: BeneficiaryFormCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                if not card.accounts:
                    st.warning("No accounts available.")
                    return None
                # In edit mode we lock the account
                if card.mode == "edit" and card.target_beneficiary_id:
                    acct = card.accounts[0]["id"]
                    st.caption(f"Editing beneficiary on **{card.accounts[0]['label']}**")
                else:
                    acct = st.selectbox(
                        "Account",
                        options=[a["id"] for a in card.accounts],
                        format_func=lambda aid: next(a["label"] for a in card.accounts if a["id"] == aid),
                    )
                btype = st.selectbox(
                    "Beneficiary type",
                    ["primary", "contingent"],
                    index=0 if (card.prefilled.get("type") or "primary") == "primary" else 1,
                )
                name = st.text_input("Full legal name", value=card.prefilled.get("name", ""))
                relationship = st.selectbox(
                    "Relationship",
                    ["spouse", "child", "parent", "sibling", "trust", "other"],
                    index=["spouse", "child", "parent", "sibling", "trust", "other"].index(
                        card.prefilled.get("relationship", "spouse")
                    ) if card.prefilled.get("relationship") in {"spouse", "child", "parent", "sibling", "trust", "other"} else 0,
                )
                _dob_default = card.prefilled.get("dob")
                dob_val = date.fromisoformat(_dob_default) if _dob_default else None
                dob = st.date_input(
                    "Date of birth",
                    value=dob_val,
                    min_value=DOB_MIN,
                    max_value=DOB_MAX,
                    format="YYYY-MM-DD",
                )
                ssn4 = st.text_input(
                    "Last 4 of SSN",
                    max_chars=4,
                    type="password",
                    value=card.prefilled.get("ssn_last4", ""),
                )
                pct = st.slider(
                    "Allocation %",
                    1, 100,
                    int(card.prefilled.get("allocation_pct", 100)),
                )
                submitted, cancelled = _submit_cancel_row(card.submit_label)
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
                    "mode": card.mode,
                    "target_beneficiary_id": card.target_beneficiary_id,
                }
    return None


def _render_beneficiary_picker(card: BeneficiaryPickerCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            if not card.beneficiaries:
                st.info("You don't have any beneficiaries on file. Pick **Add new** to create one.")
            with st.form(key, clear_on_submit=False):
                options = [("__new__", "+ Add a new beneficiary")] + [
                    (b["id"], f"{b['name']} ({b['relationship']}) — {b['plan_name']} · {b['allocation_pct']:.0f}%")
                    for b in card.beneficiaries
                ]
                pick = st.selectbox(
                    "Beneficiary",
                    options=[o[0] for o in options],
                    format_func=lambda v: dict(options)[v],
                )
                action = "edit"
                if pick != "__new__":
                    action = st.radio("Action", ["edit", "remove"], horizontal=True, index=0)
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                if pick == "__new__":
                    return {"action": "add"}
                return {"action": action, "beneficiary_id": pick}
    return None


# ---------- contributions ----------

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
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {"account_id": acct, "contribution_pct": float(new_pct)}
    return None


# ---------- allocation / rebalance ----------

def _render_allocation(card: AllocationFormCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            st.caption(
                f"Account: **{card.account_label}**. Target allocations must sum to 100%."
            )
            with st.form(key, clear_on_submit=False):
                pcts: dict[str, float] = {}
                for f in card.funds:
                    pcts[f["ticker"]] = st.slider(
                        f"{f['name']} ({f['ticker']}) — current {f['current_pct']:.1f}%",
                        0.0, 100.0, float(f["target_pct"]), 0.5,
                        key=f"{key}-{f['ticker']}",
                    )
                total = sum(pcts.values())
                if abs(total - 100.0) < 0.05:
                    st.success(f"Total: {total:.1f}%")
                else:
                    st.warning(f"Total: {total:.1f}% — must equal 100%.")
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {
                    "account_id": card.account_id,
                    "allocations": [{"ticker": t, "target_pct": p} for t, p in pcts.items()],
                }
    return None


def _render_drift(card: DriftViewCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            st.caption(f"Account: **{card.account_label}**")
            rows_html = ""
            for f in card.funds:
                drift = f["drift_pct"]
                cls = "rs-drift-pos" if drift > 0.5 else ("rs-drift-neg" if drift < -0.5 else "rs-drift-flat")
                sign = "+" if drift > 0 else ""
                rows_html += (
                    '<div class="rs-txn-row">'
                    f'<div class="rs-txn-date">{html.escape(f["ticker"])}</div>'
                    f'<div class="rs-txn-body"><span class="rs-txn-type">{f["current_pct"]:.1f}% → {f["target_pct"]:.1f}%</span>'
                    f'<span class="rs-txn-desc">{html.escape(f["name"])}</span></div>'
                    f'<div class="rs-txn-amt {cls}">{sign}{drift:.1f}% &nbsp;${f["trade_amount"]:,.0f}</div>'
                    "</div>"
                )
            st.markdown(f'<div class="rs-txn-list">{rows_html}</div>', unsafe_allow_html=True)
            with st.form(key, clear_on_submit=False):
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {"_confirmed": True}
    return None


# ---------- read-only views ----------

def _render_balance(card: BalanceViewCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            # Hero block
            st.markdown(
                f"""
                <div class="rs-hero">
                  <div class="rs-hero-label">Total balance</div>
                  <div class="rs-hero-metric">${card.total_balance:,.2f}</div>
                  <div class="rs-hero-sub">${card.vested_balance:,.2f} vested · {len(card.accounts)} account{"s" if len(card.accounts) != 1 else ""}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            # Account grid
            cards_html = "".join(
                (
                    '<div class="rs-account-card">'
                    f'<div class="rs-account-plan">{html.escape(a["plan_name"])}</div>'
                    f'<div class="rs-account-tag">{html.escape(a["type"])}</div>'
                    f'<div class="rs-account-balance">${a["balance"]:,.2f}</div>'
                    f'<div class="rs-account-vested">${a["vested_balance"]:,.2f} vested</div>'
                    "</div>"
                )
                for a in card.accounts
            )
            st.markdown(f'<div class="rs-account-grid">{cards_html}</div>', unsafe_allow_html=True)
            st.write("")
            if st.button(card.submit_label, key=f"{key}-done", type="primary"):
                return {"_acknowledged": True}
    return None


def _render_transaction_history(card: TransactionHistoryCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            if not card.transactions:
                st.info("No recent transactions on file.")
            else:
                # Filter chips via session state
                filter_key = f"{key}-filter"
                if filter_key not in st.session_state:
                    st.session_state[filter_key] = "all"
                filters = ["all", "contribution", "distribution", "dividend", "fee"]
                st.markdown('<div class="rs-txn-filter-row">', unsafe_allow_html=True)
                cols = st.columns(len(filters))
                for i, f in enumerate(filters):
                    with cols[i]:
                        if st.button(
                            f.capitalize() if f != "all" else "All",
                            key=f"{key}-flt-{f}",
                            use_container_width=True,
                        ):
                            st.session_state[filter_key] = f
                st.markdown('</div>', unsafe_allow_html=True)
                active = st.session_state[filter_key]
                visible = [
                    t for t in card.transactions
                    if active == "all" or t["txn_type"] == active
                ]
                if not visible:
                    st.caption(f"No '{active}' transactions in the last {len(card.transactions)} entries.")
                rows_html = ""
                for t in visible:
                    amt = float(t["amount"])
                    sign = "+" if amt > 0 else ""
                    cls = "rs-txn-amt-pos" if amt > 0 else ("rs-txn-amt-neg" if amt < 0 else "rs-txn-amt-neu")
                    desc = t.get("description") or ""
                    rows_html += (
                        '<div class="rs-txn-row">'
                        f'<div class="rs-txn-date">{html.escape(t["txn_date"])}</div>'
                        f'<div class="rs-txn-body"><span class="rs-txn-type">{html.escape(t["txn_type"].replace("_", " "))}</span>'
                        f'<span class="rs-txn-desc">{html.escape(desc)}</span></div>'
                        f'<div class="rs-txn-amt {cls}">{sign}${abs(amt):,.2f}</div>'
                        "</div>"
                    )
                st.markdown(f'<div class="rs-txn-list">{rows_html}</div>', unsafe_allow_html=True)
            if st.button(card.submit_label, key=f"{key}-done", type="primary"):
                return {"_acknowledged": True}
    return None


def _render_request_list(card: RequestListCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            if not card.requests:
                st.info("You don't have any recent requests on file.")
                if st.button(card.submit_label, key=f"{key}-done", type="primary"):
                    return {"_acknowledged": True}
                return None
            # Render rows
            rows_html = ""
            for r in card.requests:
                status_cls = f"rs-status-{r['status']}"
                rows_html += (
                    '<div class="rs-list-row">'
                    f'<div><div class="rs-list-title">{html.escape(r["type"].replace("_", " ").title())}</div>'
                    f'<div class="rs-list-meta">#{html.escape(r["id"])} · {html.escape(r["created_at"][:10])}</div></div>'
                    f'<span class="rs-status-pill {status_cls}">{html.escape(r["status"])}</span>'
                    "</div>"
                )
            st.markdown(rows_html, unsafe_allow_html=True)

            if card.selectable:
                pending = [r for r in card.requests if r["status"] == "pending"]
                if not pending:
                    st.caption("No pending requests are eligible for cancellation.")
                    if st.button("Done", key=f"{key}-done", type="primary"):
                        return {"_acknowledged": True}
                    return None
                with st.form(key, clear_on_submit=False):
                    pick = st.selectbox(
                        "Select a pending request to cancel",
                        options=[r["id"] for r in pending],
                        format_func=lambda rid: next(
                            f"{r['type'].replace('_', ' ').title()} · {r['created_at'][:10]} · #{r['id']}"
                            for r in pending if r["id"] == rid
                        ),
                    )
                    submitted, cancelled = _submit_cancel_row(card.submit_label)
                if cancelled:
                    return {"_cancelled": True}
                if submitted:
                    return {"request_id": pick}
            else:
                if st.button(card.submit_label, key=f"{key}-done", type="primary"):
                    return {"_acknowledged": True}
    return None


def _render_document_link(card: DocumentLinkCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            st.success(f"Your {card.kind.replace('_', ' ')} for {card.period} is ready.")
            st.markdown(
                f"**File:** `{html.escape(card.file_path)}`  \n"
                f"**Generated:** {html.escape(card.generated_at)}"
            )
            st.caption("In production, this card would render a signed download link.")
            if st.button(card.submit_label, key=f"{key}-done", type="primary"):
                return {"_acknowledged": True}
    return None


def _render_statement_picker(card: StatementPickerCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                if not card.accounts:
                    st.warning("No accounts on file.")
                    return None
                acct = st.selectbox(
                    "Account",
                    options=[a["id"] for a in card.accounts],
                    format_func=lambda aid: next(a["label"] for a in card.accounts if a["id"] == aid),
                )
                kind = st.selectbox(
                    "Document type",
                    options=card.kinds,
                    format_func=lambda k: k.replace("_", " ").title(),
                )
                period = st.selectbox("Period", options=card.periods)
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {"account_id": acct, "kind": kind, "period": period}
    return None


# ---------- tax / banking ----------

def _render_tax_withholding(card: TaxWithholdingFormCard, key: str) -> dict[str, Any] | None:
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
                p = card.prefilled
                tax_year = st.number_input(
                    "Tax year",
                    min_value=2024,
                    max_value=date.today().year + 1,
                    value=p.get("tax_year") or date.today().year,
                    step=1,
                )
                federal = st.slider(
                    "Federal withholding %",
                    0.0, 50.0,
                    float(p.get("federal_pct", 10.0)),
                    0.5,
                )
                state_code = st.selectbox(
                    "State",
                    US_STATES,
                    index=US_STATES.index(p.get("state_code", "CA")) if p.get("state_code") in US_STATES else 0,
                )
                state_pct = st.slider(
                    "State withholding %",
                    0.0, 20.0,
                    float(p.get("state_pct", 0.0)),
                    0.5,
                )
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {
                    "account_id": acct,
                    "tax_year": int(tax_year),
                    "federal_pct": float(federal),
                    "state_code": state_code,
                    "state_pct": float(state_pct),
                }
    return None


def _render_bank_account(card: BankAccountFormCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                nickname = st.text_input("Nickname", placeholder="Chase Checking")
                routing = st.text_input("Routing number", max_chars=9, type="password")
                acct_num = st.text_input("Account number", max_chars=17, type="password")
                acct_type = st.selectbox("Account type", ["checking", "savings"])
                set_default = st.checkbox("Set as default for distributions", value=True)
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                routing_digits = "".join(c for c in routing if c.isdigit())
                acct_digits = "".join(c for c in acct_num if c.isdigit())
                if len(routing_digits) != 9:
                    st.warning("Routing number must be 9 digits.")
                    return None
                if not (4 <= len(acct_digits) <= 17):
                    st.warning("Account number must be 4–17 digits.")
                    return None
                if not nickname.strip():
                    st.warning("Nickname is required.")
                    return None
                return {
                    "nickname": nickname.strip(),
                    "routing_last4": routing_digits[-4:],
                    "account_last4": acct_digits[-4:],
                    "account_type": acct_type,
                    "set_default": bool(set_default),
                }
    return None


def _render_microdeposit(card: MicroDepositCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            st.info(
                f"We sent two small deposits to **{card.bank_nickname}** ending in {card.account_last4}. "
                "Enter both amounts to verify ownership."
            )
            with st.form(key, clear_on_submit=False):
                col1, col2 = st.columns(2)
                with col1:
                    a1 = st.number_input("Deposit 1 ($)", min_value=0.01, max_value=0.99, step=0.01, format="%.2f")
                with col2:
                    a2 = st.number_input("Deposit 2 ($)", min_value=0.01, max_value=0.99, step=0.01, format="%.2f")
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {"deposit_1": float(a1), "deposit_2": float(a2)}
    return None


# ---------- distributions / loans ----------

def _render_rmd_amount(card: RmdAmountCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            st.markdown(
                f"""
                <div class="rs-hero">
                  <div class="rs-hero-label">Required minimum distribution</div>
                  <div class="rs-hero-metric">${card.required_amount:,.2f}</div>
                  <div class="rs-hero-sub">Must be taken by {html.escape(card.deadline)} · for tax year {card.tax_year}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.form(key, clear_on_submit=False):
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {"_acknowledged": True}
    return None


def _render_distribution_method(card: DistributionMethodCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                if not card.bank_accounts:
                    st.warning("No bank accounts on file — add one first.")
                    return None
                method = st.radio(
                    "How would you like to receive the funds?",
                    ["bank_transfer", "mailed_check"],
                    horizontal=True,
                    format_func=lambda v: "Bank transfer" if v == "bank_transfer" else "Mailed check",
                )
                bank_id = None
                if method == "bank_transfer":
                    bank_id = st.selectbox(
                        "Bank account",
                        options=[b["id"] for b in card.bank_accounts],
                        format_func=lambda bid: next(
                            f"{b['nickname']} · …{b['account_last4']}" for b in card.bank_accounts if b["id"] == bid
                        ),
                    )
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {"method": method, "bank_account_id": bank_id}
    return None


def _render_distribution_request(card: DistributionRequestFormCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                acct = st.selectbox(
                    "Account",
                    options=[a["id"] for a in card.accounts],
                    format_func=lambda aid: next(a["label"] for a in card.accounts if a["id"] == aid),
                )
                amount = st.number_input("Amount ($)", min_value=100.0, step=100.0, value=1000.0, format="%.2f")
                method = st.radio(
                    "Method",
                    ["bank_transfer", "mailed_check"],
                    horizontal=True,
                    format_func=lambda v: "Bank transfer" if v == "bank_transfer" else "Mailed check",
                )
                fed_pct = st.slider("Federal withholding %", 0.0, 50.0, 10.0, 0.5)
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {
                    "account_id": acct,
                    "amount": float(amount),
                    "method": method,
                    "federal_pct": float(fed_pct),
                }
    return None


def _render_loan_quote(card: LoanQuoteCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            st.markdown(
                f"""
                <div class="rs-hero">
                  <div class="rs-hero-label">Maximum loan</div>
                  <div class="rs-hero-metric">${card.max_loan_amount:,.2f}</div>
                  <div class="rs-hero-sub">Based on ${card.vested_balance:,.2f} vested · {card.suggested_rate_pct:.2f}% rate</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.form(key, clear_on_submit=False):
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {"_acknowledged": True}
    return None


def _render_loan_request(card: LoanRequestFormCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                acct = st.selectbox(
                    "Account",
                    options=[a["id"] for a in card.accounts],
                    format_func=lambda aid: next(a["label"] for a in card.accounts if a["id"] == aid),
                )
                amount = st.number_input(
                    "Loan amount ($)",
                    min_value=1000.0,
                    max_value=float(card.max_amount),
                    step=500.0,
                    value=min(10000.0, float(card.max_amount)),
                    format="%.2f",
                )
                term = st.selectbox("Term", [12, 24, 36, 48, 60], index=4)
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {
                    "account_id": acct,
                    "amount": float(amount),
                    "term_months": int(term),
                }
    return None


def _render_loan_status(card: LoanStatusCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            if not card.loans:
                st.info("You don't have any active loans.")
            else:
                for loan in card.loans:
                    st.markdown(
                        f"""
                        <div class="rs-account-card">
                          <div class="rs-account-plan">{html.escape(loan["plan_name"])}</div>
                          <div class="rs-account-tag">{html.escape(loan["status"])}</div>
                          <div class="rs-account-balance">${loan["outstanding"]:,.2f} outstanding</div>
                          <div class="rs-account-vested">
                            Principal ${loan["principal"]:,.2f} · {loan["interest_rate"]:.2f}% · {loan["term_months"]} mo
                            <br/>Next payment due {html.escape(loan["next_payment_due"] or "—")}
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            if st.button(card.submit_label, key=f"{key}-done", type="primary"):
                return {"_acknowledged": True}
    return None


# ---------- security / preferences ----------

def _render_mfa_device_list(card: MfaDeviceListCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            if not card.devices:
                st.info("No MFA devices enrolled yet.")
            else:
                rows_html = ""
                for d in card.devices:
                    rows_html += (
                        '<div class="rs-list-row">'
                        f'<div><div class="rs-list-title">{html.escape(d["label"])}</div>'
                        f'<div class="rs-list-meta">{html.escape(d["kind"].upper())}'
                        f' · enrolled {html.escape(d["enrolled_at"][:10])}'
                        f'{" · last used " + html.escape(d["last_used_at"][:10]) if d.get("last_used_at") else ""}</div></div>'
                        f'<span class="rs-status-pill rs-status-completed">active</span>'
                        "</div>"
                    )
                st.markdown(rows_html, unsafe_allow_html=True)
            with st.form(key, clear_on_submit=False):
                action = st.radio(
                    "What would you like to do?",
                    ["enroll", "remove"] if card.devices else ["enroll"],
                    horizontal=True,
                    format_func=lambda v: "Enroll a new device" if v == "enroll" else "Remove a device",
                )
                remove_id = None
                if action == "remove" and card.devices:
                    remove_id = st.selectbox(
                        "Device to remove",
                        options=[d["id"] for d in card.devices],
                        format_func=lambda did: next(d["label"] for d in card.devices if d["id"] == did),
                    )
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {"action": action, "device_id": remove_id}
    return None


def _render_mfa_enroll(card: MfaEnrollFormCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                kind = st.selectbox(
                    "Device type",
                    ["sms", "totp", "hardware"],
                    format_func=lambda k: {"sms": "SMS code", "totp": "Authenticator app", "hardware": "Hardware key"}[k],
                )
                label = st.text_input("Device label", placeholder="iPhone 15 / Authy / YubiKey-2")
                contact = ""
                if kind == "sms":
                    contact = st.text_input("Phone number for SMS", placeholder="555-555-5555")
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                if not label.strip():
                    st.warning("Device label is required.")
                    return None
                if kind == "sms":
                    digits = "".join(c for c in contact if c.isdigit())
                    if len(digits) != 10:
                        st.warning("Enter a valid 10-digit phone number.")
                        return None
                return {"kind": kind, "label": label.strip(), "contact": contact.strip() or None}
    return None


def _render_delivery_prefs(card: DeliveryPrefsFormCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            p = card.prefilled
            with st.form(key, clear_on_submit=False):
                paperless_statements = st.checkbox(
                    "Paperless statements (recommended)",
                    value=bool(p.get("paperless_statements", True)),
                )
                paperless_tax = st.checkbox(
                    "Paperless tax forms",
                    value=bool(p.get("paperless_tax", False)),
                )
                marketing_email = st.checkbox(
                    "Marketing email about new features",
                    value=bool(p.get("marketing_email", True)),
                )
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {
                    "paperless_statements": bool(paperless_statements),
                    "paperless_tax": bool(paperless_tax),
                    "marketing_email": bool(marketing_email),
                }
    return None


def _render_password_reset_link(card: PasswordResetLinkCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            st.success(f"We've sent a reset link to **{card.email_masked}**.")
            st.caption(
                "The link expires in 30 minutes. If you don't receive it, check your spam folder or "
                "call us at 1-800-555-7483."
            )
            if st.button(card.submit_label, key=f"{key}-done", type="primary"):
                return {"_acknowledged": True}
    return None


# ---------- specialist-routed (Tier 3) ----------

def _render_hardship(card: HardshipReasonFormCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            st.caption(
                "Hardship distributions are subject to IRS rules and may incur a 10% early-withdrawal penalty. "
                "A specialist will review your request."
            )
            with st.form(key, clear_on_submit=False):
                acct = st.selectbox(
                    "Account",
                    options=[a["id"] for a in card.accounts],
                    format_func=lambda aid: next(a["label"] for a in card.accounts if a["id"] == aid),
                )
                reason = st.selectbox(
                    "Hardship reason",
                    ["medical_expense", "tuition", "eviction_or_foreclosure", "funeral", "disaster_repair", "other"],
                    format_func=lambda r: r.replace("_", " ").title(),
                )
                amount = st.number_input("Amount requested ($)", min_value=500.0, step=500.0, value=5000.0, format="%.2f")
                doc_name = st.text_input(
                    "Supporting document file name (mocked upload)",
                    placeholder="medical-bill-2026-05.pdf",
                )
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                if not doc_name.strip():
                    st.warning("A supporting document is required for hardship withdrawals.")
                    return None
                return {
                    "account_id": acct,
                    "reason": reason,
                    "amount": float(amount),
                    "doc_file_name": doc_name.strip(),
                }
    return None


def _render_rollover_out(card: RolloverOutFormCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                from_acct = st.selectbox(
                    "From account",
                    options=[a["id"] for a in card.accounts],
                    format_func=lambda aid: next(a["label"] for a in card.accounts if a["id"] == aid),
                )
                dest_plan = st.text_input("Destination plan name", placeholder="Fidelity Brokerage IRA")
                dest_last4 = st.text_input("Destination account last 4", max_chars=4, type="password")
                amount = st.number_input("Amount ($)", min_value=500.0, step=500.0, value=10000.0, format="%.2f")
                method = st.radio(
                    "Rollover method",
                    ["direct", "indirect"],
                    horizontal=True,
                    format_func=lambda v: "Direct (trustee-to-trustee)" if v == "direct" else "Indirect (60-day)",
                )
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                if not dest_plan.strip() or len(dest_last4) != 4:
                    st.warning("Destination plan name and account last-4 are required.")
                    return None
                return {
                    "from_account_id": from_acct,
                    "destination_plan_name": dest_plan.strip(),
                    "destination_account_last4": dest_last4,
                    "amount": float(amount),
                    "method": method,
                }
    return None


def _render_rollover_in(card: RolloverInFormCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            with st.form(key, clear_on_submit=False):
                target_acct = st.selectbox(
                    "Roll into",
                    options=[a["id"] for a in card.accounts],
                    format_func=lambda aid: next(a["label"] for a in card.accounts if a["id"] == aid),
                )
                source_plan = st.text_input("Source plan name", placeholder="Schwab Solo 401(k)")
                source_ein = st.text_input("Source plan EIN (optional)", placeholder="12-3456789")
                amount_est = st.number_input("Estimated amount ($)", min_value=0.0, step=500.0, value=20000.0, format="%.2f")
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                if not source_plan.strip():
                    st.warning("Source plan name is required.")
                    return None
                return {
                    "target_account_id": target_acct,
                    "source_plan_name": source_plan.strip(),
                    "source_ein": source_ein.strip() or None,
                    "amount_estimate": float(amount_est),
                }
    return None


def _render_qdro(card: QdroIntakeFormCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            st.caption(
                "QDRO requests are reviewed by our legal team. Plan to allow 4–6 weeks "
                "from intake to approval."
            )
            with st.form(key, clear_on_submit=False):
                case_number = st.text_input("Court case number", placeholder="2026-FAM-001234")
                court = st.text_input("Court / jurisdiction", placeholder="San Francisco County Superior Court")
                doc_name = st.text_input(
                    "QDRO order file name (mocked upload)",
                    placeholder="qdro-order-2026.pdf",
                )
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                if not case_number.strip() or not court.strip() or not doc_name.strip():
                    st.warning("Case number, court, and the QDRO document are all required.")
                    return None
                return {
                    "case_number": case_number.strip(),
                    "court": court.strip(),
                    "doc_file_name": doc_name.strip(),
                }
    return None


def _render_specialist_routing(card: SpecialistRoutingCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            st.success(
                f"Your request has been received and routed to our specialist team. "
                f"Expect a response within **{card.eta_business_days} business days**."
            )
            st.markdown(
                f"**Confirmation:** `{html.escape(card.request_id)}`  \n"
                f"**Questions?** Call us at **{html.escape(card.contact_phone)}** "
                "and reference this confirmation number."
            )
            if st.button(card.submit_label, key=f"{key}-done", type="primary"):
                return {"_acknowledged": True}
    return None


# ---------- terminal ----------

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
                submitted, cancelled = _submit_cancel_row(card.submit_label)
            if cancelled:
                return {"_cancelled": True}
            if submitted:
                return {"_confirmed": True}
    return None


def _render_success(card: SuccessCard, key: str) -> dict[str, Any] | None:
    with st.chat_message("assistant"):
        with st.container(border=True):
            _card_header(card)
            st.success(card.title)
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
                f"**{card.intent}** is not currently available through self-service. "
                "Please call us at 1-800-555-7483 or visit your nearest branch for assistance."
            )
            if card.next_steps:
                st.write("**Typical steps for this transaction:**")
                for step in card.next_steps:
                    st.write(f"- {step}")
            if st.button(card.submit_label, key=f"{key}-done"):
                return {"_acknowledged": True}
    return None
