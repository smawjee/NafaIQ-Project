"""AI tutor endpoint tests over a minimal FastAPI app (router-only, DI-overridden
auth, monkeypatched services — no network, no DB)."""
from __future__ import annotations

import json

import httpx
import pytest
from fastapi import FastAPI

FAKE_USER = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "email": "t@example.com",
    "plan": "Free",
    "features": {"ai_tutor_daily_limit": 10},
}

PAYLOAD = {
    "lessonTitle": "Candlesticks",
    "lang": "en",
    "messages": [{"role": "user", "content": "What is a doji?"}],
}


def _make_app() -> FastAPI:
    from app.api import ai as ai_api
    from app.api.deps import require_user

    app = FastAPI()
    app.include_router(ai_api.router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: FAKE_USER
    return app


async def _sse_events(client: httpx.AsyncClient, payload: dict) -> list[dict]:
    events = []
    async with client.stream("POST", "/api/ai/tutor", json=payload) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        async for line in res.aiter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


@pytest.mark.asyncio
async def test_streams_tokens_then_done_and_persists(monkeypatch):
    from app.services.ai import quota, tutor

    async def _ok_quota(user):
        return True, 3, 10

    async def _fake_stream(body, transport=None):
        yield {"type": "token", "text": "Hello"}
        yield {"type": "token", "text": " trader"}
        yield {"type": "meta", "provider": "gemini", "model": "gemini-2.5-flash"}

    persisted = {}

    async def _fake_persist(user_id, question, reply, **kw):
        persisted.update({"user_id": user_id, "question": question, "reply": reply, **kw})

    monkeypatch.setattr(quota, "check_quota", _ok_quota)
    monkeypatch.setattr(tutor, "stream_reply", _fake_stream)
    monkeypatch.setattr(tutor, "persist_exchange", _fake_persist)

    transport = httpx.ASGITransport(app=_make_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        events = await _sse_events(client, PAYLOAD)

    tokens = [e["text"] for e in events if e["type"] == "token"]
    assert tokens == ["Hello", " trader"]
    done = events[-1]
    assert done["type"] == "done"
    assert done["usage"] == {"used": 4, "limit": 10}
    assert persisted["user_id"] == FAKE_USER["user_id"]
    assert persisted["question"] == "What is a doji?"
    assert persisted["reply"] == "Hello trader"
    assert persisted["provider"] == "gemini"


@pytest.mark.asyncio
async def test_quota_exceeded_blocks_without_llm_call(monkeypatch):
    from app.services.ai import quota, tutor

    async def _blocked(user):
        return False, 10, 10

    called = {"stream": False}

    async def _fake_stream(body, transport=None):
        called["stream"] = True
        yield {"type": "token", "text": "x"}

    monkeypatch.setattr(quota, "check_quota", _blocked)
    monkeypatch.setattr(tutor, "stream_reply", _fake_stream)

    transport = httpx.ASGITransport(app=_make_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        events = await _sse_events(client, PAYLOAD)

    assert len(events) == 1
    assert events[0]["type"] == "error" and events[0]["code"] == "quota"
    assert called["stream"] is False


@pytest.mark.asyncio
async def test_provider_failure_emits_error_and_skips_persist(monkeypatch):
    from app.services.ai import providers, quota, tutor

    async def _ok_quota(user):
        return True, 0, 10

    async def _fail_stream(body, transport=None):
        raise providers.ProviderError("all providers failed")
        yield  # pragma: no cover

    persisted = {"called": False}

    async def _fake_persist(*a, **kw):
        persisted["called"] = True

    monkeypatch.setattr(quota, "check_quota", _ok_quota)
    monkeypatch.setattr(tutor, "stream_reply", _fail_stream)
    monkeypatch.setattr(tutor, "persist_exchange", _fake_persist)

    transport = httpx.ASGITransport(app=_make_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        events = await _sse_events(client, PAYLOAD)

    assert events[-1]["type"] == "error" and events[-1]["code"] == "provider"
    assert persisted["called"] is False


@pytest.mark.asyncio
async def test_history_and_usage_endpoints(monkeypatch):
    from app.services.ai import quota, tutor

    async def _fake_history(user_id, limit=20):
        return [{"id": 1, "role": "user", "content": "q", "lesson_title": None, "lang": "en", "created_at": "2026-07-12"}]

    async def _fake_summary(user):
        return {"used": 2, "limit": 10, "remaining": 8}

    monkeypatch.setattr(tutor, "get_history", _fake_history)
    monkeypatch.setattr(quota, "usage_summary", _fake_summary)

    transport = httpx.ASGITransport(app=_make_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        hist = await client.get("/api/ai/tutor/history?limit=5")
        usage = await client.get("/api/ai/tutor/usage")

    assert hist.status_code == 200 and hist.json()[0]["content"] == "q"
    assert usage.json() == {"used": 2, "limit": 10, "remaining": 8}


def test_ai_path_is_user_authenticated():
    from app.middleware.auth import _is_user_path

    assert _is_user_path("/api/ai/tutor") is True
    assert _is_user_path("/api/ai/tutor/history") is True
    assert _is_user_path("/api/aibogus") is False
