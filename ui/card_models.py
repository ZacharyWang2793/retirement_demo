"""Pydantic card specs.

Each card is the contract between the agent and the renderer:
- Agent fills in fields, sets the card on `state.pending_card`.
- Streamlit reads `card_type` and dispatches to the matching render function.

Add a new card: subclass BaseCard with a unique `card_type` literal, then add
a render function in `ui/cards.py`, register it in `render_card`'s dispatch,
and add the class to the `Card` union and `card_from_dict` map below.
"""
from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, Field

US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
]


class BaseCard(BaseModel):
    title: str
    subtitle: str | None = None
    helper_text: str | None = None
    submit_label: str = "Save"
    error: str | None = None  # validation error from previous attempt
    icon: str | None = None  # Material Symbols name; renderer falls back to per-type default


# ---------- identity / otp ----------

class IdentityVerificationCard(BaseCard):
    card_type: Literal["identity_verification"] = "identity_verification"
    customer_name: str
    submit_label: str = "Verify"


class OtpCard(BaseCard):
    card_type: Literal["otp"] = "otp"
    delivery_hint: str = "We sent a 6-digit code to your phone."
    submit_label: str = "Submit code"


# ---------- profile / contact ----------

class AddressFormCard(BaseCard):
    card_type: Literal["address_form"] = "address_form"
    prefilled: dict[str, str] = Field(default_factory=dict)
    submit_label: str = "Save address"


class PhoneFormCard(BaseCard):
    card_type: Literal["phone_form"] = "phone_form"
    prefilled: dict[str, str] = Field(default_factory=dict)
    submit_label: str = "Save phone"


class EmailFormCard(BaseCard):
    card_type: Literal["email_form"] = "email_form"
    prefilled: dict[str, str] = Field(default_factory=dict)
    submit_label: str = "Save email"


class NameFormCard(BaseCard):
    card_type: Literal["name_form"] = "name_form"
    prefilled: dict[str, str] = Field(default_factory=dict)
    submit_label: str = "Save legal name"


# ---------- beneficiaries ----------

class BeneficiaryFormCard(BaseCard):
    card_type: Literal["beneficiary_form"] = "beneficiary_form"
    accounts: list[dict[str, str]] = Field(default_factory=list)  # [{id, label}]
    mode: Literal["add", "edit"] = "add"
    target_beneficiary_id: str | None = None  # set when mode == 'edit'
    prefilled: dict[str, Any] = Field(default_factory=dict)
    submit_label: str = "Save beneficiary"


class BeneficiaryPickerCard(BaseCard):
    card_type: Literal["beneficiary_picker"] = "beneficiary_picker"
    beneficiaries: list[dict[str, Any]] = Field(default_factory=list)
    submit_label: str = "Continue"


# ---------- contributions / allocation ----------

class ContributionFormCard(BaseCard):
    card_type: Literal["contribution_form"] = "contribution_form"
    accounts: list[dict[str, Any]] = Field(default_factory=list)  # [{id, label, current_pct}]
    submit_label: str = "Update contribution"


class AllocationFormCard(BaseCard):
    card_type: Literal["allocation_form"] = "allocation_form"
    account_id: str
    account_label: str
    funds: list[dict[str, Any]] = Field(default_factory=list)  # [{ticker,name,current_pct,target_pct}]
    submit_label: str = "Save allocation"


class DriftViewCard(BaseCard):
    card_type: Literal["drift_view"] = "drift_view"
    account_id: str
    account_label: str
    funds: list[dict[str, Any]] = Field(default_factory=list)  # [{ticker,name,current_pct,target_pct,drift_pct,trade_amount}]
    submit_label: str = "Submit rebalance"


# ---------- read-only ----------

class BalanceViewCard(BaseCard):
    card_type: Literal["balance_view"] = "balance_view"
    total_balance: float
    vested_balance: float
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    submit_label: str = "Done"


class TransactionHistoryCard(BaseCard):
    card_type: Literal["transaction_history"] = "transaction_history"
    transactions: list[dict[str, Any]] = Field(default_factory=list)
    submit_label: str = "Done"


class RequestListCard(BaseCard):
    card_type: Literal["request_list"] = "request_list"
    requests: list[dict[str, Any]] = Field(default_factory=list)
    selectable: bool = False  # True → pick one for cancellation
    submit_label: str = "Done"


# ---------- tax / banking ----------

class TaxWithholdingFormCard(BaseCard):
    card_type: Literal["tax_withholding_form"] = "tax_withholding_form"
    accounts: list[dict[str, str]] = Field(default_factory=list)
    prefilled: dict[str, Any] = Field(default_factory=dict)
    submit_label: str = "Save withholding"


class BankAccountFormCard(BaseCard):
    card_type: Literal["bank_account_form"] = "bank_account_form"
    submit_label: str = "Add bank"


class MicroDepositCard(BaseCard):
    card_type: Literal["microdeposit"] = "microdeposit"
    bank_account_id: str
    bank_nickname: str
    account_last4: str
    submit_label: str = "Verify deposits"


