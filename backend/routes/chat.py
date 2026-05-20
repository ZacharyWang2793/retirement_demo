"""Chat endpoint: POST a user message, get an SSE stream of canvas events."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from backend.deps import DEFAULT_CUSTOMER_ID, get_graph
from backend.streaming import stream_graph_events

router = APIRouter()


class ChatRequest(BaseModel):
    text: str
    customer_id: str | None = None


@router.post("/chat/{thread_id}")
def chat(thread_id: str, body: ChatRequest, graph=Depends(get_graph)):
    payload = {
        "messages": [HumanMessage(content=body.text)],
        "customer_id": body.customer_id or DEFAULT_CUSTOMER_ID,
        "thread_id": thread_id,
        "verified": True,  # demo mode — identity verification step is skipped
    }
    config = {"configurable": {"thread_id": thread_id}}
    return StreamingResponse(
        stream_graph_events(graph, payload, config),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
