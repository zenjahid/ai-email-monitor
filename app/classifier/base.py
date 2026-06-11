"""Abstract interface for email classifiers.

Every classifier produces a :class:`ClassificationResult` with a structured
decision (important, priority, category, reason).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from app.email_reader.base import Email

# ---------------------------------------------------------------------------
# Structured output
# ---------------------------------------------------------------------------

Priority = Literal["HIGH", "MEDIUM", "LOW"]
Category = Literal[
    "SERVER_DOWN",
    "PAYMENT_ISSUE",
    "CLIENT_COMPLAINT",
    "SECURITY_ALERT",
    "BILLING",
    "URGENT_REQUEST",
    "NEWSLETTER",
    "SPAM",
    "PROMOTION",
    "AUTOMATED",
    "GENERAL",
    "SCHEDULED_MAINTENANCE",
    "CI_FAILURE",
    "BUDGET_ALERT",
    "MEETING",
    "FRAUD_ALERT",
    "SUBSCRIPTION",
]


@dataclass
class ClassificationResult:
    """The structured decision produced by the AI classifier."""

    important: bool
    priority: Priority
    category: Category
    reason: str  # Human‑readable justification


# ---------------------------------------------------------------------------
# Abstract classifier
# ---------------------------------------------------------------------------


class Classifier(ABC):
    """Base class for all classifiers."""

    @abstractmethod
    def classify(self, email: Email) -> ClassificationResult:
        """Analyse an email and return a structured decision."""
        ...

    @abstractmethod
    def name(self) -> str:
        """Human‑readable identifier (e.g. ``"rule_based"``, ``"openai"``)."""
        ...
