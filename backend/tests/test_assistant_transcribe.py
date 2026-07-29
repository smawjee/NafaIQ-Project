"""Speech-to-text provider call — Whisper on Groq.

No network: httpx.MockTransport is injected through the `transport=` kwarg
providers.transcribe_audio exposes for exactly this. Keys are fake placeholders.

The behaviour worth pinning down is that transcription inherits the same
key-pool rotation as every other non-streaming call (a spent key must not take
voice input down) and that the language hint actually reaches the wire — without
it Whisper silently translates Urdu speech into English text, which would land a
mistranslated merchant name in the user's ledger.
"""
from __future__ import annotations

import json

import httpx
import pytest

from app.config import settings
from app.services.ai import providers
from app.services.ai.providers import ProviderError

AUDIO = b"\x1aE\xdf\xa3fake-webm-bytes"


def _use_groq_keys(monkeypatch, *, key: str = "", pool: str = "") -> None:
    monkeypatch.setattr(settings, "groq_api_key", key)
    monkeypatch.setattr(settings, "groq_api_keys", pool)


def _key_of(request: httpx.Request) -> str:
    return request.headers.get("authorization", "").removeprefix("Bearer ")


def _ok(text: str = "add transaction of food via Meezan card") -> httpx.Response:
    return httpx.Response(200, json={"text": text})


async def test_returns_transcript(monkeypatch):
    _use_groq_keys(monkeypatch, key="k1")
    transport = httpx.MockTransport(lambda r: _ok())

    out = await providers.transcribe_audio(AUDIO, transport=transport)

    assert out == "add transaction of food via Meezan card"


async def test_transcript_is_stripped(monkeypatch):
    # Whisper pads with a leading space very often; an unstripped transcript
    # would show up as leading whitespace in the composer.
    _use_groq_keys(monkeypatch, key="k1")
    transport = httpx.MockTransport(lambda r: _ok("  add bill  "))

    assert await providers.transcribe_audio(AUDIO, transport=transport) == "add bill"


async def test_language_hint_is_sent(monkeypatch):
    _use_groq_keys(monkeypatch, key="k1")
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        return _ok("گروسری کی ٹرانزیکشن شامل کریں")

    out = await providers.transcribe_audio(
        AUDIO, language="ur", transport=httpx.MockTransport(handler)
    )

    # Multipart body — assert the field is present rather than parsing it.
    assert b'name="language"' in bodies[0]
    assert b"ur" in bodies[0]
    assert out == "گروسری کی ٹرانزیکشن شامل کریں"


async def test_language_omitted_when_not_given(monkeypatch):
    # Whisper auto-detects when no hint is sent; sending an empty field instead
    # would be a different (and worse) request than sending none.
    _use_groq_keys(monkeypatch, key="k1")
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        return _ok()

    await providers.transcribe_audio(AUDIO, transport=httpx.MockTransport(handler))

    assert b'name="language"' not in bodies[0]


async def test_model_and_endpoint(monkeypatch):
    _use_groq_keys(monkeypatch, key="k1")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _ok()

    await providers.transcribe_audio(AUDIO, transport=httpx.MockTransport(handler))

    assert seen[0].url.path.endswith("/audio/transcriptions")
    assert b"whisper-large-v3-turbo" in seen[0].content


async def test_rotates_to_spare_key_on_quota(monkeypatch):
    # A spent key must not take voice input down — same contract as chat.
    _use_groq_keys(monkeypatch, key="dead", pool="spare")
    tried: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        key = _key_of(request)
        tried.append(key)
        if key == "dead":
            return httpx.Response(429, json={"error": {"message": "rate limit reached"}})
        return _ok()

    out = await providers.transcribe_audio(AUDIO, transport=httpx.MockTransport(handler))

    assert tried == ["dead", "spare"]
    assert out == "add transaction of food via Meezan card"


async def test_all_keys_exhausted_raises(monkeypatch):
    _use_groq_keys(monkeypatch, key="d1", pool="d2")
    transport = httpx.MockTransport(
        lambda r: httpx.Response(429, json={"error": {"message": "quota exceeded"}})
    )

    with pytest.raises(ProviderError) as exc:
        await providers.transcribe_audio(AUDIO, transport=transport)
    assert "exhausted" in str(exc.value)


async def test_non_rotating_error_is_not_retried(monkeypatch):
    # A 400 is our bug (bad audio container), not a dead key: burning the whole
    # pool on it would turn one bad upload into a provider-wide outage.
    _use_groq_keys(monkeypatch, key="k1", pool="k2")
    tried: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        tried.append(_key_of(request))
        return httpx.Response(400, json={"error": {"message": "could not decode audio"}})

    with pytest.raises(ProviderError):
        await providers.transcribe_audio(AUDIO, transport=httpx.MockTransport(handler))
    assert tried == ["k1"]


