"""Read-only SQLite URI connection management for Farmacia Lumen."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from typing import Any

from .config import settings


def get_ro_connection() -> sqlite3.Connection:
    """Open farmacia.db strictly in read-only URI mode with analytical pragmas."""
    db_path = settings.db_path
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found at {db_path}")

    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA cache_size = -64000")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA mmap_size = 268435456")
    conn.execute("PRAGMA query_only = ON")
    return conn


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency yielding a read-only SQLite connection."""
    conn = get_ro_connection()
    try:
        yield conn
    finally:
        conn.close()


def query_all(
    conn: sqlite3.Connection, sql: str, params: dict[str, Any] | tuple[Any, ...] = ()
) -> list[sqlite3.Row]:
    return conn.execute(sql, params).fetchall()


def query_one(
    conn: sqlite3.Connection, sql: str, params: dict[str, Any] | tuple[Any, ...] = ()
) -> sqlite3.Row | None:
    return conn.execute(sql, params).fetchone()
