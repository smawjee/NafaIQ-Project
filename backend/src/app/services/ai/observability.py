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
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator

from app.config import settings
from app.services.ai.safety import redact_sensitive

log = logging.getLogger(__name__)

_initialized = False

# Same guard shape as providers.py's client-class swap: enabled is a deployment
# decision (keys set), installed is a build decision (package present); neither
# drifting may break the app. Every module that wants tracing decorators
# imports them from HERE, never from `langfuse` directly — that indirection is
# the whole no-op guarantee for CI and keyless deploys.
if settings.langfuse_enabled:
    try:
        from langfuse import observe, propagate_attributes  # noqa: F401

        _TRACING = True
    except ImportError:  # pragma: no cover - depends on the build
        _TRACING = False
else:
    _TRACING = False

if not _TRACING:

    def observe(func=None, **_kwargs):  # type: ignore[no-redef]
        """Identity decorator: supports both @observe and @observe(name=...)."""
        if func is not None:
            return func
        return lambda f: f

    def propagate_attributes(**_kwargs):  # type: ignore[no-redef]
        """No-op stand-in for langfuse.propagate_attributes."""
        return nullcontext()


@contextmanager
def observation_span(
    name: str, *, as_type: str = "span", input: Any = None
) -> Iterator[Any]:
    """Manual nested span; yields the live span, or None when tracing is off.

    For work the @observe decorator can't reach cleanly — e.g. one tool
    execution inside a loop, or an API (audio) the openai wrapper doesn't
    auto-trace. Never raises: an observability failure must not break the
    request it was meant to describe.
    """
    if not _TRACING:
        yield None
        return
    try:
        from langfuse import get_client

        cm = get_client().start_as_current_observation(
            name=name, as_type=as_type, input=redact_sensitive(input)
        )
    except Exception:
        log.warning("langfuse span '%s' failed to start", name, exc_info=True)
        yield None
        return
    with cm as span:
        yield span


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
