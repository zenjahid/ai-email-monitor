"""Data-access layer for processed emails and application settings.

All functions accept an explicit ``sqlite3.Connection`` so callers can control
transaction boundaries.
"""

from __future__ import annotations

import sqlite3
from typing import Any


# ---------------------------------------------------------------------------
# Processed emails (duplicate prevention)
# ---------------------------------------------------------------------------

def mark_processed(
    conn: sqlite3.Connection,
    email_id: str,
    important: bool,
    priority: str,
    category: str,
    reason: str,
    *,
    message_id: str = "",
    sender: str = "",
    subject: str = "",
    body: str = "",
    received_at: str = "",
) -> None:
    """Insert a processed email record (or ignore if already present)."""
    conn.execute(
        """
        INSERT OR IGNORE INTO processed_emails
            (email_id, message_id, important, priority, category, reason,
             sender, subject, body, received_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (email_id, message_id, int(important), priority, category, reason,
         sender, subject, body, received_at),
    )
    conn.commit()


def is_processed(conn: sqlite3.Connection, email_id: str) -> bool:
    """Return ``True`` if *email_id* has already been processed."""
    row = conn.execute(
        "SELECT 1 FROM processed_emails WHERE email_id = ?", (email_id,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Notifications (important emails)
# ---------------------------------------------------------------------------


def get_notifications(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all important emails, newest first, as a list of dicts."""
    rows = conn.execute(
        """
        SELECT email_id, sender, subject, priority, category, reason,
               received_at, processed_at
        FROM processed_emails
        WHERE important = 1
        ORDER BY processed_at DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_emails(
    conn: sqlite3.Connection,
    filter_by: str = "all",
) -> list[dict[str, Any]]:
    """Return processed emails with an optional filter.

    Parameters
    ----------
    filter_by:
        ``"all"`` (default), ``"important"``, or ``"ignored"``.
    """
    if filter_by == "important":
        where = "WHERE important = 1"
    elif filter_by == "ignored":
        where = "WHERE important = 0"
    else:
        where = ""

    rows = conn.execute(
        f"""
        SELECT email_id, sender, subject, priority, category, reason,
               important, received_at, processed_at
        FROM processed_emails
        {where}
        ORDER BY processed_at DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_stats(conn: sqlite3.Connection, available: int = 0) -> dict[str, int]:
    """Return aggregate counts for the dashboard footer.

    Parameters
    ----------
    available:
        Total emails in dataset (mock). Pass **-1** for IMAP to indicate
        the count is unknowable; ``remaining`` will be ``-1``.
    """
    total = conn.execute("SELECT COUNT(*) FROM processed_emails").fetchone()[0]
    important = conn.execute(
        "SELECT COUNT(*) FROM processed_emails WHERE important = 1"
    ).fetchone()[0]
    ignored = total - important
    remaining = max(0, available - total) if available > 0 else -1
    return {
        "total": total,
        "important": important,
        "ignored": ignored,
        "available": available if available > 0 else 0,
        "remaining": remaining,
    }

def clear_all_processed(conn: sqlite3.Connection) -> int:
    """Delete ALL processed email records. Returns the number of rows deleted."""
    count = conn.execute("SELECT COUNT(*) FROM processed_emails").fetchone()[0]
    conn.execute("DELETE FROM processed_emails")
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Activity log
# ---------------------------------------------------------------------------


def log_activity(
    conn: sqlite3.Connection,
    event: str,
    detail: str = "",
) -> None:
    """Insert a new activity log entry."""
    conn.execute(
        "INSERT INTO activity_log (event, detail) VALUES (?, ?)",
        (event, detail),
    )
    conn.commit()


def get_activity_log(
    conn: sqlite3.Connection,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return the most recent activity log entries (newest first)."""
    rows = conn.execute(
        """
        SELECT id, event, detail, created_at
        FROM activity_log
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def clear_activity_log(conn: sqlite3.Connection) -> int:
    """Delete all activity log entries. Returns row count deleted."""
    count = conn.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
    conn.execute("DELETE FROM activity_log")
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Settings (key‑value store)
# ---------------------------------------------------------------------------

def get_settings(conn: sqlite3.Connection) -> dict[str, str]:
    """Return all settings as a plain dict."""
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def update_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Insert or update a single setting."""
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()
