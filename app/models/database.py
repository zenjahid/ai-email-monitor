"""SQLite database initialisation and connection management.

Provides a thread-safe connection factory and schema creation.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS processed_emails (
    email_id     TEXT PRIMARY KEY,
    message_id   TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    important    INTEGER NOT NULL DEFAULT 0,
    priority     TEXT    NOT NULL DEFAULT 'LOW',
    category     TEXT    NOT NULL DEFAULT 'GENERAL',
    reason       TEXT    NOT NULL DEFAULT '',
    sender       TEXT,
    subject      TEXT,
    body         TEXT,
    received_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    event     TEXT    NOT NULL,
    detail    TEXT    NOT NULL DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default settings (inserted only if they don't exist)
INSERT OR IGNORE INTO settings (key, value) VALUES ('email_source', 'mock');
INSERT OR IGNORE INTO settings (key, value) VALUES ('provider', 'rule_based');
INSERT OR IGNORE INTO settings (key, value) VALUES ('poll_interval', '120');
INSERT OR IGNORE INTO settings (key, value) VALUES ('imap_host', 'imap.gmail.com');
INSERT OR IGNORE INTO settings (key, value) VALUES ('imap_port', '993');
INSERT OR IGNORE INTO settings (key, value) VALUES ('imap_user', '');
INSERT OR IGNORE INTO settings (key, value) VALUES ('imap_pass', '');
INSERT OR IGNORE INTO settings (key, value) VALUES ('openai_api_key', '');
INSERT OR IGNORE INTO settings (key, value) VALUES ('openai_model', 'gpt-4o-mini');
INSERT OR IGNORE INTO settings (key, value) VALUES ('openai_compat_base_url', 'https://openrouter.ai/api/v1');
INSERT OR IGNORE INTO settings (key, value) VALUES ('openai_compat_api_key', '');
INSERT OR IGNORE INTO settings (key, value) VALUES ('openai_compat_model', 'anthropic/claude-3-haiku');
INSERT OR IGNORE INTO settings (key, value) VALUES ('ollama_base_url', 'http://host.docker.internal:11434');
INSERT OR IGNORE INTO settings (key, value) VALUES ('ollama_model', 'llama3.2');
"""


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

_local = threading.local()


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """Return a thread-local SQLite connection.

    Each thread gets its own connection so we stay safe in a multi‑threaded
    Flask + scheduler environment.
    """
    path = str(db_path)

    # Try to reuse an existing connection for this thread
    conn: sqlite3.Connection | None = getattr(_local, "conn", None)
    if conn is not None:
        # If the cached connection was closed, discard it
        try:
            conn.execute("SELECT 1")
            return conn
        except sqlite3.ProgrammingError:
            _local.conn = None

    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    _local.conn = conn
    return conn


def close_connection() -> None:
    """Close and remove the thread-local connection."""
    conn: sqlite3.Connection | None = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


def init_db(db_path: str | Path) -> None:
    """Create database tables and insert default settings."""
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def with_db(db_path: str | Path) -> Callable:
    """Decorator factory that injects a DB connection into the wrapped function.

    Usage::

        @with_db("/data/emails.db")
        def my_func(conn, arg1, arg2):
            ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> object:
            conn = get_connection(db_path)
            return func(conn, *args, **kwargs)
        return wrapper
    return decorator
