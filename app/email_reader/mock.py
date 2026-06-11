"""Mock email reader that serves emails from a local JSON file.

Useful for development, testing, and demonstration without connecting to a
real email server.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.email_reader.base import Email, EmailReader


class MockEmailReader(EmailReader):
    """Reads emails from a JSON file on disk.

    Each call to :meth:`fetch_unseen` yields one batch of emails. Once every
    email has been returned the reader starts returning the list again from the
    beginning, simulating new incoming messages on subsequent poll cycles.
    """

    # Class-level flag to signal all instances to reload
    _reload_requested: bool = False

    def __init__(self, data_path: str | Path = "data/mock_emails.json") -> None:
        self._data_path = Path(data_path)
        self._emails: list[Email] = []
        self._cursor: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def _global_reload(cls) -> None:
        """Signal all instances to re-read the JSON file on next fetch."""
        cls._reload_requested = True

    def name(self) -> str:
        return "mock"

    def fetch_unseen(self) -> list[Email]:
        """Return ALL unseen emails at once and advance the cursor past them.

        On the first call (or after a wrap-around) this returns the entire
        dataset so every email gets classified in a single poll cycle. Once
        every email has been returned the cursor resets so the next poll will
        re-process everything, simulating a fresh batch.
        """
        # If a global reload was requested, re-read the file
        if self.__class__._reload_requested:
            self._reload()
            self.__class__._reload_requested = False

        if not self._emails:
            self._load()

        if self._cursor >= len(self._emails):
            self._cursor = 0  # wrap around

        # Return ALL remaining emails, not just a small batch
        batch = self._emails[self._cursor:]
        self._cursor = len(self._emails)  # advance past the end
        return batch

    def _reload(self) -> None:
        """Re-read the JSON file from disk and reset the cursor.

        Useful when the mock data file has been updated via the settings page.
        """
        self._emails.clear()
        self._cursor = 0
        self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Parse the JSON data file into ``Email`` objects."""
        raw: list[dict[str, Any]] = json.loads(
            self._data_path.read_text(encoding="utf-8")
        )
        self._emails = [self._parse(item) for item in raw]

    @staticmethod
    def _parse(item: dict[str, Any]) -> Email:
        return Email(
            id=item["id"],
            from_=item.get("from", ""),
            subject=item.get("subject", ""),
            body=item.get("body", ""),
            received_at=item.get("received_at", ""),
            message_id=item.get("id", ""),
        )
