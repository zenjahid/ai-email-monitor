"""Flask routes for the dashboard UI and settings page.
"""

from __future__ import annotations

import json as json_module
import logging
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

from app.email_reader.mock import MockEmailReader
from app.models.database import get_connection, init_db
from app.models.repository import (
    clear_all_processed,
    clear_activity_log,
    get_activity_log,
    get_emails,
    get_notifications,
    get_settings,
    get_stats,
    is_processed,
    log_activity,
    update_setting,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    template_folder="templates",
    static_folder="static",
)


def _get_db_path() -> str:
    """Resolve the database path from the Flask app config."""
    from flask import current_app
    return current_app.config.get("DATABASE_PATH", "data/emails.db")


def _get_mock_json() -> str:
    """Return the contents of mock_emails.json as a pretty-printed string."""
    path = Path("data/mock_emails.json")
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "[]"


def _get_mock_parsed() -> list[dict]:
    """Return the mock emails as a list of dicts for template rendering."""
    path = Path("data/mock_emails.json")
    if path.exists():
        try:
            data = json_module.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json_module.JSONDecodeError, OSError):
            pass
    return []


def _get_available_count() -> int:
    """Return the total number of emails available.

    If ``data/mock_emails.json`` exists, returns its length (the number of
    mock emails).  If the file does **not** exist AND the configured email
    source is IMAP, returns **-1** to signal that the count is unknowable.
    Otherwise returns 0.
    """
    mock_path = Path("data/mock_emails.json")
    if mock_path.exists():
        try:
            data = json_module.loads(mock_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return len(data)
        except (json_module.JSONDecodeError, OSError):
            pass
        return 0

    # No mock file → check if source is IMAP
    try:
        db_path = _get_db_path()
        conn = get_connection(db_path)
        source = conn.execute(
            "SELECT value FROM settings WHERE key = 'email_source'"
        ).fetchone()
        if source and source["value"] != "mock":
            return -1
    except Exception:
        pass

    return 0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@dashboard_bp.route("/")
def index():
    """Render the main dashboard page."""
    return render_template("index.html")


@dashboard_bp.route("/api/notifications")
def api_notifications():
    """JSON endpoint that returns all important notifications (newest first)."""
    db_path = _get_db_path()
    conn = get_connection(db_path)
    notifications = get_notifications(conn)
    return jsonify(notifications)


@dashboard_bp.route("/api/emails")
def api_emails():
    """JSON endpoint returning processed emails with optional filter.

    Query parameters
    ----------------
    filter : str, optional
        One of ``"all"`` (default), ``"important"``, or ``"ignored"``.
    """
    db_path = _get_db_path()
    conn = get_connection(db_path)
    filter_by = request.args.get("filter", "all")
    if filter_by not in ("all", "important", "ignored"):
        filter_by = "all"
    emails = get_emails(conn, filter_by=filter_by)
    return jsonify(emails)


@dashboard_bp.route("/api/stats")
def api_stats():
    """JSON endpoint returning aggregate counts."""
    db_path = _get_db_path()
    conn = get_connection(db_path)
    available = _get_available_count()
    stats = get_stats(conn, available=available)
    return jsonify(stats)


@dashboard_bp.route("/settings", methods=["GET"])
def settings_page():
    """Render the settings page."""
    db_path = _get_db_path()
    conn = get_connection(db_path)
    settings = get_settings(conn)
    mock_json = _get_mock_json()
    mock_emails = _get_mock_parsed()
    return render_template("settings.html", settings=settings, mock_json=mock_json, mock_emails=mock_emails)


@dashboard_bp.route("/api/settings", methods=["GET"])
def api_settings_get():
    """JSON endpoint returning current settings."""
    db_path = _get_db_path()
    conn = get_connection(db_path)
    return jsonify(get_settings(conn))


@dashboard_bp.route("/api/settings", methods=["POST"])
def api_settings_save():
    """Save settings from JSON body."""
    db_path = _get_db_path()
    conn = get_connection(db_path)
    data = request.get_json(silent=True) or {}

    saved = []
    for key, value in data.items():
        # Only allow known setting keys
        if key in (
            "email_source", "provider", "poll_interval",
            "imap_host", "imap_port", "imap_user", "imap_pass",
            "openai_api_key", "openai_model",
            "openai_compat_base_url", "openai_compat_api_key", "openai_compat_model",
            "ollama_base_url", "ollama_model",
        ):
            update_setting(conn, key, str(value))
            saved.append(key)

    logger.info("Settings updated: %s", ", ".join(saved))
    return jsonify({"status": "ok", "updated": saved})


@dashboard_bp.route("/api/mock-data/delete", methods=["POST"])
def api_mock_data_delete():
    """Delete a single email from the mock dataset by its email_id."""
    data = request.get_json(silent=True) or {}
    email_id = data.get("email_id", "")

    if not email_id:
        return jsonify({"status": "error", "error": "No email_id provided"}), 400

    path = Path("data/mock_emails.json")
    try:
        if not path.exists():
            return jsonify({"status": "error", "error": "Mock data file not found"}), 404

        raw = path.read_text(encoding="utf-8")
        parsed = json_module.loads(raw)

        if not isinstance(parsed, list):
            return jsonify({"status": "error", "error": "Invalid mock data format"}), 500

        before = len(parsed)
        parsed = [item for item in parsed if item.get("id") != email_id]
        after = len(parsed)

        if before == after:
            return jsonify({"status": "error", "error": f"Email {email_id} not found"}), 404

        path.write_text(
            json_module.dumps(parsed, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Reload the mock reader
        MockEmailReader._global_reload()

        logger.info("Mock email %s deleted (%d remaining)", email_id, after)
        return jsonify({"status": "ok", "count": after})

    except (OSError, json_module.JSONDecodeError) as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500


@dashboard_bp.route("/api/mock-data", methods=["POST"])
def api_mock_data_save():
    """Save the mock email data to disk and reload the reader."""
    data = request.get_json(silent=True) or {}
    raw = data.get("data", "")

    if not raw:
        return jsonify({"status": "error", "error": "No data provided"}), 400

    # Validate JSON before writing
    try:
        parsed = json_module.loads(raw)
    except json_module.JSONDecodeError as exc:
        return jsonify({"status": "error", "error": f"Invalid JSON: {exc}"}), 400

    # Ensure it's a list
    if not isinstance(parsed, list):
        return jsonify({"status": "error", "error": "JSON must be an array of email objects"}), 400

    path = Path("data/mock_emails.json")
    path.write_text(
        json_module.dumps(parsed, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Reload the mock reader so next poll uses the updated data
    MockEmailReader._global_reload()

    logger.info("Mock data updated (%d emails)", len(parsed))
    return jsonify({"status": "ok", "count": len(parsed)})


@dashboard_bp.route("/api/mock-data/clear", methods=["POST"])
def api_mock_data_clear():
    """Delete ALL processed email records from the database."""
    db_path = _get_db_path()
    conn = get_connection(db_path)
    try:
        count = clear_all_processed(conn)
        logger.info("All processed data cleared (%d rows deleted)", count)
        return jsonify({"status": "ok", "deleted": count})
    except Exception as exc:
        logger.error("Failed to clear processed data: %s", exc)
        return jsonify({"status": "error", "error": str(exc)}), 500


@dashboard_bp.route("/api/imap/test", methods=["POST"])
def api_imap_test():
    """Test IMAP connection with provided credentials.

    Accepts JSON body with fields: imap_host, imap_port, imap_user, imap_pass.
    Returns success/failure after attempting an IMAP over SSL login.
    """
    data = request.get_json(silent=True) or {}
    host = (data.get("imap_host") or "").strip()
    port_str = (data.get("imap_port") or "993").strip()
    user = (data.get("imap_user") or "").strip()
    password = data.get("imap_pass") or ""

    if not all([host, port_str, user, password]):
        return jsonify({
            "status": "error",
            "error": "All IMAP fields (host, port, username, password) are required"
        }), 400

    try:
        port = int(port_str)
    except ValueError:
        return jsonify({"status": "error", "error": "Port must be a valid number"}), 400

    try:
        import imaplib
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(user, password)
        conn.logout()
        logger.info("IMAP test connection successful to %s:%d as %s", host, port, user)
        return jsonify({"status": "ok", "message": "IMAP connection successful!"})
    except imaplib.IMAP4.error as exc:
        logger.warning("IMAP test login failed for %s:%d: %s", host, port, exc)
        return jsonify({"status": "error", "error": f"IMAP login failed: {exc}"}), 400
    except Exception as exc:
        logger.warning("IMAP test connection error for %s:%d: %s", host, port, exc)
        return jsonify({"status": "error", "error": f"Connection failed: {exc}"}), 400


@dashboard_bp.route("/api/emails/unprocessed")
def api_emails_unprocessed():
    """Return mock emails that have NOT yet been processed.

    Reads ``mock_emails.json`` and filters out any ``email_id`` already
    present in the ``processed_emails`` table.
    """
    mock_emails = _get_mock_parsed()
    if not mock_emails:
        return jsonify([])

    db_path = _get_db_path()
    conn = get_connection(db_path)

    unprocessed = []
    for item in mock_emails:
        email_id = item.get("id", "")
        if email_id and not is_processed(conn, email_id):
            unprocessed.append(item)

    return jsonify(unprocessed)


@dashboard_bp.route("/api/processed/delete", methods=["POST"])
def api_processed_delete():
    """Delete a single processed email by ``email_id``."""
    data = request.get_json(silent=True) or {}
    email_id = data.get("email_id", "")

    if not email_id:
        return jsonify({"status": "error", "error": "No email_id provided"}), 400

    db_path = _get_db_path()
    conn = get_connection(db_path)
    conn.execute("DELETE FROM processed_emails WHERE email_id = ?", (email_id,))
    conn.commit()

    logger.info("Processed email %s deleted from database", email_id)
    return jsonify({"status": "ok"})


@dashboard_bp.route("/api/mock-data/delete-unprocessed", methods=["POST"])
def api_mock_data_delete_unprocessed():
    """Delete ALL unprocessed mock emails from the mock dataset.

    Removes every email whose ``id`` is NOT yet in the ``processed_emails``
    table.  Also reloads the mock reader so the change takes effect immediately.
    """
    mock_emails = _get_mock_parsed()
    if not mock_emails:
        return jsonify({"status": "ok", "deleted": 0})

    db_path = _get_db_path()
    conn = get_connection(db_path)

    kept = []
    deleted_count = 0
    for item in mock_emails:
        email_id = item.get("id", "")
        if email_id and not is_processed(conn, email_id):
            deleted_count += 1
        else:
            kept.append(item)

    path = Path("data/mock_emails.json")
    path.write_text(
        json_module.dumps(kept, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    MockEmailReader._global_reload()
    logger.info("Deleted %d unprocessed mock emails (%d remaining)", deleted_count, len(kept))
    return jsonify({"status": "ok", "deleted": deleted_count})


@dashboard_bp.route("/api/activity")
def api_activity():
    """Return recent activity log entries."""
    db_path = _get_db_path()
    conn = get_connection(db_path)
    limit_str = request.args.get("limit", "50")
    try:
        limit = int(limit_str)
    except ValueError:
        limit = 50
    entries = get_activity_log(conn, limit=limit)
    return jsonify(entries)


@dashboard_bp.route("/api/activity/clear", methods=["POST"])
def api_activity_clear():
    """Clear all activity log entries."""
    db_path = _get_db_path()
    conn = get_connection(db_path)
    try:
        count = clear_activity_log(conn)
        return jsonify({"status": "ok", "deleted": count})
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500


@dashboard_bp.route("/api/health")
def api_health():
    """Simple health check."""
    return jsonify({"status": "ok"})
