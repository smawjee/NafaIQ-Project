"""Langfuse LLM observability wiring.

Tracing is opt-in: when both Langfuse keys are configured, every LLM call made
through services/ai/providers.py is traced (model, tokens, latency, cost) via
Langfuse's drop-in OpenAI wrapper. When the keys are absent this is a complete
no-op, so CI, local dev without keys, and any deploy that hasn't set them run
exactly as before.

pydantic-settings loads .env into `settings`, NOT into os.environ, and the
Langfuse SDK reads its credentials from the environment / a configured client —
so we initialise the singleton EXPLICITLY from settings here, once, at startup.
"""
from __future__ import annotations

import logging

from app.config import settings

log = logging.getLogger(__name__)

_initialized = False


def init_langfuse() -> None:
    """Configure the Langfuse singleton from settings. Idempotent, safe to call
    when disabled (returns immediately), and never raises — an observability
    failure must not take down the app."""
    global _initialized
    if _initialized or not settings.langfuse_enabled:
        return
    try:
        from langfuse import Langfuse

        # Constructing with explicit credentials configures the process-wide
        # singleton that both the openai wrapper and @observe use via
        # get_client(). We don't hold the instance — get_client() returns it.
        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        _initialized = True
        log.info("langfuse tracing enabled (host=%s)", settings.langfuse_host)
    except Exception:
        # Bad key, unreachable host, SDK import issue — log and carry on
        # untraced rather than break startup.
        log.warning("langfuse init failed; continuing without tracing", exc_info=True)


def flush_langfuse() -> None:
    """Flush buffered traces on shutdown so nothing is lost on exit."""
    if not _initialized:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        log.warning("langfuse flush failed", exc_info=True)
