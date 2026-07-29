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


@pytest.fixture(autouse=True)
def _isolate_key_pools(monkeypatch):
    """Blank the multi-key pool vars for every test in this module.

    providers.py tries GEMINI_API_KEY first, then every key in GEMINI_API_KEYS.
    Any developer or CI box with those populated made these tests exercise the
    real pool: the 429 test rotated through live production keys instead of
    testing rotation, and the missing-key test could not reach the no-keys
    branch at all. Each test opts back in to exactly the keys it means to test.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_keys", "")
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "groq_api_keys", "")


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


@pytest.mark.asyncio
async def test_double_tool_use_failed_raises_typed_unparseable(monkeypatch):
    """Groq 400 `tool_use_failed` on both attempts (temp 0, then the bump) must
    surface as ProviderToolCallUnparseable — the typed error the agent catches
    to finish the turn in prose — not the generic ProviderError that used to
    show "couldn't reach the assistant" in production.
    """
    from app.config import settings
    from app.services.ai import providers

    monkeypatch.setattr(settings, "groq_api_key", "test-key")

    calls = {"n": 0}

    def tool_use_failed(request):
        calls["n"] += 1
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": "Failed to call a function. Please adjust your prompt.",
                    "type": "invalid_request_error",
                    "code": "tool_use_failed",
                    "failed_generation": '<function=add_to_watchlist{"symbol": "OGDC"}</function>',
                }
            },
        )

    tools = [
        {
            "type": "function",
            "function": {"name": "add_to_watchlist", "parameters": {"type": "object"}},
        }
    ]
    with pytest.raises(providers.ProviderToolCallUnparseable):
        await providers.complete_with_tools(
            MESSAGES, tools, transport=httpx.MockTransport(tool_use_failed)
        )
    # Exactly two attempts on the one key: temperature 0, then the bump —
    # no pointless rotation over a model fault.
    assert calls["n"] == 2