async def test_no_keys_configured(monkeypatch):
    _use_groq_keys(monkeypatch, key="", pool="")
    with pytest.raises(ProviderError) as exc:
        await providers.transcribe_audio(AUDIO)
    assert "no API key configured" in str(exc.value)


async def test_empty_audio_rejected_before_any_call(monkeypatch):
    _use_groq_keys(monkeypatch, key="k1")

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("must not reach the provider with empty audio")

    with pytest.raises(ProviderError) as exc:
        await providers.transcribe_audio(b"", transport=httpx.MockTransport(handler))
    assert "no audio" in str(exc.value)


async def test_unknown_stt_provider_rejected(monkeypatch):
    monkeypatch.setattr(settings, "ai_stt_provider", "deepgram")
    with pytest.raises(ProviderError) as exc:
        await providers.transcribe_audio(AUDIO)
    assert "unknown STT provider" in str(exc.value)


# --- malformed tool calls --------------------------------------------------
#
# Live regression: Groq returned 400 tool_use_failed because llama-3.3-70b
# emitted its call as literal text ("<function=add_goal_alert{...}</function>").
# It is sampling noise rather than a bad key, so rotation neither fires (400 is
# not a rotate status) nor would help — but at temperature 0 a plain retry
# reproduces the identical bad generation, so the retry must vary something.

_TOOL_USE_FAILED = {
    "error": {
        "message": "Failed to call a function. Please adjust your prompt.",
        "type": "invalid_request_error",
        "code": "tool_use_failed",
        "failed_generation": "<function=add_goal_alert{}</function>",
    }
}

_OK_TOOL_CALL = {
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "get_goals", "arguments": "{}"},
                    }
                ],
            }
        }
    ]
}


async def test_malformed_tool_call_is_retried_at_a_higher_temperature(monkeypatch):
    _use_groq_keys(monkeypatch, key="k1", pool="k2")
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append({"key": _key_of(request), "temperature": body.get("temperature")})
        if len(seen) == 1:
            return httpx.Response(400, json=_TOOL_USE_FAILED)
        return httpx.Response(200, json=_OK_TOOL_CALL)

    msg = await providers.complete_with_tools(
        [{"role": "user", "content": "how close am I to my Hajj Fund?"}],
        [],
        transport=httpx.MockTransport(handler),
    )

    assert msg.tool_calls[0].function.name == "get_goals"
    # Same key — this was never a key problem.
    assert [s["key"] for s in seen] == ["k1", "k1"]
    # A second identical request would be deterministic and fail the same way.
    assert seen[0]["temperature"] == 0.0
    assert seen[1]["temperature"] > 0.0


async def test_malformed_twice_gives_up_without_burning_the_pool(monkeypatch):
    # Every key runs the same model, so a second key would reproduce it.
    _use_groq_keys(monkeypatch, key="k1", pool="k2,k3")
    tried: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        tried.append(_key_of(request))
        return httpx.Response(400, json=_TOOL_USE_FAILED)

    with pytest.raises(ProviderError):
        await providers.complete_with_tools(
            [{"role": "user", "content": "hi"}], [], transport=httpx.MockTransport(handler)
        )
    assert tried == ["k1", "k1"], f"should not rotate on a model fault, got {tried}"


async def test_rate_limit_still_rotates_and_is_typed(monkeypatch):
    _use_groq_keys(monkeypatch, key="dead", pool="spare")
    tried: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        tried.append(_key_of(request))
        if _key_of(request) == "dead":
            return httpx.Response(429, json={"error": {"message": "rate limit reached"}})
        return httpx.Response(200, json=_OK_TOOL_CALL)

    msg = await providers.complete_with_tools(
        [{"role": "user", "content": "hi"}], [], transport=httpx.MockTransport(handler)
    )
    assert tried == ["dead", "spare"]
    assert msg.tool_calls


async def test_exhausted_pool_raises_the_rate_limited_subtype(monkeypatch):
    """"Busy, try again" and "something broke" need different messages."""
    _use_groq_keys(monkeypatch, key="k1", pool="k2")
    transport = httpx.MockTransport(
        lambda r: httpx.Response(
            429, json={"error": {"message": "rate limit reached. Please try again in 11.51s."}}
        )
    )
    with pytest.raises(providers.ProviderRateLimited) as exc:
        await providers.complete_with_tools(
            [{"role": "user", "content": "hi"}], [], transport=transport
        )
    assert exc.value.retry_after_s == pytest.approx(11.51)
