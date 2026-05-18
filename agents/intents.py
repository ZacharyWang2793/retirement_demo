"""Intent enum + per-intent step plan registry.

A "step" is a dict:
  {
    "name":            short id,
    "kind":            verify | collect | confirm | persist | inform,
    "card_factory":    callable(state, repo) -> Card  (None if no card; e.g. internal persist step),
    "validator":       callable(submission, state, repo) -> str | None  (returns error message on fail),
    "collector":       callable(submission, state) -> dict (merged into state.collected_data),
    "persister":       callable(state, repo) -> dict   (returned dict is merged into state.collected_data),
    "requires_verified": bool,
  }

Every intent in INTENTS has a real plan registered. The previous `NotImplementedCard`
fallback is reserved for unknown intent ids slipping in from the LLM.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta
from typing import Any, Callable

from db.repository import Repository
from ui.card_models import (
    AddressFormCard,
    AllocationFormCard,
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


# ---------- intent enum ----------

INTENTS: list[str] = [
    # profile / contact
    "change_address", "change_phone", "change_email", "change_name",
    # beneficiaries
    "add_beneficiary", "update_beneficiary",
    # read-only / status
    "check_balance", "view_transactions", "download_statement",
    "check_request_status", "cancel_request",
    # investments / contributions
    "change_contribution", "change_allocation", "rebalance",
    # distributions / withdrawals
    "take_rmd", "hardship_withdrawal", "request_loan", "loan_status",
    "qualified_distribution", "rollover_out", "rollover_in", "qdro",
    # tax / banking / security
    "update_tax_withholding", "update_direct_deposit", "manage_mfa",
    "delivery_preferences", "reset_password",
]

INTENT_LABELS: dict[str, str] = {
    "change_address": "Change address",
    "change_phone": "Change phone number",
    "change_email": "Change email address",
    "change_name": "Change legal name",
    "add_beneficiary": "Add a beneficiary",
    "update_beneficiary": "Update or remove a beneficiary",
    "check_balance": "Check account balance",
    "view_transactions": "View recent transactions",
    "download_statement": "Download statement or 1099-R",
    "check_request_status": "Check status of a pending request",
    "cancel_request": "Cancel a pending request",
    "change_contribution": "Change contribution amount",
    "change_allocation": "Change investment allocation",
    "rebalance": "Rebalance portfolio",
    "take_rmd": "Take a required minimum distribution",
    "hardship_withdrawal": "Request a hardship withdrawal",
    "request_loan": "Request a loan from your account",
    "loan_status": "Check loan status / payoff",
    "qualified_distribution": "Take a qualified distribution",
    "rollover_out": "Roll over funds to another account",
    "rollover_in": "Roll over funds in from another plan",
    "qdro": "QDRO / divorce-related distribution",
    "update_tax_withholding": "Update tax withholding",
    "update_direct_deposit": "Update direct deposit / EFT",
    "manage_mfa": "Manage MFA / trusted devices",
    "delivery_preferences": "Update paperless / delivery preferences",
    "reset_password": "Reset password",
}


# ---------- regex prefilter ----------

INTENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(change|update|new)\b.*\b(address|street|home)\b", re.I), "change_address"),
    (re.compile(r"\bmoved\b|\b(my )?new (home|place)\b", re.I), "change_address"),
    (re.compile(r"\b(change|update|new)\b.*\b(phone|cell|mobile|number)\b", re.I), "change_phone"),
    (re.compile(r"\b(change|update)\b.*\bemail\b", re.I), "change_email"),
    (re.compile(r"\b(change|update)\b.*\b(legal )?name\b", re.I), "change_name"),
    (re.compile(r"\badd\b.*\bbeneficiary\b", re.I), "add_beneficiary"),
    (re.compile(r"\b(update|remove|edit)\b.*\bbeneficiar(y|ies)\b", re.I), "update_beneficiary"),
    (re.compile(r"\b(check|what'?s|see|show)\b.*\bbalance\b", re.I), "check_balance"),
    (re.compile(r"\bhow much\b.*\b(have|saved|in my)\b", re.I), "check_balance"),
    (re.compile(r"\b(my|account)\b.*\bbalance\b", re.I), "check_balance"),
    (re.compile(r"\b(transactions?|recent activity|history)\b", re.I), "view_transactions"),
    (re.compile(r"\b(download|view|get|see)\b.*\b(statement|1099|tax form)\b", re.I), "download_statement"),
    (re.compile(r"\b(statement|1099|tax form)\b", re.I), "download_statement"),
    # cancel BEFORE the broader request-status patterns so "cancel a request" wins
    (re.compile(r"\b(cancel|withdraw)\b.*\brequest\b", re.I), "cancel_request"),
    (re.compile(r"\b(status|update on|pending)\b.*\b(request|change|update)\b", re.I), "check_request_status"),
    # Require "my" before "requests?" so it doesn't shadow request_loan / cancel_request etc.
    (re.compile(r"\bmy (open |pending )?requests?\b", re.I), "check_request_status"),
    (re.compile(r"\b(change|update|increase|decrease)\b.*\bcontribution\b", re.I), "change_contribution"),
    (re.compile(r"\b(change|update)\b.*\ballocation\b", re.I), "change_allocation"),
    (re.compile(r"\brebalance\b", re.I), "rebalance"),
    (re.compile(r"\brmd\b|\brequired minimum distribution\b", re.I), "take_rmd"),
    (re.compile(r"\bhardship\b", re.I), "hardship_withdrawal"),
    (re.compile(r"\b(request|take out|borrow)\b.*\bloan\b", re.I), "request_loan"),
    (re.compile(r"\bloan\b.*\b(status|payoff|balance)\b", re.I), "loan_status"),
    (re.compile(r"\bqualified distribution\b", re.I), "qualified_distribution"),
    (re.compile(r"\b(roll ?over|move).*\b(out|to another)\b", re.I), "rollover_out"),
    (re.compile(r"\b(roll ?over|move).*\b(in|from)\b", re.I), "rollover_in"),
    (re.compile(r"\bqdro\b|\bdivorce\b", re.I), "qdro"),
    (re.compile(r"\b(tax|federal|state)\b.*\bwithhold", re.I), "update_tax_withholding"),
    (re.compile(r"\b(direct deposit|ach|eft|bank account)\b", re.I), "update_direct_deposit"),
    (re.compile(r"\b(mfa|two[- ]?factor|authenticator)\b", re.I), "manage_mfa"),
    (re.compile(r"\b(paperless|e-?delivery|delivery preference)\b", re.I), "delivery_preferences"),
    (re.compile(r"\b(reset|change|forgot)\b.*\bpassword\b", re.I), "reset_password"),
]


def regex_classify(text: str) -> str | None:
    for pat, intent in INTENT_PATTERNS:
        if pat.search(text):
            return intent
    return None


# ---------- common card factories ----------

def _identity_card(state: dict[str, Any], repo: Repository) -> Card:
    c = repo.get_customer(state["customer_id"])
    return IdentityVerificationCard(
        title="Verify your identity",
        subtitle="We need to confirm it's really you before changing account details.",
        customer_name=f"{c['first_name']} {c['last_name']}",
    )


def _otp_card(state: dict[str, Any], repo: Repository) -> Card:
    return OtpCard(
        title="Enter verification code",
        delivery_hint="We sent a 6-digit code to your phone on file.",
    )


def _account_labels(repo: Repository, customer_id: str, only_types: set[str] | None = None) -> list[dict[str, str]]:
    accounts = repo.get_accounts(customer_id)
    return [
        {"id": a["id"], "label": f"{a['plan_name']} ({a['account_type']})"}
        for a in accounts
        if only_types is None or a["account_type"] in only_types
    ]


# ---------- profile / contact ----------

def _address_form(state: dict[str, Any], repo: Repository) -> Card:
    c = repo.get_customer(state["customer_id"])
    return AddressFormCard(
        title="Update your home address",
        subtitle="Edit any field below.",
        prefilled={
            "address_line1": c["address_line1"],
            "address_line2": c["address_line2"] or "",
            "address_city": c["address_city"],
            "address_state": c["address_state"],
            "address_postal": c["address_postal"],
        },
    )


def _phone_form(state: dict[str, Any], repo: Repository) -> Card:
    c = repo.get_customer(state["customer_id"])
    return PhoneFormCard(title="Update your phone number", prefilled={"phone": c["phone"]})


def _email_form(state: dict[str, Any], repo: Repository) -> Card:
    c = repo.get_customer(state["customer_id"])
    return EmailFormCard(title="Update your email address", prefilled={"email": c["email"]})


def _name_form(state: dict[str, Any], repo: Repository) -> Card:
    c = repo.get_customer(state["customer_id"])
    return NameFormCard(
        title="Update your legal name",
        subtitle="A supporting document is required (marriage certificate, court order, or ID).",
        prefilled={"first_name": c["first_name"], "last_name": c["last_name"]},
    )


# ---------- beneficiaries ----------

def _beneficiary_form(state: dict[str, Any], repo: Repository) -> Card:
    cid = state["customer_id"]
    bdata = (state.get("collected_data") or {}).get("beneficiary_target")
    if bdata:
        # Edit mode: lock the account, prefill from the chosen beneficiary
        accounts = [a for a in repo.get_accounts(cid) if a["id"] == bdata["account_id"]]
        labels = [
            {"id": a["id"], "label": f"{a['plan_name']} ({a['account_type']})"}
            for a in accounts
        ]
        return BeneficiaryFormCard(
            title=f"Edit beneficiary — {bdata['name']}",
            subtitle="Update any field below.",
            accounts=labels,
            mode="edit",
            target_beneficiary_id=bdata["id"],
            prefilled={
                "type": bdata["type"], "name": bdata["name"], "relationship": bdata["relationship"],
                "dob": bdata["dob"], "ssn_last4": bdata["ssn_last4"],
                "allocation_pct": bdata["allocation_pct"],
            },
            submit_label="Save changes",
        )
    return BeneficiaryFormCard(
        title="Add a beneficiary",
        subtitle="Pick the account, then enter the beneficiary's information.",
        accounts=_account_labels(repo, cid),
        mode="add",
    )


def _beneficiary_picker(state: dict[str, Any], repo: Repository) -> Card:
    beneficiaries = repo.get_beneficiaries(state["customer_id"])
    return BeneficiaryPickerCard(
        title="Update a beneficiary",
        subtitle="Pick a beneficiary to edit or remove, or add a new one.",
        beneficiaries=[
            {
                "id": b["id"],
                "name": b["name"],
                "relationship": b["relationship"],
                "type": b["type"],
                "allocation_pct": b["allocation_pct"],
                "plan_name": b["plan_name"],
                "account_id": b["account_id"],
                "dob": b["dob"],
                "ssn_last4": b["ssn_last4"],
            }
            for b in beneficiaries
        ],
    )


# ---------- contributions / allocation ----------

def _contribution_form(state: dict[str, Any], repo: Repository) -> Card:
    accounts = repo.get_accounts(state["customer_id"])
    rows = []
    for a in accounts:
        if a["account_type"] not in ("401k", "roth_401k"):
            continue
        contrib = repo.get_contribution(a["id"])
        rows.append({
            "id": a["id"], "label": a["plan_name"],
            "current_pct": contrib["contribution_pct"] if contrib else 0.0,
        })
    return ContributionFormCard(
        title="Update contribution amount",
        subtitle="Sets your standing election. Effective on the next payroll cycle.",
        accounts=rows,
    )


def _pick_primary_account(repo: Repository, customer_id: str) -> dict[str, Any] | None:
    accounts = repo.get_accounts(customer_id)
    if not accounts:
        return None
    for a in accounts:
        if a["account_type"] in ("401k", "roth_401k"):
            return a
    return accounts[0]


def _allocation_form(state: dict[str, Any], repo: Repository) -> Card:
    acct = _pick_primary_account(repo, state["customer_id"])
    if not acct:
        return NotImplementedCard(
            title="Change investment allocation",
            subtitle="No accounts found.",
            intent=INTENT_LABELS["change_allocation"],
        )
    invs = repo.get_investments(acct["id"])
    total = sum(i["current_value"] for i in invs) or 1.0
    funds = [
        {
            "ticker": i["fund_ticker"],
            "name": i["fund_name"],
            "current_pct": (i["current_value"] / total) * 100.0,
            "target_pct": i["target_allocation_pct"],
        }
        for i in invs
    ]
    return AllocationFormCard(
        title="Change investment allocation",
        subtitle="Set the target % for each fund. Allocations must sum to 100%.",
        account_id=acct["id"],
        account_label=f"{acct['plan_name']} ({acct['account_type']})",
        funds=funds,
    )


def _drift_view(state: dict[str, Any], repo: Repository) -> Card:
    acct = _pick_primary_account(repo, state["customer_id"])
    invs = repo.get_investments(acct["id"]) if acct else []
    total = sum(i["current_value"] for i in invs) or 1.0
    funds = []
    plan: list[dict[str, Any]] = []
    for i in invs:
        cur_pct = (i["current_value"] / total) * 100.0
        target_pct = i["target_allocation_pct"]
        drift = cur_pct - target_pct
        trade_amount = abs(drift / 100.0) * total
        funds.append({
            "ticker": i["fund_ticker"], "name": i["fund_name"],
            "current_pct": cur_pct, "target_pct": target_pct,
            "drift_pct": -drift,  # show as "+5" means buy more
            "trade_amount": trade_amount,
        })
        plan.append({
            "ticker": i["fund_ticker"],
            "action": "buy" if drift < 0 else ("sell" if drift > 0 else "hold"),
            "amount": trade_amount,
        })
    return DriftViewCard(
        title="Rebalance portfolio",
        subtitle="Review the trades required to bring you back to target.",
        account_id=acct["id"] if acct else "",
        account_label=f"{acct['plan_name']} ({acct['account_type']})" if acct else "",
        funds=funds,
        helper_text=None,
    )


# ---------- read-only / status ----------

def _balance_view(state: dict[str, Any], repo: Repository) -> Card:
    summary = repo.get_balance_summary(state["customer_id"])
    return BalanceViewCard(
        title="Your retirement balance",
        total_balance=summary["total_balance"],
        vested_balance=summary["vested_balance"],
        accounts=summary["accounts"],
    )


def _transaction_history(state: dict[str, Any], repo: Repository) -> Card:
    txns = repo.get_transactions(state["customer_id"], limit=20)
    return TransactionHistoryCard(
        title="Recent transactions",
        subtitle="Last 20 entries across all accounts.",
        transactions=txns,
    )


def _request_list(state: dict[str, Any], repo: Repository) -> Card:
    rows = repo.list_requests(state["customer_id"], limit=15)
    return RequestListCard(
        title="Your recent requests",
        subtitle="Status, ID, and submission date for each request.",
        requests=rows,
    )


def _request_list_cancellable(state: dict[str, Any], repo: Repository) -> Card:
    rows = repo.list_requests(state["customer_id"], limit=20)
    return RequestListCard(
        title="Cancel a pending request",
        subtitle="Only requests with a pending status are eligible to be cancelled.",
        requests=rows,
        selectable=True,
        submit_label="Cancel request",
    )


def _statement_picker(state: dict[str, Any], repo: Repository) -> Card:
    accounts = _account_labels(repo, state["customer_id"])
    today = date.today()
    periods = []
    for offset in range(0, 4):
        q = ((today.month - 1) // 3) - offset
        y = today.year + (q // 4 if q >= 0 else (q - 3) // 4)
        q = q % 4
        periods.append(f"{y} Q{q + 1}")
    periods.append(f"{today.year - 1} Annual")
    return StatementPickerCard(
        title="Download a statement",
        subtitle="Pick the account, document type, and period.",
        accounts=accounts,
        periods=periods,
        kinds=["statement_quarterly", "statement_annual", "1099r", "1099q"],
    )


def _document_link(state: dict[str, Any], repo: Repository) -> Card:
    pick = state["collected_data"]["statement_pick"]
    rid = state["collected_data"].get("request_id", "")
    return DocumentLinkCard(
        title="Statement ready",
        subtitle="Your statement has been generated.",
        file_path=f"documents/{state['customer_id']}/{pick['kind']}/{pick['period'].replace(' ', '-')}.pdf",
        kind=pick["kind"],
        period=pick["period"],
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
    )


# ---------- tax / banking ----------

def _tax_withholding_form(state: dict[str, Any], repo: Repository) -> Card:
    accounts = _account_labels(repo, state["customer_id"])
    first = repo.get_accounts(state["customer_id"])
    p = {}
    if first:
        tw = repo.get_tax_withholding(first[0]["id"])
        if tw:
            p = {
                "federal_pct": tw["federal_pct"],
                "state_code": tw.get("state_code"),
                "state_pct": tw["state_pct"],
                "tax_year": tw["tax_year"],
            }
    return TaxWithholdingFormCard(
        title="Update tax withholding",
        subtitle="Federal and state withholding for distributions.",
        accounts=accounts,
        prefilled=p,
    )


def _bank_account_form(state: dict[str, Any], repo: Repository) -> Card:
    return BankAccountFormCard(
        title="Add a bank account",
        subtitle="We'll verify ownership with two small deposits before activating it.",
    )


def _microdeposit_card(state: dict[str, Any], repo: Repository) -> Card:
    bank = state["collected_data"]["bank_account"]
    return MicroDepositCard(
        title="Verify bank account",
        bank_account_id=bank["bank_account_id"],
        bank_nickname=bank["nickname"],
        account_last4=bank["account_last4"],
    )


# ---------- loans / distributions ----------

def _loan_quote(state: dict[str, Any], repo: Repository) -> Card:
    acct = _pick_primary_account(repo, state["customer_id"])
    vested = (acct["vested_balance"] if acct else 0.0)
    # IRS rule: lesser of $50k or 50% of vested
    max_loan = min(50000.0, vested * 0.5)
    return LoanQuoteCard(
        title="Loan quote",
        subtitle="Based on your current vested balance.",
        max_loan_amount=max_loan,
        vested_balance=vested,
        suggested_rate_pct=7.5,
    )


def _loan_request_form(state: dict[str, Any], repo: Repository) -> Card:
    acct = _pick_primary_account(repo, state["customer_id"])
    vested = (acct["vested_balance"] if acct else 0.0)
    max_loan = min(50000.0, vested * 0.5)
    return LoanRequestFormCard(
        title="Request a loan",
        subtitle=f"Maximum available: ${max_loan:,.0f}",
        accounts=_account_labels(repo, state["customer_id"], only_types={"401k", "roth_401k"}),
        max_amount=max_loan,
    )


def _loan_status(state: dict[str, Any], repo: Repository) -> Card:
    loans = repo.list_loans(state["customer_id"])
    return LoanStatusCard(
        title="Your loans",
        subtitle="Outstanding balance and next payment due.",
        loans=loans,
    )


def _rmd_amount(state: dict[str, Any], repo: Repository) -> Card:
    summary = repo.get_balance_summary(state["customer_id"])
    c = repo.get_customer(state["customer_id"])
    age = (date.today() - date.fromisoformat(c["dob"])).days // 365
    # IRS Uniform Lifetime Table — simplified divisor lookup
    divisor = max(27.4 - max(0, age - 72) * 0.6, 10.0)
    required = summary["total_balance"] / divisor
    deadline = f"{date.today().year}-12-31"
    return RmdAmountCard(
        title="Your required minimum distribution",
        subtitle="Calculated using the IRS Uniform Lifetime Table.",
        required_amount=required,
        tax_year=date.today().year,
        deadline=deadline,
    )


def _distribution_method(state: dict[str, Any], repo: Repository) -> Card:
    banks = repo.list_bank_accounts(state["customer_id"])
    return DistributionMethodCard(
        title="Choose distribution method",
        subtitle="How would you like to receive the funds?",
        bank_accounts=[
            {"id": b["id"], "nickname": b["nickname"], "account_last4": b["account_number_last4"]}
            for b in banks if b["verified_at"]
        ],
    )


def _distribution_request_form(state: dict[str, Any], repo: Repository) -> Card:
    return DistributionRequestFormCard(
        title="Request a distribution",
        subtitle="Funds will be sent via your selected method, less applicable withholding.",
        accounts=_account_labels(repo, state["customer_id"]),
    )


# ---------- security / preferences ----------

def _mfa_device_list(state: dict[str, Any], repo: Repository) -> Card:
    devices = repo.list_mfa_devices(state["customer_id"])
    return MfaDeviceListCard(
        title="Manage MFA devices",
        subtitle="Add, remove, or review the devices used to verify sign-ins.",
        devices=devices,
    )


def _mfa_enroll_form(state: dict[str, Any], repo: Repository) -> Card:
    return MfaEnrollFormCard(
        title="Enroll a new MFA device",
        subtitle="Pick the type, label it, and provide contact info if needed.",
    )


def _delivery_prefs_form(state: dict[str, Any], repo: Repository) -> Card:
    p = repo.get_delivery_prefs(state["customer_id"]) or {}
    return DeliveryPrefsFormCard(
        title="Delivery preferences",
        subtitle="Choose how you want to receive statements, tax forms, and marketing email.",
        prefilled={
            "paperless_statements": bool(p.get("paperless_statements", True)),
            "paperless_tax": bool(p.get("paperless_tax", False)),
            "marketing_email": bool(p.get("marketing_email", True)),
        },
    )


def _password_reset_link(state: dict[str, Any], repo: Repository) -> Card:
    masked = state["collected_data"].get("email_masked", "***")
    return PasswordResetLinkCard(
        title="Password reset link sent",
        email_masked=masked,
    )


# ---------- specialist-routed (Tier 3) ----------

def _hardship_form(state: dict[str, Any], repo: Repository) -> Card:
    return HardshipReasonFormCard(
        title="Hardship withdrawal",
        subtitle="Hardship distributions are subject to IRS rules and require supporting documentation.",
        accounts=_account_labels(repo, state["customer_id"], only_types={"401k", "roth_401k"}),
    )


def _rollover_out_form(state: dict[str, Any], repo: Repository) -> Card:
    return RolloverOutFormCard(
        title="Roll over to another plan",
        subtitle="Direct (trustee-to-trustee) rollovers avoid mandatory 20% withholding.",
        accounts=_account_labels(repo, state["customer_id"]),
    )


def _rollover_in_form(state: dict[str, Any], repo: Repository) -> Card:
    return RolloverInFormCard(
        title="Roll over funds in",
        subtitle="Initiate transfer from an outside retirement plan.",
        accounts=_account_labels(repo, state["customer_id"]),
    )


def _qdro_form(state: dict[str, Any], repo: Repository) -> Card:
    return QdroIntakeFormCard(
        title="QDRO intake",
        subtitle="Qualified Domestic Relations Order — divorce-related distribution.",
    )


# ---------- confirmations ----------

def _confirmation_address(state: dict[str, Any], repo: Repository) -> Card:
    before = repo.get_customer(state["customer_id"])
    after = state["collected_data"]["address"]
    keys = ["address_line1", "address_line2", "address_city", "address_state", "address_postal"]
    diff = []
    for k in keys:
        b, a = str(before.get(k) or ""), str(after.get(k) or "")
        if b != a:
            diff.append({"field": k.replace("address_", "").replace("_", " ").title(), "before": b, "after": a})
    return ConfirmationCard(
        title="Confirm address change",
        subtitle="Please review the changes below.",
        diff=diff,
        summary_lines=["After confirming, this becomes your address of record."],
    )


def _confirmation_phone(state: dict[str, Any], repo: Repository) -> Card:
    before = repo.get_customer(state["customer_id"])
    after = state["collected_data"]["phone"]
    return ConfirmationCard(
        title="Confirm phone number change",
        diff=[{"field": "Phone", "before": before["phone"], "after": after["phone"]}],
    )


def _confirmation_email(state: dict[str, Any], repo: Repository) -> Card:
    before = repo.get_customer(state["customer_id"])
    after = state["collected_data"]["email"]
    return ConfirmationCard(
        title="Confirm email change",
        diff=[{"field": "Email", "before": before["email"], "after": after["email"]}],
    )


def _confirmation_name(state: dict[str, Any], repo: Repository) -> Card:
    before = repo.get_customer(state["customer_id"])
    after = state["collected_data"]["name"]
    return ConfirmationCard(
        title="Confirm legal name change",
        subtitle="Tax forms re-issued in the new name will be sent for the current tax year.",
        diff=[
            {"field": "First name", "before": before["first_name"], "after": after["first_name"]},
            {"field": "Last name", "before": before["last_name"], "after": after["last_name"]},
        ],
        summary_lines=[f"Supporting doc: {after['doc_file_name']} ({after['doc_kind'].replace('_', ' ')})"],
    )


def _confirmation_beneficiary(state: dict[str, Any], repo: Repository) -> Card:
    b = state["collected_data"]["beneficiary"]
    mode = b.get("mode", "add")
    title = {
        "add": "Confirm new beneficiary",
        "edit": "Confirm beneficiary changes",
    }.get(mode, "Confirm beneficiary changes")
    return ConfirmationCard(
        title=title,
        summary_lines=[
            f"**{b['name']}** ({b['relationship']}) — {b['type']} beneficiary",
            f"Allocation: {b['allocation_pct']}%",
        ],
    )


def _confirmation_beneficiary_remove(state: dict[str, Any], repo: Repository) -> Card:
    bdata = state["collected_data"].get("beneficiary_target", {})
    return ConfirmationCard(
        title="Confirm beneficiary removal",
        summary_lines=[
            f"Remove **{bdata.get('name', '')}** ({bdata.get('relationship', '')})"
            f" from your beneficiaries?",
        ],
    )


def _confirmation_contribution(state: dict[str, Any], repo: Repository) -> Card:
    d = state["collected_data"]["contribution"]
    contrib = repo.get_contribution(d["account_id"])
    before = contrib["contribution_pct"] if contrib else 0.0
    accounts = repo.get_accounts(state["customer_id"])
    plan_name = next((a["plan_name"] for a in accounts if a["id"] == d["account_id"]), d["account_id"])
    return ConfirmationCard(
        title="Confirm contribution change",
        summary_lines=[f"Account: **{plan_name}**"],
        diff=[{"field": "Contribution %", "before": f"{before:.1f}%", "after": f"{d['contribution_pct']:.1f}%"}],
    )


def _confirmation_allocation(state: dict[str, Any], repo: Repository) -> Card:
    d = state["collected_data"]["allocation"]
    diff = [
        {"field": a["ticker"], "before": "—", "after": f"{a['target_pct']:.1f}%"}
        for a in d["allocations"]
    ]
    return ConfirmationCard(
        title="Confirm allocation change",
        diff=diff,
        summary_lines=["Targets will apply to your next contribution cycle."],
    )


def _confirmation_tax_withholding(state: dict[str, Any], repo: Repository) -> Card:
    d = state["collected_data"]["tax_withholding"]
    return ConfirmationCard(
        title="Confirm tax withholding",
        summary_lines=[
            f"Tax year **{d['tax_year']}** · Federal **{d['federal_pct']:.1f}%** · "
            f"{d['state_code']} **{d['state_pct']:.1f}%**"
        ],
    )


def _confirmation_bank_default(state: dict[str, Any], repo: Repository) -> Card:
    bank = state["collected_data"]["bank_account"]
    return ConfirmationCard(
        title="Confirm direct deposit",
        summary_lines=[
            f"Verify deposits to **{bank['nickname']}** ending in {bank['account_last4']} "
            "and set as default for distributions?"
        ],
    )


def _confirmation_loan(state: dict[str, Any], repo: Repository) -> Card:
    d = state["collected_data"]["loan_request"]
    return ConfirmationCard(
        title="Confirm loan request",
        summary_lines=[
            f"Amount: **${d['amount']:,.2f}**",
            f"Term: **{d['term_months']} months**",
            "Rate: 7.5% (subject to plan rules)",
        ],
    )


def _confirmation_distribution(state: dict[str, Any], repo: Repository) -> Card:
    d = state["collected_data"]["distribution"]
    return ConfirmationCard(
        title="Confirm distribution",
        summary_lines=[
            f"Amount: **${d['amount']:,.2f}**",
            f"Method: **{d['method'].replace('_', ' ')}**",
            f"Federal withholding: **{d['federal_pct']:.1f}%**",
        ],
    )


def _confirmation_rmd(state: dict[str, Any], repo: Repository) -> Card:
    method = state["collected_data"]["rmd_method"]
    return ConfirmationCard(
        title="Confirm RMD distribution",
        summary_lines=[
            f"Method: **{method['method'].replace('_', ' ')}**",
        ],
    )


def _confirmation_mfa(state: dict[str, Any], repo: Repository) -> Card:
    d = state["collected_data"]["mfa_action"]
    if d.get("action") == "remove":
        target = next(
            (x for x in repo.list_mfa_devices(state["customer_id"]) if x["id"] == d.get("device_id")),
            None,
        )
        return ConfirmationCard(
            title="Confirm device removal",
            summary_lines=[f"Remove **{target['label']}** ({target['kind'].upper()})?" if target else "Remove device?"],
        )
    enroll = state["collected_data"].get("mfa_enroll", {})
    return ConfirmationCard(
        title="Confirm new MFA device",
        summary_lines=[
            f"Type: **{enroll.get('kind', '').upper()}**",
            f"Label: **{enroll.get('label', '')}**",
        ],
    )


def _confirmation_delivery_prefs(state: dict[str, Any], repo: Repository) -> Card:
    d = state["collected_data"]["delivery_prefs"]
    lines = [
        f"Paperless statements: **{'on' if d['paperless_statements'] else 'off'}**",
        f"Paperless tax forms: **{'on' if d['paperless_tax'] else 'off'}**",
        f"Marketing email: **{'on' if d['marketing_email'] else 'off'}**",
    ]
    return ConfirmationCard(title="Confirm preferences", summary_lines=lines)


def _confirmation_rollover_out(state: dict[str, Any], repo: Repository) -> Card:
    d = state["collected_data"]["rollover_out"]
    return ConfirmationCard(
        title="Confirm rollover request",
        summary_lines=[
            f"Amount: **${d['amount']:,.2f}** ({d['method']} rollover)",
            f"Destination: **{d['destination_plan_name']}** · …{d['destination_account_last4']}",
            "This request will be routed to our specialist team for review.",
        ],
    )


# ---------- success cards ----------

def _success_address(state: dict[str, Any], repo: Repository) -> Card:
    addr = state["collected_data"]["address"]
    rid = state["collected_data"].get("request_id")
    return SuccessCard(
        title="Address updated",
        subtitle="Your address of record has been updated.",
        summary_lines=[
            f"{addr['address_line1']}",
            f"{addr['address_city']}, {addr['address_state']} {addr['address_postal']}",
        ],
        request_id=rid,
    )


def _success_phone(state: dict[str, Any], repo: Repository) -> Card:
    p = state["collected_data"]["phone"]
    return SuccessCard(
        title="Phone updated",
        summary_lines=[f"New phone: {p['phone']}"],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_email(state: dict[str, Any], repo: Repository) -> Card:
    e = state["collected_data"]["email"]
    return SuccessCard(
        title="Email updated",
        summary_lines=[f"New email: {e['email']}"],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_name(state: dict[str, Any], repo: Repository) -> Card:
    n = state["collected_data"]["name"]
    return SuccessCard(
        title="Legal name updated",
        summary_lines=[
            f"New name: {n['first_name']} {n['last_name']}",
            f"Document on file: {n['doc_file_name']}",
        ],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_beneficiary(state: dict[str, Any], repo: Repository) -> Card:
    b = state["collected_data"]["beneficiary"]
    mode = b.get("mode", "add")
    title = {"add": "Beneficiary added", "edit": "Beneficiary updated"}.get(mode, "Beneficiary saved")
    return SuccessCard(
        title=title,
        summary_lines=[f"{b['name']} ({b['relationship']}) — {b['allocation_pct']}%"],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_beneficiary_remove(state: dict[str, Any], repo: Repository) -> Card:
    target = state["collected_data"].get("beneficiary_target", {})
    return SuccessCard(
        title="Beneficiary removed",
        summary_lines=[f"{target.get('name', '')} ({target.get('relationship', '')}) has been removed."],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_contribution(state: dict[str, Any], repo: Repository) -> Card:
    d = state["collected_data"]["contribution"]
    return SuccessCard(
        title="Contribution updated",
        summary_lines=[f"New contribution: {d['contribution_pct']:.1f}%"],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_allocation(state: dict[str, Any], repo: Repository) -> Card:
    return SuccessCard(
        title="Allocation updated",
        summary_lines=["Your target allocations have been saved."],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_rebalance(state: dict[str, Any], repo: Repository) -> Card:
    return SuccessCard(
        title="Rebalance submitted",
        summary_lines=["Trades will execute within the next two business days."],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_tax_withholding(state: dict[str, Any], repo: Repository) -> Card:
    return SuccessCard(
        title="Tax withholding updated",
        summary_lines=["Your new rates apply to all future distributions for the selected tax year."],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_bank(state: dict[str, Any], repo: Repository) -> Card:
    bank = state["collected_data"]["bank_account"]
    return SuccessCard(
        title="Bank account verified",
        summary_lines=[
            f"{bank['nickname']} (…{bank['account_last4']}) is now active.",
        ],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_loan(state: dict[str, Any], repo: Repository) -> Card:
    d = state["collected_data"]["loan_request"]
    return SuccessCard(
        title="Loan request submitted",
        summary_lines=[
            f"${d['amount']:,.2f} over {d['term_months']} months.",
            "Funds typically disburse within 3–5 business days.",
        ],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_rmd(state: dict[str, Any], repo: Repository) -> Card:
    return SuccessCard(
        title="RMD scheduled",
        summary_lines=["Your required minimum distribution has been scheduled."],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_distribution(state: dict[str, Any], repo: Repository) -> Card:
    d = state["collected_data"]["distribution"]
    return SuccessCard(
        title="Distribution requested",
        summary_lines=[f"${d['amount']:,.2f} via {d['method'].replace('_', ' ')}"],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_mfa(state: dict[str, Any], repo: Repository) -> Card:
    d = state["collected_data"]["mfa_action"]
    if d.get("action") == "remove":
        return SuccessCard(
            title="Device removed",
            summary_lines=["You'll no longer be prompted on that device."],
            request_id=state["collected_data"].get("request_id"),
        )
    e = state["collected_data"].get("mfa_enroll", {})
    return SuccessCard(
        title="Device enrolled",
        summary_lines=[f"**{e.get('label', '')}** ({e.get('kind', '').upper()}) is now active."],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_delivery_prefs(state: dict[str, Any], repo: Repository) -> Card:
    return SuccessCard(
        title="Preferences updated",
        summary_lines=["Your delivery preferences have been saved."],
        request_id=state["collected_data"].get("request_id"),
    )


def _success_cancel(state: dict[str, Any], repo: Repository) -> Card:
    rid = state["collected_data"].get("cancelled_request_id", "")
    return SuccessCard(
        title="Request cancelled",
        summary_lines=[f"Request {rid} has been cancelled."],
        request_id=state["collected_data"].get("request_id"),
    )


def _specialist_routing(state: dict[str, Any], repo: Repository) -> Card:
    rid = state["collected_data"].get("request_id", "")
    return SpecialistRoutingCard(
        title="Routed to a specialist",
        subtitle="Your intake has been submitted.",
        request_id=rid,
        eta_business_days=5,
    )


# ---------- validators ----------

def _ok_if_cancelled(submission: dict[str, Any]) -> bool:
    return bool(submission.get("_cancelled"))


def _validate_identity(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    ok = repo.verify_identity(state["customer_id"], submission["dob"], submission["ssn_last4"])
    return None if ok else "DOB and last-4 SSN don't match our records. Please try again."


def _validate_otp(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    return None if submission.get("otp") == "123456" else "Incorrect verification code."


def _validate_address(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    for f in ("address_line1", "address_city", "address_state", "address_postal"):
        if not submission.get(f):
            return f"Missing required field: {f}"
    if not (3 <= len(submission["address_postal"]) <= 10):
        return "ZIP code looks invalid."
    return None


def _validate_phone(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    digits = "".join(c for c in submission.get("phone", "") if c.isdigit())
    return None if len(digits) == 10 else "Phone must have 10 digits."


def _validate_email(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    e = submission.get("email", "")
    if "@" not in e or "." not in e.split("@")[-1]:
        return "Enter a valid email address."
    return None


def _validate_name(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    if not submission.get("first_name") or not submission.get("last_name"):
        return "First and last name are required."
    if not submission.get("doc_file_name"):
        return "A supporting document is required."
    return None


def _validate_beneficiary(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    for f in ("account_id", "type", "name", "relationship", "dob", "ssn_last4", "allocation_pct"):
        if submission.get(f) in (None, ""):
            return f"Missing required field: {f}"
    return None


def _validate_beneficiary_picker(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    action = submission.get("action")
    if action not in ("add", "edit", "remove"):
        return "Please choose an action."
    if action in ("edit", "remove") and not submission.get("beneficiary_id"):
        return "Pick a beneficiary first."
    return None


def _validate_contribution(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    pct = submission.get("contribution_pct")
    if pct is None or not 0 <= float(pct) <= 100:
        return "Contribution must be between 0 and 100%."
    return None


def _validate_allocation(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    allocs = submission.get("allocations") or []
    total = sum(float(a["target_pct"]) for a in allocs)
    if abs(total - 100.0) > 0.05:
        return f"Allocations must sum to 100% (got {total:.1f}%)."
    return None


def _validate_tax_withholding(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    if not 0 <= float(submission.get("federal_pct", -1)) <= 50:
        return "Federal withholding must be between 0 and 50%."
    if not 0 <= float(submission.get("state_pct", -1)) <= 20:
        return "State withholding must be between 0 and 20%."
    return None


def _validate_bank_account(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    if not submission.get("nickname"):
        return "Nickname is required."
    if len(submission.get("routing_last4", "")) != 4:
        return "Routing number must be 9 digits."
    if len(submission.get("account_last4", "")) < 4:
        return "Account number must be at least 4 digits."
    return None


def _validate_microdeposit(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    # Mocked correct amounts (always 0.12 and 0.34) — matches scripts/seed assumption
    if abs(float(submission.get("deposit_1", 0)) - 0.12) > 0.005:
        return "Deposit amounts don't match. Please re-enter."
    if abs(float(submission.get("deposit_2", 0)) - 0.34) > 0.005:
        return "Deposit amounts don't match. Please re-enter."
    return None


def _validate_loan_request(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    amt = float(submission.get("amount", 0))
    if amt < 1000:
        return "Loan amount must be at least $1,000."
    return None


def _validate_distribution_request(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    if float(submission.get("amount", 0)) < 100:
        return "Distribution amount must be at least $100."
    return None


def _validate_distribution_method(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    method = submission.get("method")
    if method == "bank_transfer" and not submission.get("bank_account_id"):
        return "Pick a bank account or switch to mailed check."
    return None


def _validate_mfa_action(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    action = submission.get("action")
    if action == "remove" and not submission.get("device_id"):
        return "Pick a device to remove."
    return None


def _validate_mfa_enroll(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    if not submission.get("label"):
        return "Device label is required."
    if submission.get("kind") == "sms":
        digits = "".join(c for c in (submission.get("contact") or "") if c.isdigit())
        if len(digits) != 10:
            return "SMS device needs a valid 10-digit phone number."
    return None


def _validate_confirmation(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    return None if submission.get("_confirmed") else "Confirmation required."


def _validate_acknowledge(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    return None if submission.get("_acknowledged") else "Please acknowledge to continue."


def _validate_request_pick(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    if not submission.get("request_id"):
        return "Pick a pending request to cancel."
    return None


def _validate_statement_pick(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    if not submission.get("account_id") or not submission.get("kind") or not submission.get("period"):
        return "Account, document type, and period are all required."
    return None


def _validate_hardship(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    if not submission.get("doc_file_name"):
        return "A supporting document is required for hardship requests."
    if float(submission.get("amount", 0)) < 500:
        return "Hardship amount must be at least $500."
    return None


def _validate_rollover_out(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    if not submission.get("destination_plan_name"):
        return "Destination plan name is required."
    if len(submission.get("destination_account_last4") or "") != 4:
        return "Destination account last-4 is required."
    return None


def _validate_rollover_in(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    if not submission.get("source_plan_name"):
        return "Source plan name is required."
    return None


def _validate_qdro(submission, state, repo):
    if _ok_if_cancelled(submission): return None
    if not submission.get("case_number") or not submission.get("court"):
        return "Case number and court are required."
    if not submission.get("doc_file_name"):
        return "QDRO order document is required."
    return None


# ---------- collectors ----------

def _collect_address(sub, st_): return {"address": sub}
def _collect_phone(sub, st_): return {"phone": sub}
def _collect_email(sub, st_): return {"email": sub}
def _collect_name(sub, st_): return {"name": sub}
def _collect_beneficiary(sub, st_): return {"beneficiary": sub}
def _collect_contribution(sub, st_): return {"contribution": sub}
def _collect_allocation(sub, st_): return {"allocation": sub}
def _collect_tax_withholding(sub, st_): return {"tax_withholding": sub}
def _collect_distribution_method(sub, st_): return {"rmd_method": sub}
def _collect_distribution(sub, st_): return {"distribution": sub}
def _collect_loan_request(sub, st_): return {"loan_request": sub}
def _collect_mfa_action(sub, st_): return {"mfa_action": sub}
def _collect_mfa_enroll(sub, st_): return {"mfa_enroll": sub}
def _collect_delivery_prefs(sub, st_): return {"delivery_prefs": sub}
def _collect_statement_pick(sub, st_): return {"statement_pick": sub}
def _collect_hardship(sub, st_): return {"hardship": sub}
def _collect_rollover_out(sub, st_): return {"rollover_out": sub}
def _collect_rollover_in(sub, st_): return {"rollover_in": sub}
def _collect_qdro(sub, st_): return {"qdro": sub}
def _collect_request_pick(sub, st_): return {"cancelled_request_id": sub.get("request_id")}


def _collect_beneficiary_pick(sub, state):
    """Look up the picked beneficiary from state and stash it so subsequent steps can use it."""
    action = sub.get("action")
    if action == "add":
        return {"beneficiary_action": "add"}
    bid = sub.get("beneficiary_id")
    # We need to find it in the picker card's data; that's been rendered already so we
    # don't have it here, but the persister can re-fetch. Just stash the action + id.
    return {"beneficiary_action": action, "beneficiary_target_id": bid}


def _collect_bank_account(sub, state):
    """Capture form fields. The persister will assign a bank_account_id."""
    return {"bank_account_pending": sub}


def _collect_microdeposit(sub, st_): return {"microdeposit": sub}


# ---------- persisters ----------

def _idempotency_key(state: dict[str, Any], step_name: str) -> str:
    raw = f"{state.get('thread_id', '')}|{state.get('intent', '')}|{step_name}|{state.get('current_step_idx', '')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _persist_address(state, repo):
    res = repo.update_address(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        new_address=state["collected_data"]["address"],
        idempotency_key=_idempotency_key(state, "persist_address"),
    )
    return {"request_id": res.request_id}


def _persist_phone(state, repo):
    res = repo.update_phone(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        new_phone=state["collected_data"]["phone"]["phone"],
        idempotency_key=_idempotency_key(state, "persist_phone"),
    )
    return {"request_id": res.request_id}


def _persist_email(state, repo):
    res = repo.update_email(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        new_email=state["collected_data"]["email"]["email"],
        idempotency_key=_idempotency_key(state, "persist_email"),
    )
    return {"request_id": res.request_id}


def _persist_name(state, repo):
    n = state["collected_data"]["name"]
    res = repo.update_name(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        first_name=n["first_name"], last_name=n["last_name"],
        doc_kind=n["doc_kind"], doc_file_name=n["doc_file_name"],
        idempotency_key=_idempotency_key(state, "persist_name"),
    )
    return {"request_id": res.request_id}


def _persist_beneficiary(state, repo):
    b = state["collected_data"]["beneficiary"]
    mode = b.get("mode", "add")
    cid = state["customer_id"]
    tid = state.get("thread_id")
    if mode == "edit" and b.get("target_beneficiary_id"):
        res = repo.update_beneficiary(
            customer_id=cid, thread_id=tid,
            beneficiary_id=b["target_beneficiary_id"],
            updates={
                "type": b["type"], "name": b["name"], "relationship": b["relationship"],
                "dob": b["dob"], "ssn_last4": b["ssn_last4"],
                "allocation_pct": float(b["allocation_pct"]),
            },
            idempotency_key=_idempotency_key(state, "persist_beneficiary"),
        )
    else:
        res = repo.add_beneficiary(
            customer_id=cid, thread_id=tid,
            account_id=b["account_id"],
            beneficiary={k: v for k, v in b.items() if k not in {"account_id", "mode", "target_beneficiary_id"}},
            idempotency_key=_idempotency_key(state, "persist_beneficiary"),
        )
    return {"request_id": res.request_id}


def _persist_beneficiary_remove(state, repo):
    target = state["collected_data"]["beneficiary_target"]
    res = repo.remove_beneficiary(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        beneficiary_id=target["id"],
        idempotency_key=_idempotency_key(state, "persist_beneficiary_remove"),
    )
    return {"request_id": res.request_id}


def _persist_contribution(state, repo):
    d = state["collected_data"]["contribution"]
    res = repo.update_contribution(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        account_id=d["account_id"], new_pct=d["contribution_pct"],
        idempotency_key=_idempotency_key(state, "persist_contribution"),
    )
    return {"request_id": res.request_id}


def _persist_allocation(state, repo):
    d = state["collected_data"]["allocation"]
    res = repo.update_allocation(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        account_id=d["account_id"], allocations=d["allocations"],
        idempotency_key=_idempotency_key(state, "persist_allocation"),
    )
    return {"request_id": res.request_id}


def _persist_rebalance(state, repo):
    acct = _pick_primary_account(repo, state["customer_id"])
    plan = [{"ticker": f["ticker"], "trade_amount": f["trade_amount"]} for f in (state.get("collected_data", {}).get("drift_funds") or [])]
    res = repo.request_rebalance(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        account_id=acct["id"] if acct else "", plan=plan,
        idempotency_key=_idempotency_key(state, "persist_rebalance"),
    )
    return {"request_id": res.request_id}


def _persist_tax_withholding(state, repo):
    d = state["collected_data"]["tax_withholding"]
    res = repo.update_tax_withholding(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        account_id=d["account_id"], tax_year=d["tax_year"],
        federal_pct=d["federal_pct"], state_code=d["state_code"], state_pct=d["state_pct"],
        idempotency_key=_idempotency_key(state, "persist_tax_withholding"),
    )
    return {"request_id": res.request_id}


def _persist_bank_add(state, repo):
    """Insert the bank row as unverified, return the bank_id for the microdeposit step."""
    sub = state["collected_data"]["bank_account_pending"]
    res, bank_id = repo.add_bank_account(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        nickname=sub["nickname"], routing_last4=sub["routing_last4"],
        account_last4=sub["account_last4"], account_type=sub["account_type"],
        set_default=sub["set_default"],
        idempotency_key=_idempotency_key(state, "persist_bank_add"),
    )
    return {
        "bank_account": {
            "bank_account_id": bank_id,
            "nickname": sub["nickname"],
            "account_last4": sub["account_last4"],
            "set_default": sub["set_default"],
        },
        "_add_request_id": res.request_id,
    }


def _persist_bank_verify(state, repo):
    bank = state["collected_data"]["bank_account"]
    res = repo.verify_bank_with_microdeposits(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        bank_account_id=bank["bank_account_id"],
        set_default=bank["set_default"],
        idempotency_key=_idempotency_key(state, "persist_bank_verify"),
    )
    return {"request_id": res.request_id}


def _persist_loan(state, repo):
    d = state["collected_data"]["loan_request"]
    res = repo.request_loan(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        account_id=d["account_id"], amount=d["amount"], term_months=d["term_months"],
        rate_pct=7.5,
        idempotency_key=_idempotency_key(state, "persist_loan"),
    )
    return {"request_id": res.request_id}


def _persist_rmd(state, repo):
    acct = _pick_primary_account(repo, state["customer_id"])
    method = state["collected_data"]["rmd_method"]
    summary = repo.get_balance_summary(state["customer_id"])
    c = repo.get_customer(state["customer_id"])
    age = (date.today() - date.fromisoformat(c["dob"])).days // 365
    divisor = max(27.4 - max(0, age - 72) * 0.6, 10.0)
    amount = summary["total_balance"] / divisor
    res = repo.create_distribution(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        account_id=acct["id"] if acct else "", kind="rmd", amount=amount,
        idempotency_key=_idempotency_key(state, "persist_rmd"),
        extra_payload={"method": method["method"], "bank_account_id": method.get("bank_account_id")},
    )
    return {"request_id": res.request_id}


def _persist_distribution(state, repo):
    d = state["collected_data"]["distribution"]
    res = repo.create_distribution(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        account_id=d["account_id"], kind="qualified", amount=d["amount"],
        idempotency_key=_idempotency_key(state, "persist_distribution"),
        extra_payload={"method": d["method"], "federal_pct": d["federal_pct"]},
    )
    return {"request_id": res.request_id}


def _persist_mfa(state, repo):
    d = state["collected_data"]["mfa_action"]
    if d.get("action") == "remove":
        res = repo.remove_mfa_device(
            customer_id=state["customer_id"], thread_id=state.get("thread_id"),
            device_id=d["device_id"],
            idempotency_key=_idempotency_key(state, "persist_mfa_remove"),
        )
    else:
        enroll = state["collected_data"].get("mfa_enroll", {})
        res = repo.enroll_mfa_device(
            customer_id=state["customer_id"], thread_id=state.get("thread_id"),
            kind=enroll["kind"], label=enroll["label"], contact=enroll.get("contact"),
            idempotency_key=_idempotency_key(state, "persist_mfa_enroll"),
        )
    return {"request_id": res.request_id}


def _persist_delivery_prefs(state, repo):
    d = state["collected_data"]["delivery_prefs"]
    res = repo.update_delivery_prefs(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        paperless_statements=d["paperless_statements"],
        paperless_tax=d["paperless_tax"],
        marketing_email=d["marketing_email"],
        idempotency_key=_idempotency_key(state, "persist_delivery_prefs"),
    )
    return {"request_id": res.request_id}


def _persist_password_reset(state, repo):
    res, masked = repo.request_password_reset(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        idempotency_key=_idempotency_key(state, "persist_password_reset"),
    )
    return {"request_id": res.request_id, "email_masked": masked}


def _persist_statement(state, repo):
    pick = state["collected_data"]["statement_pick"]
    res = repo.create_statement_request(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        account_id=pick["account_id"], kind=pick["kind"], period=pick["period"],
        idempotency_key=_idempotency_key(state, "persist_statement"),
    )
    return {"request_id": res.request_id}


def _persist_cancel(state, repo):
    rid = state["collected_data"]["cancelled_request_id"]
    res = repo.cancel_request(
        customer_id=state["customer_id"], thread_id=state.get("thread_id"),
        request_id=rid,
        idempotency_key=_idempotency_key(state, "persist_cancel"),
    )
    return {"request_id": res.request_id}


def _persist_specialist(request_type_key: str, payload_key: str):
    def _persister(state, repo):
        payload = state["collected_data"].get(payload_key) or {}
        res = repo.route_to_specialist(
            customer_id=state["customer_id"], thread_id=state.get("thread_id"),
            request_type=request_type_key, payload=payload,
            idempotency_key=_idempotency_key(state, f"persist_{request_type_key}"),
        )
        return {"request_id": res.request_id}
    return _persister


# ---------- beneficiary pick → stash target dict ----------

def _resolve_beneficiary_pick(state, repo):
    """After the picker, look up the chosen beneficiary's full record so subsequent steps
    can render diffs and the persister can find the row. Used by the update_beneficiary plan."""
    cd = state.get("collected_data") or {}
    action = cd.get("beneficiary_action")
    if action == "add":
        return {}
    bid = cd.get("beneficiary_target_id")
    if not bid:
        return {}
    for b in repo.get_beneficiaries(state["customer_id"]):
        if b["id"] == bid:
            return {"beneficiary_target": dict(b), "_pick_action": action}
    return {}


def _drift_snapshot(state, repo):
    """Run after the drift_view inform card so the persister has the same numbers."""
    acct = _pick_primary_account(repo, state["customer_id"])
    invs = repo.get_investments(acct["id"]) if acct else []
    total = sum(i["current_value"] for i in invs) or 1.0
    funds = [
        {
            "ticker": i["fund_ticker"],
            "current_pct": (i["current_value"] / total) * 100.0,
            "target_pct": i["target_allocation_pct"],
            "trade_amount": abs(((i["current_value"] / total) * 100.0 - i["target_allocation_pct"]) / 100.0) * total,
        }
        for i in invs
    ]
    return {"drift_funds": funds}


# ---------- step builders ----------

def _verify_step() -> dict[str, Any]:
    return {
        "name": "verify_identity", "kind": "verify",
        "card_factory": _identity_card, "validator": _validate_identity,
        "collector": None, "persister": None, "requires_verified": False,
    }


def _otp_step() -> dict[str, Any]:
    return {
        "name": "otp", "kind": "verify",
        "card_factory": _otp_card, "validator": _validate_otp,
        "collector": None, "persister": None, "requires_verified": False,
    }


def _confirm_step(name: str, factory: Callable, requires_verified: bool = True) -> dict[str, Any]:
    return {
        "name": name, "kind": "confirm",
        "card_factory": factory, "validator": _validate_confirmation,
        "collector": None, "persister": None, "requires_verified": requires_verified,
    }


def _persist_only(name: str, persister: Callable, requires_verified: bool = True) -> dict[str, Any]:
    return {
        "name": name, "kind": "persist",
        "card_factory": None, "validator": None,
        "collector": None, "persister": persister, "requires_verified": requires_verified,
    }


def _success_step(name: str, factory: Callable) -> dict[str, Any]:
    return {
        "name": name, "kind": "inform",
        "card_factory": factory, "validator": None,
        "collector": None, "persister": None, "requires_verified": False,
    }


# ---------- the registry ----------

INTENT_PLANS: dict[str, list[dict[str, Any]]] = {
    "change_address": [
        _verify_step(), _otp_step(),
        {"name": "collect_address", "kind": "collect", "card_factory": _address_form,
         "validator": _validate_address, "collector": _collect_address, "persister": None,
         "requires_verified": True},
        _confirm_step("confirm_address", _confirmation_address),
        _persist_only("persist_address", _persist_address),
        _success_step("success_address", _success_address),
    ],
    "change_phone": [
        _verify_step(), _otp_step(),
        {"name": "collect_phone", "kind": "collect", "card_factory": _phone_form,
         "validator": _validate_phone, "collector": _collect_phone, "persister": None,
         "requires_verified": True},
        _confirm_step("confirm_phone", _confirmation_phone),
        _persist_only("persist_phone", _persist_phone),
        _success_step("success_phone", _success_phone),
    ],
    "change_email": [
        _verify_step(), _otp_step(),
        {"name": "collect_email", "kind": "collect", "card_factory": _email_form,
         "validator": _validate_email, "collector": _collect_email, "persister": None,
         "requires_verified": True},
        _confirm_step("confirm_email", _confirmation_email),
        _persist_only("persist_email", _persist_email),
        _success_step("success_email", _success_email),
    ],
    "change_name": [
        _verify_step(), _otp_step(),
        {"name": "collect_name", "kind": "collect", "card_factory": _name_form,
         "validator": _validate_name, "collector": _collect_name, "persister": None,
         "requires_verified": True},
        _confirm_step("confirm_name", _confirmation_name),
        _persist_only("persist_name", _persist_name),
        _success_step("success_name", _success_name),
    ],
    "add_beneficiary": [
        _verify_step(), _otp_step(),
        {"name": "collect_beneficiary", "kind": "collect", "card_factory": _beneficiary_form,
         "validator": _validate_beneficiary, "collector": _collect_beneficiary, "persister": None,
         "requires_verified": True},
        _confirm_step("confirm_beneficiary", _confirmation_beneficiary),
        _persist_only("persist_beneficiary", _persist_beneficiary),
        _success_step("success_beneficiary", _success_beneficiary),
    ],
    "update_beneficiary": [
        _verify_step(), _otp_step(),
        # Pick which beneficiary + which action (add | edit | remove)
        {"name": "pick_beneficiary", "kind": "collect", "card_factory": _beneficiary_picker,
         "validator": _validate_beneficiary_picker, "collector": _collect_beneficiary_pick, "persister": None,
         "requires_verified": True},
        # Resolve pick → stashes beneficiary_target dict (for edit/remove only)
        {"name": "resolve_pick", "kind": "persist", "card_factory": None, "validator": None,
         "collector": None, "persister": _resolve_beneficiary_pick, "requires_verified": True},
        # ----- edit/add path (skip when action == 'remove') -----
        {"name": "edit_beneficiary", "kind": "collect", "card_factory": _beneficiary_form,
         "validator": _validate_beneficiary, "collector": _collect_beneficiary, "persister": None,
         "requires_verified": True,
         "skip_if": lambda s: (s.get("collected_data") or {}).get("beneficiary_action") == "remove"},
        {"name": "confirm_beneficiary_edit", "kind": "confirm",
         "card_factory": _confirmation_beneficiary, "validator": _validate_confirmation,
         "collector": None, "persister": None, "requires_verified": True,
         "skip_if": lambda s: (s.get("collected_data") or {}).get("beneficiary_action") == "remove"},
        {"name": "persist_beneficiary_edit", "kind": "persist", "card_factory": None,
         "validator": None, "collector": None, "persister": _persist_beneficiary,
         "requires_verified": True,
         "skip_if": lambda s: (s.get("collected_data") or {}).get("beneficiary_action") == "remove"},
        {"name": "success_beneficiary_edit", "kind": "inform",
         "card_factory": _success_beneficiary, "validator": None,
         "collector": None, "persister": None, "requires_verified": False,
         "skip_if": lambda s: (s.get("collected_data") or {}).get("beneficiary_action") == "remove"},
        # ----- remove path (skip when action != 'remove') -----
        {"name": "confirm_beneficiary_remove", "kind": "confirm",
         "card_factory": _confirmation_beneficiary_remove, "validator": _validate_confirmation,
         "collector": None, "persister": None, "requires_verified": True,
         "skip_if": lambda s: (s.get("collected_data") or {}).get("beneficiary_action") != "remove"},
        {"name": "persist_beneficiary_remove", "kind": "persist", "card_factory": None,
         "validator": None, "collector": None, "persister": _persist_beneficiary_remove,
         "requires_verified": True,
         "skip_if": lambda s: (s.get("collected_data") or {}).get("beneficiary_action") != "remove"},
        {"name": "success_beneficiary_remove", "kind": "inform",
         "card_factory": _success_beneficiary_remove, "validator": None,
         "collector": None, "persister": None, "requires_verified": False,
         "skip_if": lambda s: (s.get("collected_data") or {}).get("beneficiary_action") != "remove"},
    ],
    "check_balance": [
        _success_step("show_balance", _balance_view),
    ],
    "view_transactions": [
        _success_step("show_transactions", _transaction_history),
    ],
    "check_request_status": [
        _success_step("show_requests", _request_list),
    ],
    "cancel_request": [
        _verify_step(), _otp_step(),
        {"name": "pick_request", "kind": "collect", "card_factory": _request_list_cancellable,
         "validator": _validate_request_pick, "collector": _collect_request_pick, "persister": None,
         "requires_verified": True},
        _confirm_step("confirm_cancel", lambda s, r: ConfirmationCard(
            title="Cancel this request?",
            summary_lines=[f"Request **{s['collected_data'].get('cancelled_request_id', '')}** will be cancelled."],
        )),
        _persist_only("persist_cancel", _persist_cancel),
        _success_step("success_cancel", _success_cancel),
    ],
    "download_statement": [
        {"name": "pick_statement", "kind": "collect", "card_factory": _statement_picker,
         "validator": _validate_statement_pick, "collector": _collect_statement_pick, "persister": None,
         "requires_verified": False},
        _persist_only("persist_statement", _persist_statement, requires_verified=False),
        _success_step("show_link", _document_link),
    ],
    "change_contribution": [
        _verify_step(), _otp_step(),
        {"name": "collect_contribution", "kind": "collect", "card_factory": _contribution_form,
         "validator": _validate_contribution, "collector": _collect_contribution, "persister": None,
         "requires_verified": True},
        _confirm_step("confirm_contribution", _confirmation_contribution),
        _persist_only("persist_contribution", _persist_contribution),
        _success_step("success_contribution", _success_contribution),
    ],
    "change_allocation": [
        _verify_step(), _otp_step(),
        {"name": "collect_allocation", "kind": "collect", "card_factory": _allocation_form,
         "validator": _validate_allocation, "collector": _collect_allocation, "persister": None,
         "requires_verified": True},
        _confirm_step("confirm_allocation", _confirmation_allocation),
        _persist_only("persist_allocation", _persist_allocation),
        _success_step("success_allocation", _success_allocation),
    ],
    "rebalance": [
        _verify_step(), _otp_step(),
        # Snapshot drift before rendering, so persister has the same plan
        {"name": "snapshot_drift", "kind": "persist", "card_factory": None, "validator": None,
         "collector": None, "persister": _drift_snapshot, "requires_verified": True},
        {"name": "review_drift", "kind": "collect", "card_factory": _drift_view,
         "validator": _validate_confirmation, "collector": None, "persister": None,
         "requires_verified": True},
        _persist_only("persist_rebalance", _persist_rebalance),
        _success_step("success_rebalance", _success_rebalance),
    ],
    "take_rmd": [
        _verify_step(), _otp_step(),
        {"name": "show_rmd", "kind": "collect", "card_factory": _rmd_amount,
         "validator": _validate_acknowledge, "collector": None, "persister": None,
         "requires_verified": True},
        {"name": "pick_method", "kind": "collect", "card_factory": _distribution_method,
         "validator": _validate_distribution_method, "collector": _collect_distribution_method, "persister": None,
         "requires_verified": True},
        _confirm_step("confirm_rmd", _confirmation_rmd),
        _persist_only("persist_rmd", _persist_rmd),
        _success_step("success_rmd", _success_rmd),
    ],
    "request_loan": [
        _verify_step(), _otp_step(),
        {"name": "show_quote", "kind": "collect", "card_factory": _loan_quote,
         "validator": _validate_acknowledge, "collector": None, "persister": None,
         "requires_verified": True},
        {"name": "collect_loan", "kind": "collect", "card_factory": _loan_request_form,
         "validator": _validate_loan_request, "collector": _collect_loan_request, "persister": None,
         "requires_verified": True},
        _confirm_step("confirm_loan", _confirmation_loan),
        _persist_only("persist_loan", _persist_loan),
        _success_step("success_loan", _success_loan),
    ],
    "loan_status": [
        _success_step("show_loans", _loan_status),
    ],
    "qualified_distribution": [
        _verify_step(), _otp_step(),
        {"name": "collect_distribution", "kind": "collect", "card_factory": _distribution_request_form,
         "validator": _validate_distribution_request, "collector": _collect_distribution, "persister": None,
         "requires_verified": True},
        _confirm_step("confirm_distribution", _confirmation_distribution),
        _persist_only("persist_distribution", _persist_distribution),
        _success_step("success_distribution", _success_distribution),
    ],
    "update_tax_withholding": [
        _verify_step(), _otp_step(),
        {"name": "collect_tax_withholding", "kind": "collect", "card_factory": _tax_withholding_form,
         "validator": _validate_tax_withholding, "collector": _collect_tax_withholding, "persister": None,
         "requires_verified": True},
        _confirm_step("confirm_tax_withholding", _confirmation_tax_withholding),
        _persist_only("persist_tax_withholding", _persist_tax_withholding),
        _success_step("success_tax_withholding", _success_tax_withholding),
    ],
    "update_direct_deposit": [
        _verify_step(), _otp_step(),
        {"name": "collect_bank", "kind": "collect", "card_factory": _bank_account_form,
         "validator": _validate_bank_account, "collector": _collect_bank_account, "persister": None,
         "requires_verified": True},
        {"name": "bank_add", "kind": "persist", "card_factory": None, "validator": None,
         "collector": None, "persister": _persist_bank_add, "requires_verified": True},
        {"name": "verify_microdeposit", "kind": "collect", "card_factory": _microdeposit_card,
         "validator": _validate_microdeposit, "collector": _collect_microdeposit, "persister": None,
         "requires_verified": True},
        _confirm_step("confirm_bank_default", _confirmation_bank_default),
        _persist_only("persist_bank_verify", _persist_bank_verify),
        _success_step("success_bank", _success_bank),
    ],
    "manage_mfa": [
        _verify_step(), _otp_step(),
        {"name": "list_devices", "kind": "collect", "card_factory": _mfa_device_list,
         "validator": _validate_mfa_action, "collector": _collect_mfa_action, "persister": None,
         "requires_verified": True},
        # Only show enrollment form when action == 'enroll'
        {"name": "enroll_form", "kind": "collect", "card_factory": _mfa_enroll_form,
         "validator": _validate_mfa_enroll, "collector": _collect_mfa_enroll, "persister": None,
         "requires_verified": True,
         "skip_if": lambda s: (s.get("collected_data") or {}).get("mfa_action", {}).get("action") != "enroll"},
        _confirm_step("confirm_mfa", _confirmation_mfa),
        _persist_only("persist_mfa", _persist_mfa),
        _success_step("success_mfa", _success_mfa),
    ],
    "delivery_preferences": [
        {"name": "collect_delivery_prefs", "kind": "collect", "card_factory": _delivery_prefs_form,
         "validator": None, "collector": _collect_delivery_prefs, "persister": None,
         "requires_verified": False},
        _confirm_step("confirm_delivery_prefs", _confirmation_delivery_prefs, requires_verified=False),
        _persist_only("persist_delivery_prefs", _persist_delivery_prefs, requires_verified=False),
        _success_step("success_delivery_prefs", _success_delivery_prefs),
    ],
    "reset_password": [
        _verify_step(),
        _persist_only("persist_password_reset", _persist_password_reset, requires_verified=False),
        _success_step("show_reset_link", _password_reset_link),
    ],
    # ---------- Tier 3: specialist-routed ----------
    "hardship_withdrawal": [
        _verify_step(), _otp_step(),
        {"name": "collect_hardship", "kind": "collect", "card_factory": _hardship_form,
         "validator": _validate_hardship, "collector": _collect_hardship, "persister": None,
         "requires_verified": True},
        _persist_only("persist_hardship", _persist_specialist("hardship_withdrawal", "hardship")),
        _success_step("route_hardship", _specialist_routing),
    ],
    "rollover_out": [
        _verify_step(), _otp_step(),
        {"name": "collect_rollover_out", "kind": "collect", "card_factory": _rollover_out_form,
         "validator": _validate_rollover_out, "collector": _collect_rollover_out, "persister": None,
         "requires_verified": True},
        _confirm_step("confirm_rollover_out", _confirmation_rollover_out),
        _persist_only("persist_rollover_out", _persist_specialist("rollover_out", "rollover_out")),
        _success_step("route_rollover_out", _specialist_routing),
    ],
    "rollover_in": [
        {"name": "collect_rollover_in", "kind": "collect", "card_factory": _rollover_in_form,
         "validator": _validate_rollover_in, "collector": _collect_rollover_in, "persister": None,
         "requires_verified": False},
        _persist_only("persist_rollover_in", _persist_specialist("rollover_in", "rollover_in"), requires_verified=False),
        _success_step("route_rollover_in", _specialist_routing),
    ],
    "qdro": [
        _verify_step(), _otp_step(),
        {"name": "collect_qdro", "kind": "collect", "card_factory": _qdro_form,
         "validator": _validate_qdro, "collector": _collect_qdro, "persister": None,
         "requires_verified": True},
        _persist_only("persist_qdro", _persist_specialist("qdro", "qdro")),
        _success_step("route_qdro", _specialist_routing),
    ],
}


# ---------- shared success message lookup ----------

INTENT_SUCCESS_MESSAGES: dict[str, str] = {
    "change_address": "Your address has been updated.",
    "change_phone": "Your phone number has been updated.",
    "change_email": "Your email address has been updated.",
    "change_name": "Your legal name has been updated.",
    "add_beneficiary": "The new beneficiary has been added.",
    "update_beneficiary": "Your beneficiary has been updated.",
    "change_contribution": "Your contribution amount has been updated.",
    "change_allocation": "Your investment allocation has been updated.",
    "rebalance": "Your rebalance has been submitted.",
    "check_balance": "Here's your current balance.",
    "view_transactions": "Here are your recent transactions.",
    "check_request_status": "Here are your recent requests.",
    "cancel_request": "Your request has been cancelled.",
    "download_statement": "Your statement is ready.",
    "update_tax_withholding": "Your tax withholding has been updated.",
    "update_direct_deposit": "Your bank account has been added and verified.",
    "manage_mfa": "Your MFA settings have been updated.",
    "delivery_preferences": "Your delivery preferences have been updated.",
    "reset_password": "A password reset link has been sent.",
    "request_loan": "Your loan request has been submitted.",
    "loan_status": "Here's your loan status.",
    "take_rmd": "Your RMD has been scheduled.",
    "qualified_distribution": "Your distribution has been requested.",
    "hardship_withdrawal": "Your hardship request has been routed.",
    "rollover_out": "Your rollover request has been routed.",
    "rollover_in": "Your rollover intake has been routed.",
    "qdro": "Your QDRO intake has been routed.",
}
