"""IMAP email reader.

Connects to any IMAP4‑SSL server (Gmail, Outlook, self‑hosted) and fetches
unseen emails.
"""

from __future__ import annotations

import imaplib
import email as email_lib
from email.header import decode_header
from pathlib import Path
from typing import Any

from app.email_reader.base import Email, EmailReader


class IMAPEmailReader(EmailReader):
    """Fetches unseen emails via IMAP over SSL."""

    def __init__(
        self,
        host: str = "imap.gmail.com",
        port: int = 993,
        user: str = "",
        password: str = "",
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._connection: imaplib.IMAP4_SSL | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def name(self) -> str:
        return "imap"

    def fetch_unseen(self) -> list[Email]:
        """Connect (if needed), fetch unseen messages, return as ``Email`` list.

        After fetching, messages are marked as \\Seen so they won't be returned
        again on subsequent poll cycles.
        """
        conn = self._get_connection()
        conn.select("INBOX")

        _ok, data = conn.search(None, "UNSEEN")
        if not data or not data[0]:
            return []

        message_ids: list[bytes] = data[0].split()
        emails: list[Email] = []

        for uid in message_ids:
            _ok, msg_data = conn.fetch(uid, "(RFC822)")
            raw_email = msg_data[0][1] if msg_data and len(msg_data[0]) > 1 else None
            if raw_email is None:
                continue

            parsed = self._parse(raw_email, uid.decode())
            if parsed is not None:
                emails.append(parsed)

        # Mark all fetched messages as \\Seen so they don't reappear
        if message_ids:
            conn.store(b",".join(message_ids), "+FLAGS", "\\Seen")

        return emails

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_connection(self) -> imaplib.IMAP4_SSL:
        if self._connection is None:
            conn = imaplib.IMAP4_SSL(self._host, self._port)
            conn.login(self._user, self._password)
            self._connection = conn
        return self._connection

    def _parse(self, raw: bytes, uid: str) -> Email | None:
        """Parse a raw RFC‑822 message into an ``Email``."""
        try:
            msg = email_lib.message_from_bytes(raw)
        except Exception:
            return None

        subject = self._decode_header(msg.get("Subject", ""))
        from_ = self._decode_header(msg.get("From", ""))
        date = msg.get("Date", "")
        message_id = msg.get("Message-ID", "")

        body = self._get_body(msg)

        return Email(
            id=uid,
            from_=from_,
            subject=subject,
            body=body,
            received_at=date,
            message_id=message_id,
        )

    @staticmethod
    def _decode_header(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            value = value.decode(errors="replace")
        parts: list[str] = []
        for decoded, charset in decode_header(value):
            if isinstance(decoded, bytes):
                try:
                    parts.append(
                        decoded.decode(charset or "utf-8", errors="replace")
                    )
                except (LookupError, UnicodeDecodeError):
                    parts.append(decoded.decode("utf-8", errors="replace"))
            else:
                parts.append(str(decoded))
        return " ".join(parts)

    @staticmethod
    def _get_body(msg: Any) -> str:
        """Extract the plain‑text body from an email message."""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                return payload.decode(errors="replace")
        return ""
