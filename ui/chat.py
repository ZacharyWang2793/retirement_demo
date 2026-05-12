"""Render the chat history. Frozen cards (already-submitted) display as read-only summaries."""
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
