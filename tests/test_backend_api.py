"""Smoke tests for the FastAPI backend endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_customer(client: TestClient) -> None:
    r = client.get("/api/customer")
    assert r.status_code == 200
    body = r.json()
    assert body["customer"]["id"] == "demo-001"
    assert body["balance"] is not None


def test_session_create_and_save(client: TestClient) -> None:
    r = client.post("/api/sessions")
    assert r.status_code == 200
    tid = r.json()["thread_id"]

    # New session shows up in the list
    listed = client.get("/api/sessions").json()
    assert any(s["thread_id"] == tid for s in listed)

    # Save state and read it back
    body = {
        "title": "Test canvas",
        "cards": [{"card": {"id": "x", "card_type": "balance_view"}, "layout": {"i": "x", "x": 0, "y": 0, "w": 4, "h": 6}}],
        "messages": [{"role": "user", "content": "hi"}],
    }
    save = client.put(f"/api/sessions/{tid}/state", json=body)
    assert save.status_code == 200

    state = client.get(f"/api/sessions/{tid}/state").json()
    assert state["title"] == "Test canvas"
    assert len(state["cards"]) == 1
    assert state["messages"][0]["content"] == "hi"

    # Cleanup
    client.delete(f"/api/sessions/{tid}")
