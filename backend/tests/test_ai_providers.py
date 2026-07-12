"""Provider SSE clients, tested with httpx.MockTransport (no network)."""
from __future__ import annotations

import httpx
import pytest

SSE_BODY = (
    b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
    b'data: {"choices":[{"delta":{"content":" PSX"}}]}\n\n'
    b'data: {"choices":[{"delta":{}}]}\n\n'
    b"data: [DONE]\n\n"
)

MESSAGES = [{"role": "user", "content": "hi"}]


def _ok_transport() -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda request: httpx.Response(
            200, content=SSE_BODY, headers={"content-type": "text/event-stream"}
        )
    )


def _error_transport(status: int) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(status, json={"error": "x"}))


@pytest.mark.asyncio
async def test_stream_gemini_yields_deltas(monkeypatch):
    from app.config import settings
    from app.services.ai import providers

    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    chunks = [c async for c in providers.stream_gemini(MESSAGES, transport=_ok_transport())]
    assert chunks == ["Hello", " PSX"]


@pytest.mark.asyncio
async def test_stream_groq_yields_deltas(monkeypatch):
    from app.config import settings
    from app.services.ai import providers

    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    chunks = [c async for c in providers.stream_groq(MESSAGES, transport=_ok_transport())]
    assert chunks == ["Hello", " PSX"]


@pytest.mark.asyncio
async def test_http_429_raises_provider_error(monkeypatch):
    from app.config import settings
    from app.services.ai import providers

    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    with pytest.raises(providers.ProviderError):
        async for _ in providers.stream_gemini(MESSAGES, transport=_error_transport(429)):
            pass


@pytest.mark.asyncio
async def test_missing_key_raises_provider_error(monkeypatch):
    from app.config import settings
    from app.services.ai import providers

    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(providers.ProviderError):
        async for _ in providers.stream_gemini(MESSAGES, transport=_ok_transport()):
            pass


@pytest.mark.asyncio
async def test_connect_error_raises_provider_error(monkeypatch):
    from app.config import settings
    from app.services.ai import providers

    monkeypatch.setattr(settings, "groq_api_key", "test-key")

    def boom(request):
        raise httpx.ConnectError("no route")

    with pytest.raises(providers.ProviderError):
        async for _ in providers.stream_groq(MESSAGES, transport=httpx.MockTransport(boom)):
            pass
