"""Render the chat history + the empty-state quick-actions chip row."""
from __future__ import annotations

from typing import Any

import streamlit as st


def render_chat_history(history: list[dict[str, Any]]) -> None:
    for msg in history:
        role = msg.get("role", "assistant")
        if role == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        elif role == "assistant":
            with st.chat_message("assistant"):
                st.write(msg["content"])
        elif role == "system":
            with st.chat_message("assistant"):
                st.caption(msg["content"])


_CHIPS: list[tuple[str, str]] = [
    ("Check my balance", "What's my balance?"),
    ("Show recent transactions", "Show my recent transactions"),
    ("Update my address", "I want to change my address"),
    ("Add a beneficiary", "Add a beneficiary"),
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
