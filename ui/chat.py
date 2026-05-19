"""Render the chat history + the empty-state quick-actions chip row."""
from __future__ import annotations

from typing import Any

import streamlit as st


def render_chat_history(history: list[dict[str, Any]]) -> None:
    # Import here to avoid circular imports at module load time.
    from ui.card_models import _TYPE_TO_CLS
    from ui.cards import render_card_readonly

    for i, msg in enumerate(history):
        role = msg.get("role", "assistant")
        if role == "card":
            # Re-render a previously dismissed terminal card as read-only.
            card_type = msg.get("card_type")
            card_data = msg.get("card_data") or {}
            cls = _TYPE_TO_CLS.get(card_type)
            if cls:
                try:
                    card = cls(**card_data)
                    render_card_readonly(card, key=f"hist-card-{i}-{card_type}")
                except Exception:
                    pass  # Silently skip malformed history entries
        elif role == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        elif role == "assistant":
            with st.chat_message("assistant"):
                st.write(msg["content"])
        elif role == "system":
            with st.chat_message("assistant"):
                st.caption(msg["content"])


_CHIPS: list[tuple[str, str]] = [
    ("Check balance", "What's my balance?"),
    ("View transactions", "Show my recent transactions"),
    ("Update address", "I want to change my address"),
    ("Add beneficiary", "Add a beneficiary"),
]


def render_quick_actions() -> str | None:
    """Render an empty-state chip row above the chat input.

    Returns the prompt text the user clicked, or None.
    """
    with st.chat_message("assistant"):
        st.write(
            "Hi! I can help you check balances, update profile details, manage beneficiaries, "
            "or start a withdrawal or rollover. Pick a quick action below or type your question."
        )
    st.markdown('<div class="rs-chip-row">', unsafe_allow_html=True)
    cols = st.columns(len(_CHIPS))
    clicked: str | None = None
    for i, (label, prompt) in enumerate(_CHIPS):
        with cols[i]:
            if st.button(label, key=f"qa-chip-{i}", use_container_width=True):
                clicked = prompt
    st.markdown('</div>', unsafe_allow_html=True)
    return clicked
