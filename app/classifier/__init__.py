"""Classifier package.

Provides a factory (:func:`get_classifier`) that returns the appropriate
:class:`Classifier` based on the configured provider.
"""

from __future__ import annotations

from app.classifier.base import ClassificationResult, Classifier
from app.classifier.rule_based import RuleBasedClassifier
from app.classifier.api import APIClassifier


def get_classifier(
    provider: str,
    *,
    openai_api_key: str = "",
    openai_model: str = "gpt-4o-mini",
    openai_compat_base_url: str = "",
    openai_compat_api_key: str = "",
    openai_compat_model: str = "",
    ollama_base_url: str = "",
    ollama_model: str = "llama3.2",
) -> Classifier:
    """Return the appropriate :class:`Classifier` for *provider*.

    Parameters
    ----------
    provider:
        One of ``"openai"``, ``"openai_compat"``, ``"local"``, ``"rule_based"``.
    openai_api_key, openai_model:
        Credentials for the OpenAI provider.
    openai_compat_base_url, openai_compat_api_key, openai_compat_model:
        Endpoint details for OpenAI-compatible providers (OpenRouter, Groq, etc.).
    ollama_base_url, ollama_model:
        Endpoint details for local Ollama instance.
    """
    if provider == "rule_based":
        return RuleBasedClassifier()

    if provider == "openai":
        return APIClassifier(
            "openai",
            api_key=openai_api_key,
            model=openai_model,
        )

    if provider == "openai_compat":
        return APIClassifier(
            "openai_compat",
            api_key=openai_compat_api_key,
            base_url=openai_compat_base_url,
            model=openai_compat_model,
        )

    if provider == "local":
        return APIClassifier(
            "local",
            api_key="",  # Ollama often doesn't require one
            base_url=ollama_base_url,
            model=ollama_model,
        )

    raise ValueError(
        f"Unknown provider: {provider!r}. "
        "Expected one of: openai, openai_compat, local, rule_based"
    )


__all__ = [
    "ClassificationResult",
    "Classifier",
    "get_classifier",
]
