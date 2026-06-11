"""API-based email classifier using LLMs.

Supports three provider modes:
- ``openai`` — official OpenAI API
- ``openai_compat`` — any OpenAI-compatible endpoint (OpenRouter, Groq, Together AI, etc.)
- ``local`` — Ollama (or any local OpenAI-compatible server)

All three use the `openai` Python client under the hood, differing only in
``base_url`` and ``api_key``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from app.classifier.base import (
    Category,
    ClassificationResult,
    Classifier,
    Priority,
)
from app.classifier.rule_based import RuleBasedClassifier
from app.email_reader.base import Email

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an email classification assistant. Your job is to analyse the subject and body of an email and determine:

1. **important** (boolean) — Is this email important and action-required? True if it's a client complaint, payment failure, server outage, urgent request, security alert, or similar. False if it's a newsletter, spam, promotion, automated notification, or routine update.
2. **priority** — One of: HIGH, MEDIUM, LOW
3. **category** — One of: SERVER_DOWN, PAYMENT_ISSUE, CLIENT_COMPLAINT, SECURITY_ALERT, BILLING, URGENT_REQUEST, NEWSLETTER, SPAM, PROMOTION, AUTOMATED, GENERAL, SCHEDULED_MAINTENANCE, CI_FAILURE, BUDGET_ALERT, MEETING, FRAUD_ALERT, SUBSCRIPTION
4. **reason** — A short sentence explaining why this classification was chosen.

Respond ONLY with valid JSON in this exact format:
{"important": true/false, "priority": "HIGH|MEDIUM|LOW", "category": "CATEGORY", "reason": "..."}"""


# ---------------------------------------------------------------------------
# Provider configuration mapping
# ---------------------------------------------------------------------------

def _build_client(
    provider: str,
    api_key: str,
    base_url: str | None = None,
) -> tuple[OpenAI, str]:
    """Return ``(client, model_name)`` for the given provider.

    Parameters
    ----------
    provider:
        One of ``"openai"``, ``"openai_compat"``, ``"local"``.
    api_key:
        API key to use (may be empty for local/Ollama).
    base_url:
        Override base URL (required for ``openai_compat`` and ``local``).
    """
    if provider == "openai":
        return OpenAI(api_key=api_key), "gpt-4o-mini"

    elif provider == "openai_compat":
        return OpenAI(
            api_key=api_key,
            base_url=base_url,
        ), "gpt-4o-mini"  # model name is set separately in the request

    elif provider == "local":
        # Ollama — often doesn't need an API key
        url = base_url or "http://localhost:11434/v1"
        return OpenAI(api_key=api_key or "ollama", base_url=url), "llama3.2"

    else:
        raise ValueError(f"Unknown provider: {provider!r}")


# ---------------------------------------------------------------------------
# API Classifier
# ---------------------------------------------------------------------------


class APIClassifier(Classifier):
    """Classifies emails by calling an LLM API (OpenAI / OpenAI-compatible / Ollama).

    On any API failure (timeout, auth error, rate limit, malformed response)
    it **falls back** to :class:`RuleBasedClassifier` so the system always
    produces a result.
    """

    def __init__(
        self,
        provider: str,
        *,
        api_key: str = "",
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self._provider = provider
        self._client, self._default_model = _build_client(provider, api_key, base_url)
        self._model = model or self._default_model
        self._fallback = RuleBasedClassifier()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def name(self) -> str:
        return self._provider

    def classify(self, email: Email) -> ClassificationResult:
        try:
            result = self._call_api(email)
            if result is not None:
                return result
        except Exception as exc:
            logger.warning(
                "API classifier failed (%s), falling back to rule-based: %s",
                self._provider,
                exc,
            )

        return self._fallback.classify(email)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_api(self, email: Email) -> ClassificationResult | None:
        """Attempt to classify via the LLM API. Returns ``None`` on failure."""
        user_message = (
            f"Subject: {email.subject}\n\nBody: {email.body}"
        )

        logger.debug(
            "[%s] Sending to LLM — email=%s model=%s\nsubject=%s",
            self._provider,
            email.id,
            self._model,
            email.subject,
        )

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=300,
            timeout=30,
        )

        raw = response.choices[0].message.content
        logger.debug(
            "[%s] LLM response — email=%s\nraw=%s",
            self._provider,
            email.id,
            raw,
        )
        if not raw:
            return None

        return self._parse_response(raw)

    def _parse_response(self, raw: str) -> ClassificationResult | None:
        """Parse the JSON response from the LLM."""
        # Strip optional markdown fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove ```json ... ``` wrappers
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("\n```", 1)[0]

        try:
            data: dict[str, Any] = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON: %r", raw[:200])
            return None

        important = bool(data.get("important", False))
        priority_str = str(data.get("priority", "LOW")).upper()
        category_str = str(data.get("category", "GENERAL")).upper()
        reason = str(data.get("reason", ""))

        # Validate enums
        priority: Priority = priority_str if priority_str in ("HIGH", "MEDIUM", "LOW") else "LOW"
        category: Category = category_str if category_str in (
            "SERVER_DOWN", "PAYMENT_ISSUE", "CLIENT_COMPLAINT", "SECURITY_ALERT",
            "BILLING", "URGENT_REQUEST", "NEWSLETTER", "SPAM", "PROMOTION",
            "AUTOMATED", "GENERAL", "SCHEDULED_MAINTENANCE", "CI_FAILURE",
            "BUDGET_ALERT", "MEETING", "FRAUD_ALERT", "SUBSCRIPTION",
        ) else "GENERAL"

        return ClassificationResult(
            important=important,
            priority=priority,
            category=category,
            reason=reason or "Classified by AI",
        )