# ---------- distributions ----------

class RmdAmountCard(BaseCard):
    card_type: Literal["rmd_amount"] = "rmd_amount"
    required_amount: float
    tax_year: int
    deadline: str
    submit_label: str = "Continue"


class DistributionMethodCard(BaseCard):
    card_type: Literal["distribution_method"] = "distribution_method"
    bank_accounts: list[dict[str, str]] = Field(default_factory=list)
    submit_label: str = "Continue"


class DistributionRequestFormCard(BaseCard):
    card_type: Literal["distribution_request_form"] = "distribution_request_form"
    accounts: list[dict[str, str]] = Field(default_factory=list)
    submit_label: str = "Request distribution"


# ---------- specialist-routed (Tier 3) ----------

class HardshipReasonFormCard(BaseCard):
    card_type: Literal["hardship_form"] = "hardship_form"
    accounts: list[dict[str, str]] = Field(default_factory=list)
    submit_label: str = "Submit for review"


class RolloverOutFormCard(BaseCard):
    card_type: Literal["rollover_out_form"] = "rollover_out_form"
    accounts: list[dict[str, str]] = Field(default_factory=list)
    submit_label: str = "Continue"


class RolloverInFormCard(BaseCard):
    card_type: Literal["rollover_in_form"] = "rollover_in_form"
    accounts: list[dict[str, str]] = Field(default_factory=list)
    submit_label: str = "Submit for review"


class QdroIntakeFormCard(BaseCard):
    card_type: Literal["qdro_form"] = "qdro_form"
    submit_label: str = "Submit for review"


class SpecialistRoutingCard(BaseCard):
    card_type: Literal["specialist_routing"] = "specialist_routing"
    request_id: str
    eta_business_days: int = 5
    contact_phone: str = "1-800-555-7483"
    submit_label: str = "Done"


# ---------- terminal ----------

class ConfirmationCard(BaseCard):
    card_type: Literal["confirmation"] = "confirmation"
    summary_lines: list[str] = Field(default_factory=list)
    diff: list[dict[str, str]] = Field(default_factory=list)  # [{field, before, after}]
    submit_label: str = "Confirm"


class SuccessCard(BaseCard):
    card_type: Literal["success"] = "success"
    summary_lines: list[str] = Field(default_factory=list)
    request_id: str | None = None
    submit_label: str = "Done"


class NotImplementedCard(BaseCard):
    card_type: Literal["not_implemented"] = "not_implemented"
    intent: str
    next_steps: list[str] = Field(default_factory=list)
    submit_label: str = "OK"


Card = Union[
    IdentityVerificationCard,
    OtpCard,
    AddressFormCard,
    PhoneFormCard,
    EmailFormCard,
    NameFormCard,
    BeneficiaryFormCard,
    BeneficiaryPickerCard,
    ContributionFormCard,
    AllocationFormCard,
    DriftViewCard,
    BalanceViewCard,
    TransactionHistoryCard,
    RequestListCard,
    TaxWithholdingFormCard,
    BankAccountFormCard,
    MicroDepositCard,
    RmdAmountCard,
    DistributionMethodCard,
    DistributionRequestFormCard,
    HardshipReasonFormCard,
    RolloverOutFormCard,
    RolloverInFormCard,
    QdroIntakeFormCard,
    SpecialistRoutingCard,
    ConfirmationCard,
    SuccessCard,
    NotImplementedCard,
]


_TYPE_TO_CLS: dict[str, type[BaseCard]] = {
    "identity_verification": IdentityVerificationCard,
    "otp": OtpCard,
    "address_form": AddressFormCard,
    "phone_form": PhoneFormCard,
    "email_form": EmailFormCard,
    "name_form": NameFormCard,
    "beneficiary_form": BeneficiaryFormCard,
    "beneficiary_picker": BeneficiaryPickerCard,
    "contribution_form": ContributionFormCard,
    "allocation_form": AllocationFormCard,
    "drift_view": DriftViewCard,
    "balance_view": BalanceViewCard,
    "transaction_history": TransactionHistoryCard,
    "request_list": RequestListCard,
    "tax_withholding_form": TaxWithholdingFormCard,
    "bank_account_form": BankAccountFormCard,
    "microdeposit": MicroDepositCard,
    "rmd_amount": RmdAmountCard,
    "distribution_method": DistributionMethodCard,
    "distribution_request_form": DistributionRequestFormCard,
    "hardship_form": HardshipReasonFormCard,
    "rollover_out_form": RolloverOutFormCard,
    "rollover_in_form": RolloverInFormCard,
    "qdro_form": QdroIntakeFormCard,
    "specialist_routing": SpecialistRoutingCard,
    "confirmation": ConfirmationCard,
    "success": SuccessCard,
    "not_implemented": NotImplementedCard,
}


def card_from_dict(data: dict[str, Any]) -> Card:
    """Reconstruct a card from a serialized dict (e.g., from interrupt payload)."""
    return _TYPE_TO_CLS[data["card_type"]](**data)
