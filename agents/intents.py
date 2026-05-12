"""Intent enum + per-intent step plan registry.

A "step" is a dict:
  {
    "name":            short id,
    "kind":            verify | collect | confirm | persist | inform,
    "card_factory":    callable(state, repo) -> Card  (None if no card; e.g. internal persist step),
    "validator":       callable(submission, state, repo) -> str | None  (returns error message on fail),
    "persister":       callable(state, repo, idempotency_key) -> dict   (return data merged into state.collected_data),
    "requires_verified": bool,
  }

The full taxonomy is registered. A handful of intents have full plans;
the rest fall through to a single NotImplementedCard step so the routing
demo still works for them.
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable

from db.repository import Repository
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
)


# ---------- intent enum ----------

INTENTS: list[str] = [
    # profile / contact
    "change_address",
    "change_phone",
    "change_email",
    "change_name",
    # beneficiaries
    "add_beneficiary",
    "update_beneficiary",
    # read-only / status
    "check_balance",
    "view_transactions",
    "download_statement",
    "check_request_status",
    "cancel_request",
    # investments / contributions
    "change_contribution",
    "change_allocation",
    "rebalance",
    # distributions / withdrawals
    "take_rmd",
    "hardship_withdrawal",
    "request_loan",
    "loan_status",
    "qualified_distribution",
    "rollover_out",
    "rollover_in",
    "qdro",
    # tax / banking / security
    "update_tax_withholding",
    "update_direct_deposit",
    "manage_mfa",
    "delivery_preferences",
    "reset_password",
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

import re

INTENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(change|update|new)\b.*\b(address|street|home)\b", re.I), "change_address"),
    (re.compile(r"\bmoved\b|\b(my )?new (home|place)\b", re.I), "change_address"),
    (re.compile(r"\b(change|update|new)\b.*\b(phone|cell|mobile|number)\b", re.I), "change_phone"),
    (re.compile(r"\b(change|update)\b.*\bemail\b", re.I), "change_email"),
    (re.compile(r"\b(change|update)\b.*\b(legal )?name\b", re.I), "change_name"),
    (re.compile(r"\badd\b.*\bbeneficiary\b", re.I), "add_beneficiary"),
    (re.compile(r"\b(update|remove|change)\b.*\bbeneficiar(y|ies)\b", re.I), "update_beneficiary"),
    (re.compile(r"\b(check|what'?s|see|show)\b.*\bbalance\b", re.I), "check_balance"),
    (re.compile(r"\bhow much\b.*\b(have|saved|in my)\b", re.I), "check_balance"),
    (re.compile(r"\b(my|account)\b.*\bbalance\b", re.I), "check_balance"),
    (re.compile(r"\b(transactions?|recent activity|history)\b", re.I), "view_transactions"),
    (re.compile(r"\b(statement|1099|tax form)\b", re.I), "download_statement"),
    (re.compile(r"\b(status|update on|pending)\b.*\b(request|change|update)\b", re.I), "check_request_status"),
    (re.compile(r"\b(cancel|withdraw)\b.*\brequest\b", re.I), "cancel_request"),
    (re.compile(r"\b(change|update|increase|decrease)\b.*\bcontribution\b", re.I), "change_contribution"),
    (re.compile(r"\b(change|update)\b.*\ballocation\b", re.I), "change_allocation"),
    (re.compile(r"\brebalance\b", re.I), "rebalance"),
    (re.compile(r"\brmd\b|\brequired minimum distribution\b", re.I), "take_rmd"),
    (re.compile(r"\bhardship\b", re.I), "hardship_withdrawal"),
    (re.compile(r"\b(request|take out|borrow)\b.*\bloan\b", re.I), "request_loan"),
    (re.compile(r"\bloan\b.*\b(status|payoff|balance)\b", re.I), "loan_status"),
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


# ---------- card factories ----------

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
    return PhoneFormCard(
        title="Update your phone number",
        prefilled={"phone": c["phone"]},
    )


def _beneficiary_form(state: dict[str, Any], repo: Repository) -> Card:
    accounts = repo.get_accounts(state["customer_id"])
    return BeneficiaryFormCard(
        title="Add a beneficiary",
        subtitle="Pick the account, then enter the beneficiary's information.",
        accounts=[
            {"id": a["id"], "label": f"{a['plan_name']} ({a['account_type']})"}
            for a in accounts
        ],
    )


def _contribution_form(state: dict[str, Any], repo: Repository) -> Card:
    accounts = repo.get_accounts(state["customer_id"])
    rows = []
    for a in accounts:
        if a["account_type"] not in ("401k", "roth_401k"):
            continue
        contrib = repo.get_contribution(a["id"])
        rows.append({
            "id": a["id"],
            "label": f"{a['plan_name']}",
            "current_pct": contrib["contribution_pct"] if contrib else 0.0,
        })
    return ContributionFormCard(
        title="Update contribution amount",
        subtitle="Sets your standing election. Effective on the next payroll cycle.",
        accounts=rows,
    )


def _confirmation_address(state: dict[str, Any], repo: Repository) -> Card:
    before = repo.get_customer(state["customer_id"])
    after = state["collected_data"]["address"]
    keys = ["address_line1", "address_line2", "address_city", "address_state", "address_postal"]
    diff = []
    for k in keys:
        b = before.get(k) or ""
        a = after.get(k) or ""
        if str(b) != str(a):
            diff.append({"field": k.replace("address_", "").replace("_", " ").title(), "before": str(b), "after": str(a)})
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


def _confirmation_beneficiary(state: dict[str, Any], repo: Repository) -> Card:
    b = state["collected_data"]["beneficiary"]
    return ConfirmationCard(
        title="Confirm new beneficiary",
        summary_lines=[
            f"**{b['name']}** ({b['relationship']}) — {b['type']} beneficiary",
            f"Allocation: {b['allocation_pct']}%",
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


def _balance_view(state: dict[str, Any], repo: Repository) -> Card:
    summary = repo.get_balance_summary(state["customer_id"])
    return BalanceViewCard(
        title="Your retirement balance",
        total_balance=summary["total_balance"],
        vested_balance=summary["vested_balance"],
        accounts=summary["accounts"],
    )


def _transaction_history(state: dict[str, Any], repo: Repository) -> Card:
    txns = repo.get_transactions(state["customer_id"], limit=15)
    return TransactionHistoryCard(
        title="Recent transactions",
        subtitle="Last 15 entries across all accounts.",
        transactions=txns,
    )


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
    rid = state["collected_data"].get("request_id")
    return SuccessCard(title="Phone updated", summary_lines=[f"New phone: {p['phone']}"], request_id=rid)


def _success_beneficiary(state: dict[str, Any], repo: Repository) -> Card:
    b = state["collected_data"]["beneficiary"]
    rid = state["collected_data"].get("request_id")
    return SuccessCard(
        title="Beneficiary added",
        summary_lines=[f"{b['name']} ({b['relationship']}) — {b['allocation_pct']}%"],
        request_id=rid,
    )


def _success_contribution(state: dict[str, Any], repo: Repository) -> Card:
    d = state["collected_data"]["contribution"]
    rid = state["collected_data"].get("request_id")
    return SuccessCard(
        title="Contribution updated",
        summary_lines=[f"New contribution: {d['contribution_pct']:.1f}%"],
        request_id=rid,
    )


def _stub_card_factory(intent: str, steps: list[str]) -> Callable[[dict[str, Any], Repository], Card]:
    label = INTENT_LABELS.get(intent, intent)

    def factory(state: dict[str, Any], repo: Repository) -> Card:
        return NotImplementedCard(
            title=f"{label}",
            subtitle=f"This intent is registered but the form isn't built in this prototype.",
            intent=label,
            next_steps=steps,
        )

    return factory


# ---------- validators ----------

def _validate_identity(submission: dict[str, Any], state: dict[str, Any], repo: Repository) -> str | None:
    if submission.get("_cancelled"):
        return None
    ok = repo.verify_identity(state["customer_id"], submission["dob"], submission["ssn_last4"])
    return None if ok else "DOB and last-4 SSN don't match our records. Please try again."


def _validate_otp(submission: dict[str, Any], state: dict[str, Any], repo: Repository) -> str | None:
    if submission.get("_cancelled"):
        return None
    return None if submission.get("otp") == "123456" else "Incorrect verification code."


def _validate_address(submission: dict[str, Any], state: dict[str, Any], repo: Repository) -> str | None:
    if submission.get("_cancelled"):
        return None
    for f in ("address_line1", "address_city", "address_state", "address_postal"):
        if not submission.get(f):
            return f"Missing required field: {f}"
    if not (3 <= len(submission["address_postal"]) <= 10):
        return "ZIP code looks invalid."
    return None


def _validate_phone(submission: dict[str, Any], state: dict[str, Any], repo: Repository) -> str | None:
    if submission.get("_cancelled"):
        return None
    digits = "".join(c for c in submission.get("phone", "") if c.isdigit())
    return None if len(digits) == 10 else "Phone must have 10 digits."


def _validate_beneficiary(submission: dict[str, Any], state: dict[str, Any], repo: Repository) -> str | None:
    if submission.get("_cancelled"):
        return None
    for f in ("account_id", "type", "name", "relationship", "dob", "ssn_last4", "allocation_pct"):
        if submission.get(f) in (None, ""):
            return f"Missing required field: {f}"
    return None


def _validate_contribution(submission: dict[str, Any], state: dict[str, Any], repo: Repository) -> str | None:
    if submission.get("_cancelled"):
        return None
    pct = submission.get("contribution_pct")
    if pct is None or not 0 <= float(pct) <= 100:
        return "Contribution must be between 0 and 100%."
    return None


def _validate_confirmation(submission: dict[str, Any], state: dict[str, Any], repo: Repository) -> str | None:
    if submission.get("_cancelled"):
        return None
    return None if submission.get("_confirmed") else "Confirmation required."


# ---------- collectors (move submission into collected_data under a domain key) ----------

def _collect_address(submission: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {"address": submission}


def _collect_phone(submission: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {"phone": submission}


def _collect_beneficiary(submission: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {"beneficiary": submission}


def _collect_contribution(submission: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {"contribution": submission}


# ---------- persisters (write to DB; return data merged back into collected_data) ----------

def _idempotency_key(state: dict[str, Any], step_name: str) -> str:
    raw = f"{state.get('thread_id','')}|{state.get('intent','')}|{step_name}|{state.get('current_step_idx','')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _persist_address(state: dict[str, Any], repo: Repository) -> dict[str, Any]:
    res = repo.update_address(
        customer_id=state["customer_id"],
        thread_id=state.get("thread_id"),
        new_address=state["collected_data"]["address"],
        idempotency_key=_idempotency_key(state, "persist_address"),
    )
    return {"request_id": res.request_id}


def _persist_phone(state: dict[str, Any], repo: Repository) -> dict[str, Any]:
    res = repo.update_phone(
        customer_id=state["customer_id"],
        thread_id=state.get("thread_id"),
        new_phone=state["collected_data"]["phone"]["phone"],
        idempotency_key=_idempotency_key(state, "persist_phone"),
    )
    return {"request_id": res.request_id}


def _persist_beneficiary(state: dict[str, Any], repo: Repository) -> dict[str, Any]:
    b = state["collected_data"]["beneficiary"]
    res = repo.add_beneficiary(
        customer_id=state["customer_id"],
        thread_id=state.get("thread_id"),
        account_id=b["account_id"],
        beneficiary={k: v for k, v in b.items() if k != "account_id"},
        idempotency_key=_idempotency_key(state, "persist_beneficiary"),
    )
    return {"request_id": res.request_id}


def _persist_contribution(state: dict[str, Any], repo: Repository) -> dict[str, Any]:
    d = state["collected_data"]["contribution"]
    res = repo.update_contribution(
        customer_id=state["customer_id"],
        thread_id=state.get("thread_id"),
        account_id=d["account_id"],
        new_pct=d["contribution_pct"],
        idempotency_key=_idempotency_key(state, "persist_contribution"),
    )
    return {"request_id": res.request_id}


# ---------- step builders ----------

def _verify_step() -> dict[str, Any]:
    return {
        "name": "verify_identity",
        "kind": "verify",
        "card_factory": _identity_card,
        "validator": _validate_identity,
        "collector": None,
        "persister": None,
        "requires_verified": False,
    }


def _otp_step() -> dict[str, Any]:
    return {
        "name": "otp",
        "kind": "verify",
        "card_factory": _otp_card,
        "validator": _validate_otp,
        "collector": None,
        "persister": None,
        "requires_verified": False,
    }


# ---------- the registry ----------

INTENT_PLANS: dict[str, list[dict[str, Any]]] = {
    "change_address": [
        _verify_step(),
        _otp_step(),
        {"name": "collect_address", "kind": "collect", "card_factory": _address_form,
         "validator": _validate_address, "collector": _collect_address, "persister": None,
         "requires_verified": True},
        {"name": "confirm_address", "kind": "confirm", "card_factory": _confirmation_address,
         "validator": _validate_confirmation, "collector": None, "persister": None,
         "requires_verified": True},
        {"name": "persist_address", "kind": "persist", "card_factory": None,
         "validator": None, "collector": None, "persister": _persist_address,
         "requires_verified": True},
        {"name": "success_address", "kind": "inform", "card_factory": _success_address,
         "validator": None, "collector": None, "persister": None,
         "requires_verified": False},
    ],
    "change_phone": [
        _verify_step(),
        _otp_step(),
        {"name": "collect_phone", "kind": "collect", "card_factory": _phone_form,
         "validator": _validate_phone, "collector": _collect_phone, "persister": None,
         "requires_verified": True},
        {"name": "confirm_phone", "kind": "confirm", "card_factory": _confirmation_phone,
         "validator": _validate_confirmation, "collector": None, "persister": None,
         "requires_verified": True},
        {"name": "persist_phone", "kind": "persist", "card_factory": None,
         "validator": None, "collector": None, "persister": _persist_phone,
         "requires_verified": True},
        {"name": "success_phone", "kind": "inform", "card_factory": _success_phone,
         "validator": None, "collector": None, "persister": None,
         "requires_verified": False},
    ],
    "add_beneficiary": [
        _verify_step(),
        _otp_step(),
        {"name": "collect_beneficiary", "kind": "collect", "card_factory": _beneficiary_form,
         "validator": _validate_beneficiary, "collector": _collect_beneficiary, "persister": None,
         "requires_verified": True},
        {"name": "confirm_beneficiary", "kind": "confirm", "card_factory": _confirmation_beneficiary,
         "validator": _validate_confirmation, "collector": None, "persister": None,
         "requires_verified": True},
        {"name": "persist_beneficiary", "kind": "persist", "card_factory": None,
         "validator": None, "collector": None, "persister": _persist_beneficiary,
         "requires_verified": True},
        {"name": "success_beneficiary", "kind": "inform", "card_factory": _success_beneficiary,
         "validator": None, "collector": None, "persister": None,
         "requires_verified": False},
    ],
    "change_contribution": [
        _verify_step(),
        _otp_step(),
        {"name": "collect_contribution", "kind": "collect", "card_factory": _contribution_form,
         "validator": _validate_contribution, "collector": _collect_contribution, "persister": None,
         "requires_verified": True},
        {"name": "confirm_contribution", "kind": "confirm", "card_factory": _confirmation_contribution,
         "validator": _validate_confirmation, "collector": None, "persister": None,
         "requires_verified": True},
        {"name": "persist_contribution", "kind": "persist", "card_factory": None,
         "validator": None, "collector": None, "persister": _persist_contribution,
         "requires_verified": True},
        {"name": "success_contribution", "kind": "inform", "card_factory": _success_contribution,
         "validator": None, "collector": None, "persister": None,
         "requires_verified": False},
    ],
    # read-only intents
    "check_balance": [
        {"name": "show_balance", "kind": "inform", "card_factory": _balance_view,
         "validator": None, "collector": None, "persister": None,
         "requires_verified": False},
    ],
    "view_transactions": [
        {"name": "show_transactions", "kind": "inform", "card_factory": _transaction_history,
         "validator": None, "collector": None, "persister": None,
         "requires_verified": False},
    ],
}


# ---------- stubs for everything else (registered, not implemented) ----------

STUB_NEXT_STEPS: dict[str, list[str]] = {
    "change_email": ["Verify identity", "Enter new email", "Confirm via email link", "Update on file"],
    "change_name": ["Verify identity", "Upload supporting document (e.g., marriage certificate)", "Update on file", "Re-issue tax forms with new name"],
    "update_beneficiary": ["Verify identity", "Pick existing beneficiary", "Update fields or remove", "Confirm allocation totals 100%"],
    "download_statement": ["Pick period", "Pick document type (statement / 1099-R / 1099-Q)", "Generate PDF", "Email or download"],
    "check_request_status": ["Pick from your recent requests", "View status and timestamps"],
    "cancel_request": ["Pick a pending request", "Confirm cancellation", "Update status to cancelled"],
    "change_allocation": ["Verify identity", "Show current allocation", "Adjust target % per fund", "Confirm allocations sum to 100%"],
    "rebalance": ["Verify identity", "Show drift from targets", "Compute trades", "Confirm and submit"],
    "take_rmd": ["Verify identity", "Show RMD amount", "Pick distribution method", "Pick tax withholding", "Confirm and submit"],
    "hardship_withdrawal": ["Verify identity", "Pick hardship reason", "Upload supporting documents", "Pick distribution method", "Confirm and submit"],
    "request_loan": ["Verify identity", "Show max loan amount", "Pick amount and term", "Confirm and submit"],
    "loan_status": ["Show outstanding balance", "Show next payment due", "Show payoff amount"],
    "qualified_distribution": ["Verify identity", "Pick amount", "Pick withholding", "Confirm"],
    "rollover_out": ["Verify identity", "Pick destination plan", "Pick amount and method (direct vs indirect)", "Confirm"],
    "rollover_in": ["Verify identity", "Provide source plan info", "Initiate transfer", "Confirm receipt"],
    "qdro": ["Verify identity", "Upload divorce decree / QDRO order", "Route to QDRO team for review"],
    "update_tax_withholding": ["Verify identity", "Pick tax year", "Update federal/state %", "Confirm"],
    "update_direct_deposit": ["Verify identity", "Enter routing/account (last-4)", "Verify with micro-deposits", "Set as default"],
    "manage_mfa": ["Verify identity", "Pick MFA method (SMS / Authenticator / Hardware key)", "Enroll new device", "Confirm"],
    "delivery_preferences": ["Pick paperless settings", "Confirm email on file", "Save"],
    "reset_password": ["Verify identity", "Send reset link", "Set new password"],
}


def _stub_plan(intent: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "stub",
            "kind": "inform",
            "card_factory": _stub_card_factory(intent, STUB_NEXT_STEPS.get(intent, [])),
            "validator": None,
            "collector": None,
            "persister": None,
            "requires_verified": False,
        }
    ]


for _i in INTENTS:
    if _i not in INTENT_PLANS:
        INTENT_PLANS[_i] = _stub_plan(_i)


# ---------- success extractor ----------

INTENT_SUCCESS_MESSAGES: dict[str, str] = {
    "change_address": "Your address has been updated.",
    "change_phone": "Your phone number has been updated.",
    "add_beneficiary": "The new beneficiary has been added.",
    "change_contribution": "Your contribution amount has been updated.",
    "check_balance": "Here's your current balance.",
    "view_transactions": "Here are your recent transactions.",
}
