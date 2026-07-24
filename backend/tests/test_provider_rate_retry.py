"""Automatic rate-limit recovery for the assistant.

Groq's TPM cap is per-organisation, so once every key is throttled, rotating
again can't help — the only cure is to wait out the window. complete_with_tools
must do that automatically (wait the provider's retry-after, retry) so the user
never sees a 429, instead of surfacing the error for them to retry by hand.
"""
import pytest

from app.services.ai import providers
from app.services.ai.providers import ProviderError, ProviderRateLimited


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    slept: list[float] = []

    async def fake_sleep(d):
        slept.append(d)

    monkeypatch.setattr(providers.asyncio, "sleep", fake_sleep)
    return slept


@pytest.mark.asyncio
async def test_auto_retries_then_succeeds(monkeypatch, _no_real_sleep):
    calls = {"n": 0}

    async def once(messages, tools, *, tool_choice="auto", transport=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ProviderRateLimited("all keys exhausted", 0.01)
        return "OK"

    monkeypatch.setattr(providers, "_complete_with_tools_once", once)

    result = await providers.complete_with_tools([], [])
    assert result == "OK"
    assert calls["n"] == 2          # retried once, transparently
    assert _no_real_sleep == [0.01]  # waited the provider's retry-after first


@pytest.mark.asyncio
async def test_gives_up_after_bounded_attempts(monkeypatch, _no_real_sleep):
    calls = {"n": 0}

    async def always(messages, tools, *, tool_choice="auto", transport=None):
        calls["n"] += 1
        raise ProviderRateLimited("exhausted", 0.01)

    monkeypatch.setattr(providers, "_complete_with_tools_once", always)
    monkeypatch.setattr(providers.settings, "ai_assistant_rate_retry_attempts", 2)

    with pytest.raises(ProviderRateLimited):
        await providers.complete_with_tools([], [])
    assert calls["n"] == 3  # initial + 2 retries, then it stops (no infinite loop)


@pytest.mark.asyncio
async def test_non_rate_limit_error_is_not_retried(monkeypatch, _no_real_sleep):
    calls = {"n": 0}

    async def once(messages, tools, *, tool_choice="auto", transport=None):
        calls["n"] += 1
        raise ProviderError("bad request")

    monkeypatch.setattr(providers, "_complete_with_tools_once", once)

    with pytest.raises(ProviderError):
        await providers.complete_with_tools([], [])
    assert calls["n"] == 1  # a non-429 failure surfaces immediately
