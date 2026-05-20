"""Shared dependencies for backend routes."""
from __future__ import annotations

import os
from functools import lru_cache

from agents.graph import build_graph
from db.connection import get_db
from db.repository import Repository

DEFAULT_CUSTOMER_ID = os.environ.get("DEFAULT_CUSTOMER_ID", "demo-001")


@lru_cache(maxsize=1)
def get_repo() -> Repository:
    return Repository(get_db())


@lru_cache(maxsize=1)
def get_graph():
    return build_graph(get_repo())
