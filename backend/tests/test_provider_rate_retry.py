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


# --- skip-dead-key rotation ------------------------------------------------


class _RateLimited(Exception):
    status_code = 429


def test_cooled_key_moves_to_the_back():
    # A key that just 429'd is tried LAST, so the pool routes to a fresh org.
    providers._KEY_COOLDOWNS.clear()
    providers._cool_key("groq", 0, _RateLimited("rate limit; try again in 30s"))
    assert providers._ready_indices("groq", 0, 3) == [1, 2, 0]
    providers._KEY_COOLDOWNS.clear()


def test_cooldown_expires_and_is_cleaned_up():
    providers._KEY_COOLDOWNS.clear()
    providers._KEY_COOLDOWNS[("groq", 1)] = 0.0  # deadline in the past
    assert providers._key_ready("groq", 1) is True
    assert ("groq", 1) not in providers._KEY_COOLDOWNS
    providers._KEY_COOLDOWNS.clear()


def test_all_keys_cooled_still_returns_every_index():
    # Never silently drop the request: if every key is cooling, all are still
    # tried (as a last resort) rather than returning an empty list.
    providers._KEY_COOLDOWNS.clear()
    providers._cool_key("groq", 0, _RateLimited("x"))
    providers._cool_key("groq", 1, _RateLimited("x"))
    assert sorted(providers._ready_indices("groq", 0, 2)) == [0, 1]
    providers._KEY_COOLDOWNS.clear()


def test_non_rate_limit_error_does_not_cool_a_key():
    providers._KEY_COOLDOWNS.clear()
    providers._cool_key("groq", 0, ProviderError("auth failed"))  # 401-ish, not 429
    assert providers._ready_indices("groq", 0, 2) == [0, 1]  # nothing sidelined
    providers._KEY_COOLDOWNS.clear()
