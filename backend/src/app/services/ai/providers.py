"""LLM provider clients built on the official OpenAI Python SDK.

Gemini (primary) and Groq (fallback) both expose OpenAI-compatible
/chat/completions endpoints, so a single SDK serves both via base_url —
one code path, symmetric errors, typed streaming.

Design constraints preserved from the original httpx implementation:
- Public contract is unchanged: stream_gemini / stream_groq yield text deltas
  and raise ProviderError for anything that makes a provider unusable.
- SDK retries are DISABLED (max_retries=0): failover to the next provider is
  handled by the caller (tutor.stream_reply), and silent same-provider
  retries would fight it.
- The `transport` kwarg exists only for test injection (httpx.MockTransport),
  threaded through via the SDK's http_client parameter.
"""
from __future__ import annotations

from typing import AsyncIterator, Optional

import httpx
import openai
from openai import AsyncOpenAI

from app.config import settings

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
