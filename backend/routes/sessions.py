"""Canvas session endpoints — list / create / get / save / delete sessions.

A "session" is a single canvas instance: thread_id + saved card layout + messages.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.deps import DEFAULT_CUSTOMER_ID, get_repo
from db.repository import Repository

router = APIRouter()


class SaveStateRequest(BaseModel):
    title: str | None = None
    cards: list[dict[str, Any]]
    messages: list[dict[str, Any]]


@router.get("/sessions")
def list_sessions(repo: Repository = Depends(get_repo)) -> list[dict]:
    return repo.list_canvas_sessions(DEFAULT_CUSTOMER_ID)


@router.post("/sessions")
def create_session(repo: Repository = Depends(get_repo)) -> dict:
    thread_id = str(uuid.uuid4())
    repo.create_canvas_session(thread_id=thread_id, customer_id=DEFAULT_CUSTOMER_ID)
    return {"thread_id": thread_id, "title": None, "cards": [], "messages": []}


@router.get("/sessions/{thread_id}/state")
def get_session_state(thread_id: str, repo: Repository = Depends(get_repo)) -> dict:
    session = repo.get_canvas_session(thread_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.put("/sessions/{thread_id}/state")
def save_session_state(
    thread_id: str,
    body: SaveStateRequest,
    repo: Repository = Depends(get_repo),
) -> dict:
    repo.save_canvas_state(
        thread_id=thread_id,
        title=body.title,
        cards=body.cards,
        messages=body.messages,
    )
    return {"ok": True}


@router.delete("/sessions/{thread_id}")
def delete_session(thread_id: str, repo: Repository = Depends(get_repo)) -> dict:
    repo.delete_canvas_session(thread_id)
    return {"ok": True}
