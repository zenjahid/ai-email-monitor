"""Centralized configuration management.

Reads from environment variables (loaded from .env via python-dotenv)
and provides a typed `Config` dataclass for the rest of the application.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

EmailSource = Literal["mock", "imap"]
Provider = Literal["openai", "openai_compat", "local", "rule_based"]


# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------

@dataclass
class Config:
    """Immutable configuration snapshot for the application."""

    # ---- Email source ----
    email_source: EmailSource = "mock"

    # IMAP
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_user: str = ""
    imap_pass: str = ""


    # ---- AI Provider ----
    provider: Provider = "rule_based"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # OpenAI-compatible
    openai_compat_base_url: str = "https://openrouter.ai/api/v1"
    openai_compat_api_key: str = ""
    openai_compat_model: str = "anthropic/claude-3-haiku"

    # Ollama
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3.2"

    # ---- General ----
    poll_interval: int = 120
    database_path: str = "data/emails.db"
    debug: bool = False

    # ---- Derived helpers ----
    @property
    def database_path_resolved(self) -> Path:
        return Path(self.database_path).resolve()

    @property
    def use_api(self) -> bool:
        """Whether the provider is an API-based classifier (not rule_based)."""
        return self.provider in ("openai", "openai_compat", "local")


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(*, env_file: str | None = None) -> Config:
    """Load configuration from environment variables.

    If *env_file* is provided it will be loaded with ``python-dotenv``
    (useful for local development).
    """
    if env_file is not None:
        load_dotenv(env_file)

    get = os.environ.get

    return Config(
        # Email source
        email_source=_coerce_email_source(get("EMAIL_SOURCE", "mock")),
        imap_host=get("IMAP_HOST", "imap.gmail.com"),
        imap_port=int(get("IMAP_PORT", "993")),
        imap_user=get("IMAP_USER", ""),
        imap_pass=get("IMAP_PASS", ""),
        # Provider
        provider=_coerce_provider(get("PROVIDER", "rule_based")),
        openai_api_key=get("OPENAI_API_KEY", ""),
        openai_model=get("OPENAI_MODEL", "gpt-4o-mini"),
        openai_compat_base_url=get(
            "OPENAI_COMPAT_BASE_URL", "https://openrouter.ai/api/v1"
        ),
        openai_compat_api_key=get("OPENAI_COMPAT_API_KEY", ""),
        openai_compat_model=get("OPENAI_COMPAT_MODEL", "anthropic/claude-3-haiku"),
        ollama_base_url=get("OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
        ollama_model=get("OLLAMA_MODEL", "llama3.2"),
        # General
        poll_interval=int(get("POLL_INTERVAL", "120")),
        database_path=get("DATABASE_PATH", "data/emails.db"),
        debug=get("DEBUG", "false").strip().lower() == "true",
    )


# ---------------------------------------------------------------------------
# Internal coercers
# ---------------------------------------------------------------------------

def _coerce_email_source(raw: str) -> EmailSource:
    raw = raw.strip().lower()
    if raw in ("mock", "imap"):
        return raw  # type: ignore[return-value]
    raise ValueError(
        f"Invalid EMAIL_SOURCE {raw!r}. Expected one of: mock, imap"
    )


def _coerce_provider(raw: str) -> Provider:
    raw = raw.strip().lower()
    if raw in ("openai", "openai_compat", "local", "rule_based"):
        return raw  # type: ignore[return-value]
    raise ValueError(
        f"Invalid PROVIDER {raw!r}. "
        "Expected one of: openai, openai_compat, local, rule_based"
    )
