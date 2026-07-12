"""Async SSE clients for OpenAI-compatible chat-completion providers.

Gemini (primary) and Groq (fallback) both expose /chat/completions with
`stream: true` returning `data: {json}` SSE lines terminated by `data: [DONE]`.
The `transport` kwarg exists only for test injection (httpx.MockTransport).
"""
from __future__ import annotations

import json
from typing import AsyncIterator, Optional

import httpx

from app.config import settings

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class ProviderError(Exception):
    """Provider unusable: missing key, HTTP error, transport error."""


async def _stream_chat(
    url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncIterator[str]:
    if not api_key:
        raise ProviderError(f"no API key configured for {url}")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "stream": True}
    try:
        async with httpx.AsyncClient(
            timeout=settings.ai_tutor_request_timeout_s, transport=transport
        ) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as res:
                if res.status_code != 200:
                    await res.aread()
                    raise ProviderError(f"{url}: HTTP {res.status_code}")
                async for line in res.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue  # tolerate malformed keep-alive lines
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {}).get("content")
                    if delta:
                        yield delta
    except httpx.HTTPError as e:
        raise ProviderError(f"{url}: {e}") from e


def stream_gemini(
    messages: list[dict[str, str]],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncIterator[str]:
    return _stream_chat(
        GEMINI_URL, settings.gemini_api_key, settings.ai_tutor_model_primary, messages, transport
    )


def stream_groq(
    messages: list[dict[str, str]],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncIterator[str]:
    return _stream_chat(
        GROQ_URL, settings.groq_api_key, settings.ai_tutor_model_fallback, messages, transport
    )
