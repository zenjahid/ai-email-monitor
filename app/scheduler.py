"""Background scheduler that polls the email source and classifies new emails.

Runs in a daemon thread alongside the Flask server.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.classifier import Classifier, get_classifier, RuleBasedClassifier
from app.email_reader import EmailReader, get_email_reader
from app.models.database import get_connection
from app.models.repository import (
    get_settings,
    is_processed,
    log_activity,
    mark_processed,
    update_setting,
)

logger = logging.getLogger(__name__)


def _build_reader(settings: dict[str, str]) -> EmailReader:
    """Construct an :class:`EmailReader` from settings dict."""
    return get_email_reader(
        source=settings.get("email_source", "mock"),
        imap_host=settings.get("imap_host", "imap.gmail.com"),
        imap_port=int(settings.get("imap_port", "993")),
        imap_user=settings.get("imap_user", ""),
        imap_pass=settings.get("imap_pass", ""),
    )


def _build_classifier(settings: dict[str, str]) -> Classifier:
    """Construct a :class:`Classifier` from settings dict."""
    provider = settings.get("provider", "rule_based")

    # Map settings keys to classifier parameters
    openai_key = settings.get("openai_api_key", "")
    openai_model = settings.get("openai_model", "gpt-4o-mini")

    compat_url = settings.get("openai_compat_base_url", "")
    compat_key = settings.get("openai_compat_api_key", "")
    compat_model = settings.get("openai_compat_model", "")

    ollama_url = settings.get("ollama_base_url", "")
    ollama_model = settings.get("ollama_model", "llama3.2")

    return get_classifier(
        provider,
        openai_api_key=openai_key,
        openai_model=openai_model,
        openai_compat_base_url=compat_url,
        openai_compat_api_key=compat_key,
        openai_compat_model=compat_model,
        ollama_base_url=ollama_url,
        ollama_model=ollama_model,
    )


def _safe_classify(classifier: Classifier, email: Any) -> Any:
    """Safely classify an email, falling back to rule-based on any error."""
    try:
        return classifier.classify(email)
    except Exception as exc:
        logger.error("Classification error for email %s: %s", email.id, exc)
        return RuleBasedClassifier().classify(email)


def _poll(db_path: str) -> int:
    """Run one poll cycle. Returns the number of new emails processed."""
    conn = get_connection(db_path)
    settings = get_settings(conn)

    reader = _build_reader(settings)
    classifier = _build_classifier(settings)

    emails = reader.fetch_unseen()
    count = 0

    for email in emails:
        if is_processed(conn, email.id):
            continue

        result = _safe_classify(classifier, email)

        mark_processed(
            conn,
            email_id=email.id,
            important=result.important,
            priority=result.priority,
            category=result.category,
            reason=result.reason,
            message_id=email.message_id,
            sender=email.from_,
            subject=email.subject,
            body=email.body,
            received_at=email.received_at,
        )
        count += 1

        level = "IMPORTANT" if result.important else "IGNORED"
        logger.info(
            "[%s] %s | %s | %s | %s",
            level,
            email.id,
            email.subject[:60],
            result.priority,
            result.reason,
        )

        # Log to activity timeline
        try:
            log_activity(
                conn,
                "classified",
                f"{email.id} → {result.category} ({level}) — {result.reason}",
            )
        except Exception:
            pass

    if count:
        try:
            log_activity(conn, "poll", f"Processed {count} new email(s)")
        except Exception:
            pass

    # Don't close the connection — it's cached in thread-local storage
    # and will be reused on the next poll cycle.
    return count


def run_poll_loop(db_path: str, interval: int = 120) -> None:
    """Continuously poll the email source.

    The poll interval is read from the database settings on every cycle,
    so changes made via the dashboard Settings page take effect immediately
    (no restart needed).
    """
    logger.info("Scheduler started (default poll interval=%ss, db=%s)", interval, db_path)

    # Log scheduler start
    try:
        conn = get_connection(db_path)
        log_activity(conn, "scheduler", f"Scheduler started (interval={interval}s)")
    except Exception:
        pass

    while True:
        try:
            processed = _poll(db_path)
            if processed:
                logger.info("Poll cycle complete — processed %d new emails", processed)
        except Exception as exc:
            logger.error("Poll cycle failed: %s", exc)
            try:
                conn = get_connection(db_path)
                log_activity(conn, "error", f"Poll cycle failed: {exc}")
            except Exception:
                pass

        # Read the latest poll interval from DB settings each cycle
        try:
            conn = get_connection(db_path)
            row = conn.execute(
                "SELECT value FROM settings WHERE key = 'poll_interval'"
            ).fetchone()
            if row:
                interval = max(10, int(row["value"]))
        except Exception:
            pass  # fall back to previous interval value

        logger.debug("Next poll in %ds", interval)
        time.sleep(interval)
