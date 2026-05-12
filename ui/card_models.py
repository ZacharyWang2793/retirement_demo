"""Pydantic card specs.

Each card is the contract between the agent and the renderer:
- Agent fills in fields, sets the card on `state.pending_card`.
- Streamlit reads `card_type` and dispatches to the matching render function.

Add a new card: subclass BaseCard with a unique `card_type` literal, then add
a render function in `ui/cards.py`.
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


class IdentityVerificationCard(BaseCard):
    card_type: Literal["identity_verification"] = "identity_verification"
    customer_name: str
    submit_label: str = "Verify"


class OtpCard(BaseCard):
    card_type: Literal["otp"] = "otp"
    delivery_hint: str = "We sent a 6-digit code to your phone."
    submit_label: str = "Submit code"


class AddressFormCard(BaseCard):
    card_type: Literal["address_form"] = "address_form"
    prefilled: dict[str, str] = Field(default_factory=dict)
    submit_label: str = "Save address"


class PhoneFormCard(BaseCard):
    card_type: Literal["phone_form"] = "phone_form"
    prefilled: dict[str, str] = Field(default_factory=dict)
    submit_label: str = "Save phone"


class BeneficiaryFormCard(BaseCard):
    card_type: Literal["beneficiary_form"] = "beneficiary_form"
    accounts: list[dict[str, str]] = Field(default_factory=list)  # [{id, label}]
    submit_label: str = "Add beneficiary"


class ContributionFormCard(BaseCard):
    card_type: Literal["contribution_form"] = "contribution_form"
    accounts: list[dict[str, Any]] = Field(default_factory=list)  # [{id, label, current_pct}]
    submit_label: str = "Update contribution"


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


class ConfirmationCard(BaseCard):
    card_type: Literal["confirmation"] = "confirmation"
    summary_lines: list[str] = Field(default_factory=list)  # display-friendly strings
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
    BeneficiaryFormCard,
    ContributionFormCard,
    BalanceViewCard,
    TransactionHistoryCard,
    ConfirmationCard,
    SuccessCard,
    NotImplementedCard,
]


def card_from_dict(data: dict[str, Any]) -> Card:
    """Reconstruct a card from a serialized dict (e.g., from interrupt payload)."""
    type_to_cls = {
        "identity_verification": IdentityVerificationCard,
        "otp": OtpCard,
        "address_form": AddressFormCard,
        "phone_form": PhoneFormCard,
        "beneficiary_form": BeneficiaryFormCard,
        "contribution_form": ContributionFormCard,
        "balance_view": BalanceViewCard,
        "transaction_history": TransactionHistoryCard,
        "confirmation": ConfirmationCard,
        "success": SuccessCard,
        "not_implemented": NotImplementedCard,
    }
    cls = type_to_cls[data["card_type"]]
    return cls(**data)
