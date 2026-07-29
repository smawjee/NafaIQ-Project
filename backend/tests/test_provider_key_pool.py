"""Multi-key fallback: rotate to a spare key when one key's quota is spent.

No network — httpx.MockTransport is injected through the `transport=` kwarg that
providers.* already expose for exactly this. Keys here are fake placeholders.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import openai
import pytest
from pydantic import BaseModel

from app.config import Settings, merge_key_pool, settings
from app.services.ai import providers
from app.services.ai.providers import PROVIDER_GEMINI, PROVIDER_GROQ, ProviderError, ReportClient

MESSAGES = [{"role": "user", "content": "hi"}]

SSE_BODY = (
    b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
    b'data: {"choices":[{"delta":{"content":" PSX"}}]}\n\n'
    b"data: [DONE]\n\n"
)

JSON_BODY = {"choices": [{"message": {"role": "assistant", "content": '{"ok":true}'}}]}


def _use_keys(monkeypatch, *, gemini: str = "", gemini_pool: str = "") -> None:
    monkeypatch.setattr(settings, "gemini_api_key", gemini)
    monkeypatch.setattr(settings, "gemini_api_keys", gemini_pool)


def _key_of(request: httpx.Request) -> str:
    return request.headers.get("authorization", "").removeprefix("Bearer ")


def _sse_ok() -> httpx.Response:
    return httpx.Response(200, content=SSE_BODY, headers={"content-type": "text/event-stream"})


def _routing_transport(responses: dict[str, httpx.Response], seen: list[str]) -> httpx.MockTransport:
    """Reply per-key, recording which keys were actually tried and in what order."""

    def handler(request: httpx.Request) -> httpx.Response:
        key = _key_of(request)
        seen.append(key)
        return responses[key]

    return httpx.MockTransport(handler)


# --- pool parsing / back-compat -------------------------------------------
def test_single_key_pool_is_just_that_key():
    assert merge_key_pool("k1", "") == ["k1"]


def test_no_keys_at_all_is_empty():
    assert merge_key_pool("", "") == []


def test_pool_strips_whitespace_blanks_and_trailing_commas():
    assert merge_key_pool("", " k1 , k2 ,, k3 ,") == ["k1", "k2", "k3"]


def test_singular_key_leads_the_pool():
    # The pre-existing GEMINI_API_KEY must stay the first key tried, so an
    # existing single-key deployment behaves exactly as before.
    assert merge_key_pool("primary", "spare1,spare2") == ["primary", "spare1", "spare2"]


def test_pool_dedupes_preserving_order():
    # Same key in both vars (or listed twice) must not be tried twice.
    assert merge_key_pool("k1", "k2,k1,k2,k3") == ["k1", "k2", "k3"]


def test_settings_defaults_are_empty():
    s = Settings(_env_file=None)
    assert s.gemini_api_keys == ""
    assert s.groq_api_keys == ""
    assert s.gemini_api_key_pool == []
    assert s.groq_api_key_pool == []


def test_settings_pool_properties_read_both_vars(monkeypatch):
    _use_keys(monkeypatch, gemini="g0", gemini_pool="g1,g2")
    assert settings.gemini_api_key_pool == ["g0", "g1", "g2"]


def test_pool_only_deployment_needs_no_singular_key(monkeypatch):
    _use_keys(monkeypatch, gemini="", gemini_pool="g1,g2")
    assert settings.gemini_api_key_pool == ["g1", "g2"]


# --- streaming -------------------------------------------------------------
@pytest.mark.asyncio
async def test_stream_single_key_still_works(monkeypatch):
    _use_keys(monkeypatch, gemini="only-key")
    seen: list[str] = []
    transport = _routing_transport({"only-key": _sse_ok()}, seen)
    chunks = [c async for c in providers.stream_gemini(MESSAGES, transport=transport)]
    assert chunks == ["Hello", " PSX"]
    assert seen == ["only-key"]


@pytest.mark.asyncio
async def test_stream_rotates_to_next_key_on_429(monkeypatch):
    _use_keys(monkeypatch, gemini="spent", gemini_pool="fresh")
    seen: list[str] = []
    transport = _routing_transport(
        {
            "spent": httpx.Response(429, json={"error": {"message": "quota exceeded"}}),
            "fresh": _sse_ok(),
        },
        seen,
    )
    chunks = [c async for c in providers.stream_gemini(MESSAGES, transport=transport)]
    assert chunks == ["Hello", " PSX"]
    assert seen == ["spent", "fresh"]  # tried in order, stopped at the working key


@pytest.mark.asyncio
async def test_stream_rotates_past_a_dead_key(monkeypatch):
    # A revoked key (401) must not take the app down — advance to the spare.
    _use_keys(monkeypatch, gemini="revoked", gemini_pool="fresh")
    seen: list[str] = []
    transport = _routing_transport(
        {
            "revoked": httpx.Response(401, json={"error": {"message": "invalid api key"}}),
            "fresh": _sse_ok(),
        },
        seen,
    )
    chunks = [c async for c in providers.stream_gemini(MESSAGES, transport=transport)]
    assert chunks == ["Hello", " PSX"]
    assert seen == ["revoked", "fresh"]


@pytest.mark.asyncio
async def test_stream_raises_when_all_keys_exhausted(monkeypatch):
    _use_keys(monkeypatch, gemini="k1", gemini_pool="k2,k3")
    seen: list[str] = []
    spent = lambda: httpx.Response(429, json={"error": {"message": "quota exceeded"}})  # noqa: E731
    transport = _routing_transport({"k1": spent(), "k2": spent(), "k3": spent()}, seen)

    with pytest.raises(ProviderError) as ei:
        async for _ in providers.stream_gemini(MESSAGES, transport=transport):
            pass

    assert seen == ["k1", "k2", "k3"]  # every key was tried
    assert "all 3 gemini keys exhausted" in str(ei.value)


@pytest.mark.asyncio
async def test_stream_does_not_rotate_on_a_malformed_request(monkeypatch):
    # 400 is our fault, not the key's: every key would fail identically, so
    # fail fast on the first one instead of burning the pool.
    _use_keys(monkeypatch, gemini="k1", gemini_pool="k2,k3")
    seen: list[str] = []
    transport = _routing_transport(
        {
            "k1": httpx.Response(400, json={"error": {"message": "invalid 'messages[0].role'"}}),
            "k2": _sse_ok(),
            "k3": _sse_ok(),
        },
        seen,
    )
    with pytest.raises(ProviderError):
        async for _ in providers.stream_gemini(MESSAGES, transport=transport):
            pass
    assert seen == ["k1"]


@pytest.mark.asyncio
async def test_stream_does_not_rotate_on_a_connect_error(monkeypatch):
    # The network is down, not the key. Trying the spares just multiplies latency.
    _use_keys(monkeypatch, gemini="k1", gemini_pool="k2")
    calls = {"n": 0}

    def boom(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("no route")

    with pytest.raises(ProviderError):
        async for _ in providers.stream_gemini(MESSAGES, transport=httpx.MockTransport(boom)):
            pass
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_stream_never_rotates_once_tokens_are_emitted(monkeypatch):
    # Rotating mid-stream would replay the opening tokens to a user who has
    # already seen them. Truncate and raise instead.
    _use_keys(monkeypatch, gemini="k1", gemini_pool="k2")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(_key_of(request))
        if _key_of(request) == "k1":
            # one good token, then the connection drops mid-body
            async def _drop():
                yield b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
                raise httpx.ReadError("connection reset")

            return httpx.Response(
                200, content=_drop(), headers={"content-type": "text/event-stream"}
            )
        return _sse_ok()

    received = []
    with pytest.raises(ProviderError):
        async for c in providers.stream_gemini(MESSAGES, transport=httpx.MockTransport(handler)):
            received.append(c)

    assert received == ["Hel"]  # partial output kept, not replayed
    assert seen == ["k1"]  # k2 was never tried


@pytest.mark.asyncio
async def test_stream_with_no_keys_configured_raises(monkeypatch):
    _use_keys(monkeypatch, gemini="", gemini_pool="")
    with pytest.raises(ProviderError) as ei:
        async for _ in providers.stream_gemini(MESSAGES, transport=httpx.MockTransport(lambda r: _sse_ok())):
            pass
    assert "no API key configured" in str(ei.value)


@pytest.mark.asyncio
async def test_rotation_logs_index_never_the_key(monkeypatch):
    _use_keys(monkeypatch, gemini="super-secret-key", gemini_pool="fresh")
    events: list[tuple] = []
    monkeypatch.setattr(
        providers.log, "warning", lambda event, **kw: events.append((event, kw))
    )
    seen: list[str] = []
    transport = _routing_transport(
        {
            "super-secret-key": httpx.Response(429, json={"error": {"message": "quota"}}),
            "fresh": _sse_ok(),
        },
        seen,
    )
    [c async for c in providers.stream_gemini(MESSAGES, transport=transport)]

    assert len(events) == 1
    event, fields = events[0]
    assert event == "llm_key_rotated"
    assert fields["provider"] == PROVIDER_GEMINI
    assert fields["key_index"] == 0
    # the key itself (or any prefix of it) must never be logged
    assert "super-secret-key" not in str(fields)
    assert "super" not in str(fields)


# --- one-shot JSON ---------------------------------------------------------
@pytest.mark.asyncio
async def test_complete_json_rotates_on_429(monkeypatch):
    _use_keys(monkeypatch, gemini="spent", gemini_pool="fresh")
    seen: list[str] = []
    transport = _routing_transport(
        {
            "spent": httpx.Response(429, json={"error": {"message": "quota exceeded"}}),
            "fresh": httpx.Response(200, json=JSON_BODY),
        },
        seen,
    )
    raw = await providers.complete_gemini_json(MESSAGES, transport=transport)
    assert raw == '{"ok":true}'
    assert seen == ["spent", "fresh"]


@pytest.mark.asyncio
async def test_complete_json_raises_when_all_keys_exhausted(monkeypatch):
    _use_keys(monkeypatch, gemini="k1", gemini_pool="k2")
    seen: list[str] = []
    spent = lambda: httpx.Response(429, json={"error": {"message": "quota exceeded"}})  # noqa: E731
    transport = _routing_transport({"k1": spent(), "k2": spent()}, seen)

    with pytest.raises(ProviderError) as ei:
        await providers.complete_gemini_json(MESSAGES, transport=transport)
    assert seen == ["k1", "k2"]
    assert "all 2 gemini keys exhausted" in str(ei.value)


@pytest.mark.asyncio
async def test_complete_json_does_not_rotate_on_400(monkeypatch):
    _use_keys(monkeypatch, gemini="k1", gemini_pool="k2")
    seen: list[str] = []
    transport = _routing_transport(
        {
            "k1": httpx.Response(400, json={"error": {"message": "unsupported response_format"}}),
            "k2": httpx.Response(200, json=JSON_BODY),
        },
        seen,
    )
    with pytest.raises(ProviderError):
        await providers.complete_gemini_json(MESSAGES, transport=transport)
    assert seen == ["k1"]


# --- error classification --------------------------------------------------
def _api_error(status: int, message: str) -> openai.APIStatusError:
    request = httpx.Request("POST", "https://example.invalid/chat/completions")
    response = httpx.Response(status, json={"error": {"message": message}}, request=request)
    return openai.APIStatusError(message, response=response, body=None)


def test_should_rotate_on_quota_wording_behind_an_odd_status():
    # Gemini reports some quota/key faults as 400, not 429.
    assert providers._should_rotate(_api_error(400, "Resource has been exhausted"))
    assert providers._should_rotate(_api_error(400, "API key not valid. Pass a valid API key."))


def test_should_not_rotate_on_a_plain_bad_request():
    assert not providers._should_rotate(_api_error(400, "invalid 'messages[0].role'"))


def test_should_not_rotate_on_server_error_or_transport_error():
    assert not providers._should_rotate(_api_error(500, "internal error"))
    assert not providers._should_rotate(httpx.ConnectError("no route"))


def test_should_rotate_through_a_wrapped_cause():
    # Instructor wraps provider errors rather than re-raising them.
    inner = _api_error(429, "quota exceeded")
    try:
        try:
            raise inner
        except openai.APIStatusError as e:
            raise RuntimeError("instructor gave up") from e
    except RuntimeError as wrapped:
        assert providers._should_rotate(wrapped)


# --- Instructor report path ------------------------------------------------
def _rate_limited() -> openai.RateLimitError:
    request = httpx.Request("POST", "https://example.invalid/chat/completions")
    response = httpx.Response(429, json={"error": {"message": "quota"}}, request=request)
    return openai.RateLimitError("quota", response=response, body=None)


class _Tiny(providers.BaseModel):
    headline: str


@pytest.mark.asyncio
async def test_generate_structured_rotates_to_next_key(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "spent")
    monkeypatch.setattr(settings, "groq_api_keys", "fresh")

    spent_client = AsyncMock()
    spent_client.chat.completions.create = AsyncMock(side_effect=_rate_limited())
    fresh = _Tiny(headline="PSX up")
    fresh_client = AsyncMock()
    fresh_client.chat.completions.create = AsyncMock(return_value=fresh)

    built: list[int] = []

    def _fake_build(provider, *, key_index, transport=None):
        built.append(key_index)
        return ReportClient(
            client=fresh_client, model="m", provider=provider, key_index=key_index
        )

    monkeypatch.setattr(providers, "_build_report_client", _fake_build)

    rc = ReportClient(client=spent_client, model="m", provider=PROVIDER_GROQ)
    result = await providers.generate_structured(rc, response_model=_Tiny, messages=MESSAGES)

    assert result == fresh
    assert built == [1]  # rebuilt on key 2 of the pool only


@pytest.mark.asyncio
async def test_generate_structured_raises_when_all_keys_exhausted(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "spent")
    monkeypatch.setattr(settings, "groq_api_keys", "also-spent")

    dead = AsyncMock()
    dead.chat.completions.create = AsyncMock(side_effect=_rate_limited())
    monkeypatch.setattr(
        providers,
        "_build_report_client",
        lambda provider, *, key_index, transport=None: ReportClient(
            client=dead, model="m", provider=provider, key_index=key_index
        ),
    )

    rc = ReportClient(client=dead, model="m", provider=PROVIDER_GROQ)
    with pytest.raises(ProviderError) as ei:
        await providers.generate_structured(rc, response_model=_Tiny, messages=MESSAGES)
    assert "all 2 groq keys exhausted" in str(ei.value)


@pytest.mark.asyncio
async def test_generate_structured_does_not_rotate_on_a_bad_request(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "k1")
    monkeypatch.setattr(settings, "groq_api_keys", "k2")

    bad = AsyncMock()
    bad.chat.completions.create = AsyncMock(side_effect=_api_error(400, "bad schema"))
    built: list[int] = []
    monkeypatch.setattr(
        providers,
        "_build_report_client",
        lambda provider, *, key_index, transport=None: built.append(key_index),
    )

    rc = ReportClient(client=bad, model="m", provider=PROVIDER_GROQ)
    with pytest.raises(ProviderError):
        await providers.generate_structured(rc, response_model=_Tiny, messages=MESSAGES)
    assert built == []  # never reached for the second key


def test_make_report_client_uses_the_first_key(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "groq_api_keys", "first,second")
    rc = providers.make_report_client(confidential=True)
    assert rc.provider == PROVIDER_GROQ
    assert rc.key_index == 0
    assert providers._report_api_key(PROVIDER_GROQ, 0) == "first"
    assert providers._report_api_key(PROVIDER_GROQ, 1) == "second"
    assert providers._report_api_key(PROVIDER_GROQ, 9) == ""


@pytest.mark.asyncio
async def test_complete_json_wraps_unexpected_errors_as_provider_error(monkeypatch):
    """Everything out of _complete_json must be a ProviderError.

    email_import/llm.py catches providers.ProviderError to fall back from
    Gemini to Groq. An exception of any other type (the SDK failing to decode a
    200 whose body is not JSON, say) escapes that handler, so the fallback
    never runs and the bank-email parse fails outright.
    """
    from app.config import settings
    from app.services.ai import providers

    monkeypatch.setattr(settings, "gemini_api_key", "k1")
    monkeypatch.setattr(settings, "gemini_api_keys", "")

    class _Boom:
        async def __aenter__(self):
            raise AttributeError("'NoneType' object has no attribute 'choices'")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(providers, "_client", lambda *a, **k: _Boom())

    with pytest.raises(providers.ProviderError):
        await providers.complete_gemini_json([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_make_report_client_exposes_a_closable_http_client(monkeypatch):
    """The pool behind a ReportClient must be reachable and actually close.

    AsyncOpenAI does not own the lifecycle of an injected httpx client, so
    without a handle every make_report_client() stranded a connection pool for
    the life of the process — once per report, plus once per key rotation.
    """
    from app.config import settings
    from app.services.ai import providers

    monkeypatch.setattr(settings, "groq_api_key", "k1")
    monkeypatch.setattr(settings, "groq_api_keys", "")

    rc = providers.make_report_client(confidential=True)
    assert rc.http_client is not None, "no handle on the httpx client — it cannot be closed"
    assert rc.http_client.is_closed is False

    await providers.aclose_report_client(rc)
    assert rc.http_client.is_closed is True


@pytest.mark.asyncio
async def test_aclose_report_client_tolerates_hand_built_clients():
    """Tests and future callers hand-build stand-ins; closing must not break them."""
    from types import SimpleNamespace

    from app.services.ai import providers

    await providers.aclose_report_client(SimpleNamespace(provider="groq", model="m"))


@pytest.mark.asyncio
async def test_rotation_closes_the_final_client_on_success(monkeypatch):
    """A successful rotation must not strand the client it rotated ONTO.

    _create_rotating closes each client it rotates AWAY from, but the last one
    is returned through and the caller's `finally` only owns the client it
    passed in. Without a `finally` here, every rotation leaked one httpx pool
    for the life of the process.
    """
    from app.config import settings
    from app.services.ai import providers

    monkeypatch.setattr(settings, "groq_api_key", "dead-key")
    monkeypatch.setattr(settings, "groq_api_keys", "good-key")

    built: list = []
    real_build = providers._build_report_client

    def _spy(provider, *, key_index, transport=None):
        rc = real_build(provider, key_index=key_index, transport=transport)
        built.append(rc)
        return rc

    monkeypatch.setattr(providers, "_build_report_client", _spy)

    class _Model(BaseModel):
        ok: bool

    calls = {"n": 0}

    async def _create(**_kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise openai.RateLimitError(
                "quota exceeded",
                response=httpx.Response(429, request=httpx.Request("POST", "http://x")),
                body=None,
            )
        return _Model(ok=True)

    first = providers.make_report_client(confidential=True)
    monkeypatch.setattr(type(first.client.chat.completions), "create", staticmethod(_create))

    result = await providers._create_rotating(
        first, response_model=_Model, messages=[{"role": "user", "content": "hi"}], max_retries=1
    )

    assert result.ok is True
    # built[0] is `first` itself (make_report_client goes through _build_report_client).
    # _create_rotating must NOT close that one — the caller owns it.
    rotated = [rc for rc in built if rc is not first]
    assert rotated, "expected a rotation to build a second client"
    for rc in rotated:
        assert rc.http_client.is_closed is True, "rotated-onto client was left open (leaked pool)"
    assert first.http_client.is_closed is False, "closed the caller's client — not ours to close"

    await providers.aclose_report_client(first)
