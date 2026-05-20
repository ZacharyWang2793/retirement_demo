"""Translate LangGraph state stream → typed SSE events for the frontend.

The frontend consumes these event types:
  - announcement   (short routing message; e.g. "Starting allocation update")
  - card           (a Card to spawn on the canvas, full Pydantic dict)
  - message        (assistant reply text for the inline strip)
  - card_close     (the card with this id should disappear)
  - done           (stream finished)
  - error          (something went wrong)

Each card has an `id` we generate so the frontend can address it later.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Iterator

from langgraph.graph import StateGraph

from ui.card_models import Card


def _format_sse(event: str, data: dict[str, Any] | None = None) -> str:
    payload = json.dumps(data or {}, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def stream_graph_events(graph: StateGraph, payload: Any, config: dict[str, Any]) -> Iterator[str]:
    """Run the graph and yield SSE-formatted strings.

    Tracks which fields we've already emitted so we don't repeat them when LangGraph
    publishes overlapping state snapshots between nodes.
    """
    seen_announcement: str | None = None
    seen_final_message: str | None = None
    last_card_signature: tuple | None = None

    try:
        for ev in graph.stream(payload, config, stream_mode="values"):
            ann = ev.get("routing_announcement")
            if ann and ann != seen_announcement:
                seen_announcement = ann
                yield _format_sse("announcement", {"text": ann})

            msg = ev.get("final_message")
            if msg and msg != seen_final_message:
                seen_final_message = msg
                yield _format_sse("message", {"text": msg})

            card_obj: Card | None = ev.get("pending_card")
            if card_obj is not None:
                # Dedup by card_type + title — adjacent reruns sometimes resurface the same card
                card_dict = card_obj.model_dump() if hasattr(card_obj, "model_dump") else dict(card_obj)
                sig = (card_dict.get("card_type"), card_dict.get("title"))
                if sig != last_card_signature:
                    last_card_signature = sig
                    card_dict["id"] = str(uuid.uuid4())
                    yield _format_sse("card", {"card": card_dict})

        yield _format_sse("done", {})
    except Exception as exc:  # noqa: BLE001 - we want to surface anything to the client
        yield _format_sse("error", {"message": str(exc)})
