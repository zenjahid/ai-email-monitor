"""Abstract interface for email readers.

Every email source (mock, IMAP) implements this interface so the
classifier and scheduler can remain source‑agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Email:
    """Normalised email model used throughout the application."""

    id: str  # Unique identifier for deduplication
    from_: str = field(metadata={"help": "Sender address"})
    subject: str = ""
    body: str = ""
    received_at: str = ""  # ISO‑8601 timestamp

    # Optional metadata carried from source
    message_id: str = ""


class EmailReader(ABC):
    """Base class for email readers."""

    @abstractmethod
    def fetch_unseen(self) -> list[Email]:
        """Fetch new (unseen) emails.

        Returns a list of :class:`Email` objects. After a successful fetch the
        reader should mark those emails as seen / processed so they are not
        returned again on the next call.

        If no new emails are available return an empty list.
        """
        ...

    @abstractmethod
    def name(self) -> str:
        """Human‑readable identifier for the source (e.g. ``"mock"``)."""
        ...
