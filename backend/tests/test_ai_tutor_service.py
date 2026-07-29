"""Tutor service: prompt building, provider fallback, quota math.

Provider calls are faked by monkeypatching app.services.ai.providers functions
(no network); quota DB reads are faked by monkeypatching ai_repo.
"""
from __future__ import annotations

import pytest

from app.schemas.ai import TutorRequest
from app.services.ai import providers


def _request(**overrides) -> TutorRequest:
    payload = {
        "lessonTitle": "Candlesticks",
        "lang": "en",
        "messages": [{"role": "user", "content": "What is a doji?"}],
    }
    payload.update(overrides)
    return TutorRequest(**payload)


async def _gen(chunks):
    for c in chunks:
        yield c


async def _failing_gen():
    raise providers.ProviderError("boom")
    yield  # pragma: no cover — makes this an async generator


def test_system_prompt_english_mentions_lesson_and_examples():
    from app.services.ai import tutor

    prompt = tutor.build_system_prompt("Candlesticks", None, "en")
    assert "Candlesticks" in prompt
    assert "KSE-100" in prompt
    assert "Reply in English" in prompt


def test_system_prompt_urdu_and_context():
    from app.services.ai import tutor

    prompt = tutor.build_system_prompt("Candlesticks", "Doji section", "ur")
    assert "Doji section" in prompt
    assert "Urdu" in prompt


@pytest.mark.asyncio
async def test_stream_reply_uses_gemini_when_healthy(monkeypatch):
    from app.services.ai import tutor

    monkeypatch.setattr(providers, "stream_gemini", lambda m, transport=None: _gen(["A", "B"]))
    monkeypatch.setattr(providers, "stream_groq", lambda m, transport=None: _failing_gen())
    events = [e async for e in tutor.stream_reply(_request())]
    assert [e["text"] for e in events if e["type"] == "token"] == ["A", "B"]
    meta = events[-1]
    assert meta["type"] == "meta" and meta["provider"] == "gemini"


@pytest.mark.asyncio
async def test_stream_reply_falls_back_to_groq(monkeypatch):
    from app.services.ai import tutor

    monkeypatch.setattr(providers, "stream_gemini", lambda m, transport=None: _failing_gen())
    monkeypatch.setattr(providers, "stream_groq", lambda m, transport=None: _gen(["G"]))
    events = [e async for e in tutor.stream_reply(_request())]
    assert [e["text"] for e in events if e["type"] == "token"] == ["G"]
    assert events[-1]["provider"] == "groq"


@pytest.mark.asyncio
async def test_stream_reply_raises_when_all_fail(monkeypatch):
    from app.services.ai import tutor

    monkeypatch.setattr(providers, "stream_gemini", lambda m, transport=None: _failing_gen())
    monkeypatch.setattr(providers, "stream_groq", lambda m, transport=None: _failing_gen())
    with pytest.raises(providers.ProviderError):
        async for _ in tutor.stream_reply(_request()):
            pass


@pytest.mark.asyncio
async def test_mid_stream_failure_does_not_fall_back(monkeypatch):
    from app.services.ai import tutor

    async def _breaks_mid_stream(m, transport=None):
        yield "partial"
        raise providers.ProviderError("mid-stream")

    called = {"groq": False}

    def _groq(m, transport=None):
        called["groq"] = True
        return _gen(["nope"])

    monkeypatch.setattr(providers, "stream_gemini", _breaks_mid_stream)
    monkeypatch.setattr(providers, "stream_groq", _groq)
    received = []
    with pytest.raises(providers.ProviderError):
        async for e in tutor.stream_reply(_request()):
            received.append(e)
    assert [e["text"] for e in received] == ["partial"]
    assert called["groq"] is False  # never switched mid-stream


@pytest.mark.asyncio
@pytest.mark.requires_db  # touches the real engine
async def test_check_quota_under_at_and_unlimited(monkeypatch):
    from app.repositories import ai_repo
    from app.services.ai import quota

    async def _used(conn, uid):
        return 9

    monkeypatch.setattr(ai_repo, "get_today_usage", _used)

    user = {"user_id": "u1", "features": {"ai_tutor_daily_limit": 10}}
    allowed, used, limit = await quota.check_quota(user)
    assert (allowed, used, limit) == (True, 9, 10)

    async def _at_limit(conn, uid):
        return 10

    monkeypatch.setattr(ai_repo, "get_today_usage", _at_limit)
    allowed, used, limit = await quota.check_quota(user)
    assert allowed is False

    unlimited = {"user_id": "u1", "features": {"ai_tutor_daily_limit": None}}
    allowed, used, limit = await quota.check_quota(unlimited)
    assert allowed is True and limit is None

    no_features = {"user_id": "u1", "features": {}}
    allowed, used, limit = await quota.check_quota(no_features)
    assert allowed is True and limit is None
