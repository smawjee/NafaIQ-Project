"""Async clients for OpenAI-compatible chat-completion providers.

Gemini (primary) and Groq (fallback) both expose /chat/completions. Two call
shapes are supported:
- streaming (`stream_gemini`/`stream_groq`) — SSE `data: {json}` lines
  terminated by `data: [DONE]`; used by the AI tutor.
- one-shot JSON (`complete_gemini_json`/`complete_groq_json`) — `stream: false`
  with JSON-object response format; used by the bank-email parser, which needs
  a whole structured object rather than a token stream.

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


async def _complete_json(
    url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> str:
    """One-shot completion constrained to a JSON object. Returns raw JSON text."""
    if not api_key:
        raise ProviderError(f"no API key configured for {url}")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(
            timeout=settings.ai_tutor_request_timeout_s, transport=transport
        ) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code != 200:
                raise ProviderError(f"{url}: HTTP {res.status_code}")
            data = res.json()
    except httpx.HTTPError as e:
        raise ProviderError(f"{url}: {e}") from e
    except json.JSONDecodeError as e:
        raise ProviderError(f"{url}: malformed response body: {e}") from e

    choices = data.get("choices") or []
    if not choices:
        raise ProviderError(f"{url}: no choices in response")
    content = (choices[0].get("message") or {}).get("content")
    if not content:
        raise ProviderError(f"{url}: empty completion")
    return content


async def complete_gemini_json(
    messages: list[dict[str, str]],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> str:
    return await _complete_json(
        GEMINI_URL, settings.gemini_api_key, settings.ai_tutor_model_primary, messages, transport
    )


async def complete_groq_json(
    messages: list[dict[str, str]],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> str:
    return await _complete_json(
        GROQ_URL, settings.groq_api_key, settings.ai_tutor_model_fallback, messages, transport
    )
