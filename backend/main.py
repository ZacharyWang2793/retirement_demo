"""FastAPI entry point for the canvas backend.

Wraps the existing LangGraph (agents/) and repository (db/) as a JSON+SSE API
consumed by the Next.js frontend in frontend/.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import cards, chat, customer, sessions

app = FastAPI(title="Meridian Retirement Canvas API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(cards.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(customer.router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
