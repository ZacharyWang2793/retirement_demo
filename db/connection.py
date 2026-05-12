"""SQLite connection management. Schema is applied on first connect."""
from __future__ import annotations

import os
import sqlite3
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.environ.get("RETIREMENT_DB_PATH", "data/retirement.db")
SCHEMA_PATH = Path(__file__).parent.parent / "data" / "schema.sql"


def _apply_schema(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()


@lru_cache(maxsize=1)
def get_db() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _apply_schema(conn)
    return conn


def reset_db() -> None:
    """Drop the cached connection and delete the file. Used by seed script and tests."""
    get_db.cache_clear()
    if Path(DB_PATH).exists():
        Path(DB_PATH).unlink()
