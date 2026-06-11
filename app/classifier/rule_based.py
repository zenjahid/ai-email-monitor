"""Rule-based email classifier using keyword and pattern matching.

This is the **minimum acceptable** AI approach per the spec. It serves as both
a standalone classifier and a fallback when an API-based classifier fails.
"""

from __future__ import annotations

import re
from typing import Pattern

from app.classifier.base import (
    Category,
    ClassificationResult,
    Classifier,
    Priority,
)
from app.email_reader.base import Email


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

RulePriority = tuple[str, Priority, Category, str]  # (label, priority, category, reason)


RULES: list[tuple[Pattern[str], RulePriority]] = [
    # -- HIGH priority rules --
    (
        re.compile(r"\b(server\s*down|outage|production\s*down|database\s*connection.*exhaust|connection.*pool|pool.*full)\b", re.IGNORECASE),
        ("server_down", "HIGH", "SERVER_DOWN", "Urgent server/outage mention detected"),
    ),
    (
        re.compile(r"\b(payment\s*fail(?:ed|ure)?|payment\s*declined|billing\s*issue|invoice.*overdue|payment\s*gateway.*down|checkout.*not\s*working|losing\s*sales)\b", re.IGNORECASE),
        ("payment_fail", "HIGH", "PAYMENT_ISSUE", "Payment failure or billing issue detected"),
    ),
    (
        re.compile(r"\b(ddos|security\s*breach|unauthorized\s*transactions?|fraud\s*alert)\b", re.IGNORECASE),
        ("security", "HIGH", "SECURITY_ALERT", "Security alert detected"),
    ),
    (
        re.compile(r"\b(urgent|asap|critical|immediate\s*action)\b", re.IGNORECASE),
        ("urgent", "HIGH", "URGENT_REQUEST", "Urgent/critical language detected"),
    ),
    (
        re.compile(r"\b(unauthorized\s*transaction|account.*compromised|frozen)\b", re.IGNORECASE),
        ("fraud", "HIGH", "FRAUD_ALERT", "Potential fraud or account compromise detected"),
    ),
    # -- MEDIUM priority rules --
    (
        re.compile(r"\b(complaint|unhappy|discrepancy|refund)\b", re.IGNORECASE),
        ("complaint", "MEDIUM", "CLIENT_COMPLAINT", "Client complaint or issue detected"),
    ),
    (
        re.compile(r"\b(budget\s*alert|budget.*exceed|overage|overspend)\b", re.IGNORECASE),
        ("budget", "MEDIUM", "BUDGET_ALERT", "Budget or cost alert detected"),
    ),
    (
        re.compile(r"\b(ci\s*fail(?:ed|ure)?|pipeline.*fail(?:ed|ure)?|build.*fail(?:ed|ure)?|integration.*test.*fail(?:ed|ure)?)\b", re.IGNORECASE),
        ("ci_fail", "MEDIUM", "CI_FAILURE", "CI/CD pipeline failure detected"),
    ),
    (
        re.compile(r"\b(scheduled\s*maint|maintenance.*window)\b", re.IGNORECASE),
        ("maintenance", "LOW", "SCHEDULED_MAINTENANCE", "Scheduled maintenance notification"),
    ),
    # -- NON-IMPORTANT rules --
    (
        re.compile(r"\b(newsletter|unsubscribe|weekly\s*digest|read\s*more)\b", re.IGNORECASE),
        ("newsletter", "LOW", "NEWSLETTER", "Automated newsletter or subscription email"),
    ),
    (
        re.compile(r"\b(buy\s*one\s*get\s*one|flash\s*sale|hot\s*deal|70%\s*off|claim.*prize|won.*million)\b", re.IGNORECASE),
        ("spam_promo", "LOW", "SPAM", "Spam, phishing, or promotional content detected"),
    ),
    (
        re.compile(r"\b(order.*shipped|your\s*order|track\s*your\s*package)\b", re.IGNORECASE),
        ("order", "LOW", "AUTOMATED", "Automated order/shipping notification"),
    ),
    (
        re.compile(r"\b(connection\s*request|linkedin|connection.*invite)\b", re.IGNORECASE),
        ("social", "LOW", "GENERAL", "Social network connection request"),
    ),
    (
        re.compile(r"\b(renewed|subscription.*renew|next billing)\b", re.IGNORECASE),
        ("subscription", "LOW", "SUBSCRIPTION", "Automated subscription renewal notice"),
    ),
]


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class RuleBasedClassifier(Classifier):
    """Classifies emails by matching subject and body against keyword patterns."""

    def name(self) -> str:
        return "rule_based"

    def classify(self, email: Email) -> ClassificationResult:
        text = f"{email.subject} {email.body}".lower()

        for pattern, (label, priority, category, reason) in RULES:
            if pattern.search(text):
                return ClassificationResult(
                    important=priority in ("HIGH", "MEDIUM"),
                    priority=priority,
                    category=category,
                    reason=reason,
                )

        # Default: not important
        return ClassificationResult(
            important=False,
            priority="LOW",
            category="GENERAL",
            reason="No importance indicators found in email content",
        )
