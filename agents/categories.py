"""Category registry: the 6 domain groupings, each owned by one subagent.

A ``CategorySpec`` bundles, for one retirement-account domain:
- the member intents it owns (with their step plans, reused from ``INTENT_PLANS``),
- a domain-knowledge system prompt the subagent's brain uses to answer questions
  and handle situations within that domain.

Intent → category mapping mirrors the existing groupings in ``agents/intents.py``.
Domain facts that previously lived in the orchestrator prompt now live here, on the
category that owns them (e.g. the specialist rollover/hardship/QDRO facts live on
``distributions``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.intents import INTENT_LABELS, INTENT_PLANS, INTENT_SUCCESS_MESSAGES


# Intents handled by a specialist team rather than completed instantly. The
# supervisor proposes (answers first) before routing these.
SPECIALIST_INTENTS: set[str] = {"rollover_out", "rollover_in", "hardship_withdrawal", "qdro"}

# Read-only intents — present the data immediately, never propose.
READONLY_INTENTS: set[str] = {"check_balance", "view_transactions", "check_request_status"}


@dataclass(frozen=True)
class CategorySpec:
    category_id: str
    label: str
    system_prompt: str                      # domain knowledge spanning all member intents
    member_intents: tuple[str, ...]         # intents this agent owns
    model: str | None = None                # optional per-agent model override
    # members maps intent_id -> step plan (reused by reference from INTENT_PLANS)
    members: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def label_for(self, intent_id: str) -> str:
        return INTENT_LABELS.get(intent_id, intent_id)

    def success_message_for(self, intent_id: str) -> str:
        return INTENT_SUCCESS_MESSAGES.get(intent_id, "")


# ---------- per-category domain knowledge prompts ----------

_PROFILE_CONTACT = """\
This domain covers a member's profile and contact details: home address, phone number, \
email address, and legal name.
- Address changes become the member's official address of record once confirmed.
- A legal name change requires a supporting document (marriage certificate, court order, \
or government ID) and re-issues current-year tax forms in the new name.
- Phone and email changes take effect immediately after confirmation.
All of these complete instantly once the member confirms."""

_BENEFICIARIES = """\
This domain covers account beneficiaries — the people or entities who receive the account \
if the member passes away.
- A beneficiary can be primary (first in line) or contingent (backup).
- Each beneficiary has a name, relationship, date of birth, SSN last-4, and an allocation \
percentage. Primary allocations across beneficiaries are intended to total 100%.
- Members can add a new beneficiary, edit an existing one, or remove one."""

_ACCOUNT_STATUS = """\
This domain covers viewing account information and managing pending requests.
- Balance (total and vested), recent transactions, and request status are READ-ONLY — \
present the data directly and finish; never ask the member to confirm a read.
- Cancelling a request is an action: only requests still in 'pending' status are eligible; \
completed or already-cancelled requests cannot be cancelled."""

_INVESTMENTS = """\
This domain covers how the member's retirement money is invested.
- Contribution: the standing payroll election as a percentage of pay; a change applies on \
the next payroll cycle.
- Allocation: the target percentage for each fund. Targets must sum to 100%. Changes apply \
to future contributions, not existing holdings.
- Rebalance: trading the current holdings back to their target allocation. 'Drift' is how far \
each fund is from its target; rebalancing buys underweight funds and sells overweight ones. \
Trades typically execute within two business days."""

# The 4 specialist fact blocks, relocated here from the orchestrator prompt.
_DISTRIBUTIONS = """\
This domain covers taking money out of retirement accounts. Some flows complete instantly \
(required minimum distribution, qualified distribution); four are reviewed by a specialist \
team before they proceed (rollover out, rollover in, hardship withdrawal, QDRO).

Use these facts to answer accurately, conversationally — never dump them as a list:
- Required minimum distribution (RMD): once a member reaches the required age, the IRS \
requires a minimum amount be withdrawn each year (calculated with the IRS Uniform Lifetime \
Table); missing it carries a penalty. RMDs complete instantly here.
- Qualified distribution: a standard withdrawal; subject to applicable withholding. Amounts \
have a minimum and funds go out via the selected method.
- Rollover out: a direct (trustee-to-trustee) rollover moves funds straight to the new plan \
with no taxes withheld. An indirect rollover pays the participant first: 20% mandatory federal \
withholding applies, and the full original amount must be redeposited within 60 days or it \
counts as a taxable distribution. A 1099-R is issued either way. An early-withdrawal penalty \
may apply under age 59 1/2.
- Rollover in: accepts transfers from a 401(k), 403(b), or IRA. A direct transfer avoids \
withholding. Pre-tax money must go into a pre-tax account and Roth into Roth. Done as a direct \
rollover it is not a taxable event.
- Hardship withdrawal: qualifying reasons include medical bills, buying a primary home, \
tuition, eviction or foreclosure prevention, funeral costs, and casualty repairs. Subject to \
income tax and typically a 10% early-withdrawal penalty under age 59 1/2. Supporting \
documentation is required and the amount cannot be repaid.
- QDRO: a Qualified Domestic Relations Order is a court order that divides retirement assets \
in a divorce. The plan must review and approve the order before the alternate payee receives \
their share. Review typically takes 4 to 6 weeks."""

_TAX_BANKING = """\
This domain covers tax withholding and bank / direct-deposit setup.
- Tax withholding: federal withholding on distributions (allowed 0–50%) and state withholding \
(allowed 0–20%), set per tax year.
- Direct deposit: adding a bank account requires verifying ownership with two small \
microdeposits before the account becomes active and can be set as the default for distributions."""


# ---------- the registry ----------

_CATEGORY_DEFS: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("profile_contact", "Profile & contact", _PROFILE_CONTACT,
     ("change_address", "change_phone", "change_email", "change_name")),
    ("beneficiaries", "Beneficiaries", _BENEFICIARIES,
     ("add_beneficiary", "update_beneficiary")),
    ("account_status", "Account status & requests", _ACCOUNT_STATUS,
     ("check_balance", "view_transactions", "check_request_status", "cancel_request")),
    ("investments", "Investments & contributions", _INVESTMENTS,
     ("change_contribution", "change_allocation", "rebalance")),
    ("distributions", "Distributions & withdrawals", _DISTRIBUTIONS,
     ("take_rmd", "hardship_withdrawal", "qualified_distribution",
      "rollover_out", "rollover_in", "qdro")),
    ("tax_banking", "Tax & banking", _TAX_BANKING,
     ("update_tax_withholding", "update_direct_deposit")),
]


def _build_specs() -> dict[str, CategorySpec]:
    specs: dict[str, CategorySpec] = {}
    for cat_id, label, prompt, members in _CATEGORY_DEFS:
        plans = {i: INTENT_PLANS[i] for i in members if i in INTENT_PLANS}
        specs[cat_id] = CategorySpec(
            category_id=cat_id,
            label=label,
            system_prompt=prompt,
            member_intents=members,
            members=plans,
        )
    return specs


CATEGORY_SPECS: dict[str, CategorySpec] = _build_specs()

# Reverse map: intent_id -> category_id
INTENT_TO_CATEGORY: dict[str, str] = {
    intent: cat_id
    for cat_id, spec in CATEGORY_SPECS.items()
    for intent in spec.member_intents
}


def category_node_name(category_id: str) -> str:
    """Graph node name for a category agent (':' is reserved in node names)."""
    return f"cat_{category_id}"
