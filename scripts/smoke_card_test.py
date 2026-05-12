"""Standalone Streamlit smoke test — no LLM, no graph.

Run: `streamlit run scripts/smoke_card_test.py`

Verifies the card library renders correctly and form submissions return data.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from db.connection import get_db  # noqa: E402
from db.repository import Repository  # noqa: E402
from ui.card_models import (  # noqa: E402
    AddressFormCard,
    IdentityVerificationCard,
)
from ui.cards import render_card  # noqa: E402


st.set_page_config(page_title="Card smoke test", page_icon=":material/check_circle:")
st.title("Card smoke test")
st.caption("No LLM, no LangGraph. Just renders cards directly.")

repo = Repository(get_db())
customer = repo.get_customer("demo-001")

if "submissions" not in st.session_state:
    st.session_state.submissions = []

card_kind = st.sidebar.selectbox("Card to test", ["Identity", "Address"])

if card_kind == "Identity":
    card = IdentityVerificationCard(
        title="Verify your identity",
        subtitle="We need to confirm it's really you before changing account details.",
        customer_name=f"{customer['first_name']} {customer['last_name']}",
    )
else:
    card = AddressFormCard(
        title="Update your address",
        subtitle="Your home address on file.",
        prefilled={
            "address_line1": customer["address_line1"],
            "address_line2": customer["address_line2"] or "",
            "address_city": customer["address_city"],
            "address_state": customer["address_state"],
            "address_postal": customer["address_postal"],
        },
    )

result = render_card(card, key=f"smoke-{card_kind}")

if result is not None:
    st.session_state.submissions.append(result)

if st.session_state.submissions:
    st.divider()
    st.subheader("Submissions captured")
    for s in st.session_state.submissions:
        st.json(s)
