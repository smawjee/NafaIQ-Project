"""LLM provider clients on the OpenAI Python SDK.

Gemini (primary) and Groq (fallback) both speak OpenAI-compatible
/chat/completions, so one SDK serves both via base_url.

Three call shapes are supported:
- streaming (`stream_gemini`/`stream_groq`) — yields text deltas; used by the
  AI tutor.
- one-shot JSON (`complete_gemini_json`/`complete_groq_json`) — `stream=False`
  with response_format=json_object, returning raw JSON text; used by the
  bank-email parser, which needs a whole object rather than a token stream.
- structured reports (`make_report_client`/`generate_structured`) — Instructor
  wraps the same clients for Pydantic-validated output.

Notes:
- SDK retries are off (max_retries=0): the caller handles failover, and silent
  same-provider retries would fight it.
- Any provider being unusable raises ProviderError.
- The `transport` kwarg is only for test injection (httpx.MockTransport).
"""
from __future__ import annotations

import os
import time
from typing import Any, AsyncIterator, NamedTuple, Optional, Type, TypeVar

import httpx
import instructor
import openai
import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings

log = structlog.get_logger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Kept for callers/tests that reference the full endpoint URLs.
GEMINI_URL = GEMINI_BASE_URL + "chat/completions"
GROQ_URL = GROQ_BASE_URL + "/chat/completions"


class ProviderError(Exception):
    """Provider unusable: missing key, HTTP error, transport error."""


def _client(
    base_url: str,
    api_key: str,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        max_retries=0,
        http_client=httpx.AsyncClient(
            timeout=settings.ai_tutor_request_timeout_s, transport=transport
        ),
    )


