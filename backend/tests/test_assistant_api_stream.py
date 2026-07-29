from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

FAKE_USER = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "email": "t@example.com",
    "plan": "Free",
    "features": {},
}


def _make_app() -> FastAPI:
    from app.api import assistant as assistant_api
    from app.api.deps import require_user

    app = FastAPI()
    app.include_router(assistant_api.router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: FAKE_USER
    return app


async def _sse_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    transport = httpx.ASGITransport(app=_make_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        async with client.stream("POST", "/api/assistant/chat", json=payload) as res:
            assert res.status_code == 200
            assert res.headers["content-type"].startswith("text/event-stream")
            async for line in res.aiter_lines():
                if line.startswith("data:"):
                    events.append(json.loads(line[5:].strip()))
    return events


@pytest.mark.asyncio
async def test_assistant_chat_streams_clean_token_draft_done(monkeypatch):
    from app.api import assistant as assistant_api

    async def quota(_user_id, _limit):
        return True, 7

    async def turn(_user, _messages, _lang):
        yield {"type": "token", "text": "Please review this before I save it."}
        yield {
            "type": "draft",
            "action": "add_transaction",
            "tier": "confirm",
            "args": {"merchant": "KFC", "transaction_type": "expense"},
            "missing": ["amount"],
            "invalidate": ["finance-transactions"],
        }

    monkeypatch.setattr(assistant_api.assistant_usage, "check_and_increment", quota)
    monkeypatch.setattr(assistant_api.agent, "run_turn", turn)

    events = await _sse_events(
        {
            "lang": "en",
            "conversation_id": "conversation-1",
            "messages": [{"role": "user", "content": "add food"}],
        }
    )

    assert events == [
        {"type": "token", "text": "Please review this before I save it."},
        {
            "type": "draft",
            "action": "add_transaction",
            "tier": "confirm",
            "args": {"merchant": "KFC", "transaction_type": "expense"},
            "missing": ["amount"],
            "invalidate": ["finance-transactions"],
        },
        {"type": "done", "usage": {"used": 7, "limit": 40}},
    ]


@pytest.mark.asyncio
async def test_assistant_chat_quota_error_is_clean_and_done_is_not_sent(monkeypatch):
    from app.api import assistant as assistant_api

    async def quota(_user_id, _limit):
        return False, 40

    async def turn(*_args, **_kwargs):  # pragma: no cover
        raise AssertionError("quota block must not call the agent")
        yield

    monkeypatch.setattr(assistant_api.assistant_usage, "check_and_increment", quota)
    monkeypatch.setattr(assistant_api.agent, "run_turn", turn)

    events = await _sse_events(
        {"lang": "en", "messages": [{"role": "user", "content": "hi"}]}
    )

    assert events == [
        {
            "type": "error",
            "code": "quota",
            "message": "You've reached today's NafaIQ Assistant limit. It resets tomorrow.",
        }
    ]
