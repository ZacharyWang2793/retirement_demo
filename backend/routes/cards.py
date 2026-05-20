"""Card endpoints: submit (resume graph with form data) and cancel."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel

from backend.deps import get_graph
from backend.streaming import stream_graph_events

router = APIRouter()


class SubmitRequest(BaseModel):
    submission: dict[str, Any]


@router.post("/cards/{thread_id}/submit")
def submit_card(thread_id: str, body: SubmitRequest, graph=Depends(get_graph)):
    config = {"configurable": {"thread_id": thread_id}}
    return StreamingResponse(
        stream_graph_events(graph, Command(resume=body.submission), config),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/cards/{thread_id}/cancel")
def cancel_card(thread_id: str, graph=Depends(get_graph)):
    config = {"configurable": {"thread_id": thread_id}}
    return StreamingResponse(
        stream_graph_events(graph, Command(resume={"_cancelled": True}), config),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
