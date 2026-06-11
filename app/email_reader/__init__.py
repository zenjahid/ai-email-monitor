"""Email reader package.

Provides a factory (:func:`get_email_reader`) to instantiate the correct reader
based on configuration.
"""

from __future__ import annotations

from app.email_reader.base import Email, EmailReader
from app.email_reader.mock import MockEmailReader
from app.email_reader.imap import IMAPEmailReader


def get_email_reader(
    source: str,
    *,
    imap_host: str = "imap.gmail.com",
    imap_port: int = 993,
    imap_user: str = "",
    imap_pass: str = "",
) -> EmailReader:
    """Return the appropriate :class:`EmailReader` for *source*.

    Parameters
    ----------
    source:
        One of ``"mock"`` or ``"imap"``.
    imap_host, imap_port, imap_user, imap_pass:
        IMAP connection details (used when *source* is ``"imap"``).
    """
    if source == "mock":
        return MockEmailReader()
    elif source == "imap":
        return IMAPEmailReader(
            host=imap_host,
            port=imap_port,
            user=imap_user,
            password=imap_pass,
        )
    else:
        raise ValueError(f"Unknown email source: {source!r}. Expected 'mock' or 'imap'.")



__all__ = [
    "Email",
    "EmailReader",
    "get_email_reader",
]