async def _stream_chat(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncIterator[str]:
    if not api_key:
        raise ProviderError(f"no API key configured for {base_url}")
    try:
        async with _client(base_url, api_key, transport) as client:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
    except openai.OpenAIError as e:
        raise ProviderError(f"{base_url}: {e}") from e
    except httpx.HTTPError as e:
        raise ProviderError(f"{base_url}: {e}") from e


def stream_gemini(
    messages: list[dict[str, str]],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncIterator[str]:
    return _stream_chat(
        GEMINI_BASE_URL,
        settings.gemini_api_key,
        settings.ai_tutor_model_primary,
        messages,
        transport,
    )


def stream_groq(
    messages: list[dict[str, str]],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncIterator[str]:
    return _stream_chat(
        GROQ_BASE_URL,
        settings.groq_api_key,
        settings.ai_tutor_model_fallback,
        messages,
        transport,
    )


# ===========================================================================
# One-shot JSON completions — used by the bank-email transaction parser
# ===========================================================================
#
# Ported onto the OpenAI SDK during the dev merge. `dev` implemented these on
# raw httpx before this module was refactored to the SDK; keeping that version
# would have meant two transports, two error-mapping paths and two timeout
# settings in one file. Signatures are unchanged, so
# services/email_import/llm.py needs no edit.


async def _complete_json(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> str:
    """One-shot completion constrained to a JSON object. Returns raw JSON text."""
    if not api_key:
        raise ProviderError(f"no API key configured for {base_url}")
    try:
        async with _client(base_url, api_key, transport) as client:
            res = await client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                stream=False,
                response_format={"type": "json_object"},
            )
    except openai.OpenAIError as e:
        raise ProviderError(f"{base_url}: {e}") from e
    except httpx.HTTPError as e:
        raise ProviderError(f"{base_url}: {e}") from e

    if not res.choices:
        raise ProviderError(f"{base_url}: no choices in response")
    content = res.choices[0].message.content
    if not content:
        raise ProviderError(f"{base_url}: empty completion")
    return content


async def complete_gemini_json(
    messages: list[dict[str, str]],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> str:
    return await _complete_json(
        GEMINI_BASE_URL,
        settings.gemini_api_key,
        settings.ai_tutor_model_primary,
        messages,
        transport,
    )


async def complete_groq_json(
    messages: list[dict[str, str]],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> str:
    return await _complete_json(
        GROQ_BASE_URL,
        settings.groq_api_key,
        settings.ai_tutor_model_fallback,
        messages,
        transport,
    )


# ===========================================================================
# Report clients — Instructor structured output + privacy-driven model routing
# ===========================================================================
#
# Reports return complete, Pydantic-validated JSON (not a token stream).
# Instructor wraps the same OpenAI-compatible clients above to give us schema
# validation + self-correcting retries, and drives both providers.
#
# Instructor mode per provider (swappable): Groq uses Mode.TOOLS (its Llama
# models have reliable native tool calling); Gemini uses Mode.JSON (its
# OpenAI-compat tool calling is flakier than JSON/response_format mode).
#
# Model names + routing come from env, so switching to a paid/ZDR tier is a
# config change, not a rewrite.

PROVIDER_GROQ = "groq"
PROVIDER_GEMINI = "gemini"

# The free Gemini AI Studio tier trains on prompts and allows human review, so
# confidential per-user data must NEVER route here. A future paid Gemini tier
# would be a different provider name and would not be in this set.
_GEMINI_FREE_PROVIDERS = frozenset({PROVIDER_GEMINI})

_INSTRUCTOR_MODE = {
    PROVIDER_GROQ: instructor.Mode.TOOLS,
    PROVIDER_GEMINI: instructor.Mode.JSON,
}

_PROVIDER_BASE_URL = {
    PROVIDER_GROQ: GROQ_BASE_URL,
    PROVIDER_GEMINI: GEMINI_BASE_URL,
}

# AsyncOpenAI rejects an empty api_key at construction. We build clients eagerly
# (routing must work without live keys), so fall back to a sentinel; a real call
# with no key then surfaces a normal auth error.
_MISSING_KEY = "not-configured"

T = TypeVar("T", bound=BaseModel)


class ReportClient(NamedTuple):
    """What the engine needs to generate one structured report: the
    Instructor-patched client, the resolved model name, and the provider."""

    client: instructor.AsyncInstructor
    model: str
    provider: str


def _report_provider(*, confidential: bool) -> str:
    """Which provider a report routes to, env-driven. Confidential per-user
    reports default to Groq (doesn't train on inputs); shared/no-PII reports
    default to the free Gemini tier. Both overridable via env."""
    if confidential:
        return os.getenv("AI_REPORT_CONFIDENTIAL_PROVIDER", PROVIDER_GROQ).strip().lower()
    return os.getenv("AI_REPORT_SHARED_PROVIDER", PROVIDER_GEMINI).strip().lower()


def _report_model(provider: str) -> str:
    """Model name for a provider — env override, else free-tier default."""
    if provider == PROVIDER_GROQ:
        return os.getenv("AI_REPORT_MODEL_GROQ", settings.ai_tutor_model_fallback)
    if provider == PROVIDER_GEMINI:
        return os.getenv("AI_REPORT_MODEL_GEMINI", settings.ai_tutor_model_primary)
    raise ProviderError(f"unknown report provider: {provider!r}")


def _report_api_key(provider: str) -> str:
    if provider == PROVIDER_GROQ:
        return settings.groq_api_key
    if provider == PROVIDER_GEMINI:
        return settings.gemini_api_key
    raise ProviderError(f"unknown report provider: {provider!r}")


def make_report_client(
    *,
    confidential: bool,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> ReportClient:
    """Build the Instructor-wrapped client + model for a report surface.
    confidential=True -> Groq; confidential=False -> a free tier.

    Hard privacy guard: if config would route confidential data to the free
    Gemini AI Studio tier, raise ProviderError — that tier trains on prompts and
    allows human review, so confidential data must never go there."""
    provider = _report_provider(confidential=confidential)

    if provider not in _PROVIDER_BASE_URL:
        raise ProviderError(f"unknown report provider: {provider!r}")

    if confidential and provider in _GEMINI_FREE_PROVIDERS:
        raise ProviderError(
            "refusing to route confidential per-user report data to the free "
            "Gemini AI Studio tier: it trains on prompts and permits human "
            "review (spec §4.5). Route confidential reports to Groq (or a paid "
            "ZDR tier)."
        )

    base_url = _PROVIDER_BASE_URL[provider]
    api_key = _report_api_key(provider) or _MISSING_KEY
    raw = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        max_retries=0,
        http_client=httpx.AsyncClient(
            timeout=settings.ai_tutor_request_timeout_s, transport=transport
        ),
    )
    client = instructor.from_openai(raw, mode=_INSTRUCTOR_MODE[provider])
    return ReportClient(client=client, model=_report_model(provider), provider=provider)


def log_report_generation(**fields: Any) -> None:
    """One structlog line per report generation, with whatever fields the caller
    has. A thin patchable seam so the generate helper and the engine both log
    through one place."""
    log.info("ai_report_generation", **fields)


async def generate_structured(
    report_client: ReportClient,
    *,
    response_model: Type[T],
    messages: list[dict[str, str]],
    report_type: str = "",
    lang: str = "en",
    max_retries: int = 2,
    **kwargs: Any,
) -> T:
    """Generate + validate a report against a Pydantic schema via Instructor.
    Instructor guarantees shape (self-correcting up to max_retries); the engine
    still runs numeric verification on top."""
    started = time.perf_counter()
    tokens: Optional[int] = None
    try:
        result: T = await report_client.client.chat.completions.create(
            model=report_client.model,
            response_model=response_model,
            messages=messages,  # type: ignore[arg-type]
            max_retries=max_retries,
            **kwargs,
        )
    except openai.OpenAIError as e:
        raise ProviderError(f"{report_client.provider}: {e}") from e
    finally:
        latency_ms = int((time.perf_counter() - started) * 1000)

    # Instructor attaches the raw completion (with usage) when available.
    raw = getattr(result, "_raw_response", None)
    usage = getattr(raw, "usage", None)
    if usage is not None:
        tokens = getattr(usage, "total_tokens", None)

    log_report_generation(
        report_type=report_type,
        provider=report_client.provider,
        model=report_client.model,
        lang=lang,
        latency_ms=latency_ms,
        tokens=tokens,
    )
    return result
