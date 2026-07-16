"""LLM provider clients on the OpenAI Python SDK.

Gemini (primary) and Groq (fallback) both speak OpenAI-compatible
/chat/completions, so one SDK serves both via base_url.

Three call shapes are supported:
- streaming (`stream_gemini`/`stream_groq`) — yields text deltas; used by the
  AI tutor.
- one-shot JSON (`complete_gemini_json`/`complete_groq_json`) — `stream=False`
  with response_format=json_object, returning raw JSON text; used by the
  bank-email parser, which needs a whole object rather than a token stream.
- structured reports (`make_report_client`/`generate_structured`) — Instructor
  wraps the same clients for Pydantic-validated output.

Notes:
- SDK retries are off (max_retries=0): the caller handles failover, and silent
  same-provider retries would fight it.
- Any provider being unusable raises ProviderError.
- The `transport` kwarg is only for test injection (httpx.MockTransport).

Key pools (multi-key fallback):
- Each provider takes a list of keys (singular `*_API_KEY` first, then the
  comma-separated `*_API_KEYS` pool — see config.merge_key_pool). All three call
  shapes walk that list, moving to the next key only when the current one is
  *individually* unusable: quota/rate-limit (429) or dead (401/403). Errors that
  every key would hit identically — a malformed request (400), a 5xx, a
  connect/timeout error — fail fast, because burning three more keys on them
  just multiplies latency by 4 and hides the real fault.
- When every key is unusable, ProviderError is raised, so the existing
  Gemini -> Groq failover at the caller (tutor/engine/email parser) still fires.
"""
from __future__ import annotations

import math
import os
import time
from typing import Any, AsyncIterator, NamedTuple, Optional, Type, TypeVar

import httpx
import instructor
import openai
import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings

log = structlog.get_logger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Kept for callers/tests that reference the full endpoint URLs.
GEMINI_URL = GEMINI_BASE_URL + "chat/completions"
GROQ_URL = GROQ_BASE_URL + "/chat/completions"


PROVIDER_GROQ = "groq"
PROVIDER_GEMINI = "gemini"

_PROVIDER_BASE_URL = {
    PROVIDER_GROQ: GROQ_BASE_URL,
    PROVIDER_GEMINI: GEMINI_BASE_URL,
}


class ProviderError(Exception):
    """Provider unusable: missing key, HTTP error, transport error."""


# ===========================================================================
# Key pools — rotate to a spare key when one key (not the provider) is dead
# ===========================================================================

# Statuses that condemn one key rather than the request: 429 = that key's
# free-tier quota/rate limit is spent; 401/403 = that key is invalid, revoked or
# lacks access. A dead key must not take the app down, so both advance.
_ROTATE_STATUS = frozenset({401, 403, 429})

# Belt-and-braces: providers are inconsistent about status codes for quota and
# bad keys (Gemini's OpenAI-compat layer reports an invalid key as 400
# INVALID_ARGUMENT, not 401). These markers are matched only against a real API
# status error's body, and each names the key/quota specifically — a genuinely
# malformed request does not say "exceeded your current quota".
_ROTATE_MARKERS = (
    "quota",
    "rate limit",
    "rate_limit",
    "ratelimit",
    "resource_exhausted",
    "resource has been exhausted",
    "too many requests",
    "api key not valid",
    "invalid api key",
    "api_key_invalid",
    "api key expired",
)

_PROVIDER_KEY_POOL = {
    PROVIDER_GROQ: lambda: settings.groq_api_key_pool,
    PROVIDER_GEMINI: lambda: settings.gemini_api_key_pool,
}


def _keys_for(provider: str) -> list[str]:
    """Ordered key pool for a provider. Read live (not cached at import) so env
    changes and test monkeypatching of `settings` both take effect."""
    try:
        getter = _PROVIDER_KEY_POOL[provider]
    except KeyError:
        raise ProviderError(f"unknown provider: {provider!r}") from None
    return getter()


def _condemns_key(exc: BaseException) -> bool:
    """True if this one exception means *this key* is unusable."""
    if isinstance(
        exc,
        (openai.RateLimitError, openai.AuthenticationError, openai.PermissionDeniedError),
    ):
        return True
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status in _ROTATE_STATUS:
        return True
    if isinstance(exc, openai.APIStatusError):
        text = str(exc).lower()
        return any(marker in text for marker in _ROTATE_MARKERS)
    return False


def _should_rotate(exc: BaseException) -> bool:
    """Whether to try the next key. Walks the cause chain because Instructor
    wraps provider errors (InstructorRetryException) rather than re-raising."""
    seen: BaseException | None = exc
    for _ in range(5):
        if seen is None:
            break
        if _condemns_key(seen):
            return True
        seen = seen.__cause__ or seen.__context__
    return False


def _exhausted(provider: str, count: int, last: BaseException | None) -> ProviderError:
    return ProviderError(f"all {count} {provider} keys exhausted: {last}")


# One client per (base_url, api_key), reused for the process lifetime.
#
# A fresh AsyncOpenAI + httpx.AsyncClient per call means a fresh TCP + TLS
# handshake per call: measured at 1259ms vs 827ms for a reused client — 432ms
# (1.5x) of pure setup on every request. Search feels it worst, since each
# keystroke-driven query pays it just to embed a few words.
#
# Safe to share: httpx.AsyncClient is documented as safe for concurrent
# requests, and one entry per key means rotation just selects a different
# cached client rather than invalidating anything.
_CLIENTS: dict[tuple[str, str], AsyncOpenAI] = {}


def _client(
    base_url: str,
    api_key: str,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncOpenAI:
    """A pooled client. Callers must NOT close it — see close_llm_clients."""
    if transport is not None:
        # Test injection: each case passes its own MockTransport, so caching
        # would serve one test's mock to the next.
        return AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            max_retries=0,
            http_client=httpx.AsyncClient(
                timeout=settings.ai_tutor_request_timeout_s, transport=transport
            ),
        )
    cached = _CLIENTS.get((base_url, api_key))
    if cached is None:
        cached = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            max_retries=0,
            http_client=httpx.AsyncClient(
                timeout=settings.ai_tutor_request_timeout_s
            ),
        )
        _CLIENTS[(base_url, api_key)] = cached
    return cached


async def close_llm_clients() -> None:
    """Release the pooled clients. Wired into the app lifespan."""
    for client in list(_CLIENTS.values()):
        try:
            await client.close()
        except Exception:  # noqa: BLE001 - shutdown must not raise
            log.warning("llm_client_close_failed", exc_info=True)
    _CLIENTS.clear()


async def _stream_chat(
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncIterator[str]:
    """Stream text deltas, rotating keys on quota/auth failures.

    Streaming rotation is deliberately limited to *before the first token is
    yielded*. Once a delta has gone out, the caller (SSE -> browser) has already
    rendered it; a retry on a fresh key restarts generation from scratch, and
    the user would see the first sentence twice with no way to un-send it. The
    provider cannot resume a stream mid-way, so there is no correct retry here —
    we re-raise and let the caller's provider-level failover decide, matching
    the existing no-fallback-mid-stream rule in tutor.stream_reply.

    Before the first token nothing is committed, so rotating is free. A 429 on a
    spent key surfaces at the `create()` await (the response status arrives with
    the headers, ahead of any SSE body), which is exactly where the common case
    lands.
    """
    base_url = _PROVIDER_BASE_URL[provider]
    keys = _keys_for(provider)
    if not keys:
        raise ProviderError(f"no API key configured for {base_url}")

    last: Optional[BaseException] = None
    for index, api_key in enumerate(keys):
        emitted = False
        try:
            client = _client(base_url, api_key, transport)
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    emitted = True
                    yield delta
            return
        except (openai.OpenAIError, httpx.HTTPError) as e:
            last = e
            if emitted or not _should_rotate(e):
                raise ProviderError(f"{base_url}: {e}") from e
            log.warning(
                "llm_key_rotated",
                provider=provider,
                key_index=index,
                key_count=len(keys),
                call="stream",
                error=type(e).__name__,
            )
    raise _exhausted(provider, len(keys), last) from last


def stream_gemini(
    messages: list[dict[str, str]],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncIterator[str]:
    return _stream_chat(
        PROVIDER_GEMINI,
        settings.ai_tutor_model_primary,
        messages,
        transport,
    )


def stream_groq(
    messages: list[dict[str, str]],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncIterator[str]:
    return _stream_chat(
        PROVIDER_GROQ,
        settings.ai_tutor_model_fallback,
        messages,
        transport,
    )


# ===========================================================================
# One-shot JSON completions — used by the bank-email transaction parser
# ===========================================================================
#
# Ported onto the OpenAI SDK during the dev merge. `dev` implemented these on
# raw httpx before this module was refactored to the SDK; keeping that version
# would have meant two transports, two error-mapping paths and two timeout
# settings in one file. Signatures are unchanged, so
# services/email_import/llm.py needs no edit.


async def _complete_json(
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> str:
    """One-shot completion constrained to a JSON object. Returns raw JSON text.

    Nothing is handed to the caller until the whole object is in hand, so — unlike
    the streaming path — every key in the pool can be tried freely."""
    base_url = _PROVIDER_BASE_URL[provider]
    keys = _keys_for(provider)
    if not keys:
        raise ProviderError(f"no API key configured for {base_url}")

    last: Optional[BaseException] = None
    for index, api_key in enumerate(keys):
        try:
            client = _client(base_url, api_key, transport)
            res = await client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                stream=False,
                response_format={"type": "json_object"},
            )
        except (openai.OpenAIError, httpx.HTTPError) as e:
            last = e
            if not _should_rotate(e):
                raise ProviderError(f"{base_url}: {e}") from e
            log.warning(
                "llm_key_rotated",
                provider=provider,
                key_index=index,
                key_count=len(keys),
                call="complete_json",
                error=type(e).__name__,
            )
            continue
        except Exception as e:
            # Everything leaving this function must be a ProviderError:
            # email_import/llm.py keys its Gemini->Groq fallback on that type,
            # so any other exception (e.g. the SDK failing to decode a 200
            # whose body is not JSON) skips the fallback entirely and fails the
            # whole parse instead of trying the next provider.
            raise ProviderError(f"{base_url}: {type(e).__name__}: {e}") from e

        # A well-formed but empty answer is the model's fault, not the key's:
        # another key would return the same thing, so fail instead of rotating.
        if not res.choices:
            raise ProviderError(f"{base_url}: no choices in response")
        content = res.choices[0].message.content
        if not content:
            raise ProviderError(f"{base_url}: empty completion")
        return content
    raise _exhausted(provider, len(keys), last) from last


async def complete_gemini_json(
    messages: list[dict[str, str]],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> str:
    return await _complete_json(
        PROVIDER_GEMINI,
        settings.ai_tutor_model_primary,
        messages,
        transport,
    )


async def complete_groq_json(
    messages: list[dict[str, str]],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> str:
    return await _complete_json(
        PROVIDER_GROQ,
        settings.ai_tutor_model_fallback,
        messages,
        transport,
    )


# ===========================================================================
# Embeddings — Gemini only (Groq has no embeddings API)
# ===========================================================================
#
# Used by LearnHub RAG (corpus indexing + query embedding). There is no
# provider fallback for this call shape — only key-pool rotation — because
# vectors from different models live in different spaces: a Groq-embedded
# query could not be compared against a Gemini-embedded corpus anyway.


def _fit_embedding(vec: list[float], dim: int) -> list[float]:
    """Truncate a vector to `dim` and L2-normalize it.

    Gemini's OpenAI-compat layer accepts a `dimensions` param but it is
    undocumented and sometimes ignored, returning the model's native 3072 dims.
    gemini-embedding-001 is MRL-trained, so the first `dim` components are a
    valid embedding on their own — but only after re-normalizing, because a
    truncated unit vector is no longer unit length. Applied unconditionally:
    re-normalizing an already-unit vector is a no-op, so there is no
    "already correct" fast path to get wrong."""
    if len(vec) < dim:
        raise ProviderError(f"embedding has {len(vec)} dims, need at least {dim}")
    fitted = vec[:dim]
    norm = math.sqrt(sum(x * x for x in fitted))
    if norm == 0.0:
        raise ProviderError("embedding has zero norm, cannot normalize")
    return [x / norm for x in fitted]


async def embed_gemini(
    texts: list[str],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> list[list[float]]:
    """Embed `texts`, one vector per text, each exactly settings.ai_embedding_dim
    long and L2-normalized. Walks the Gemini key pool exactly like
    _complete_json: nothing is handed to the caller until the whole batch is in
    hand, so every key can be tried freely."""
    if not texts:
        return []

    keys = _keys_for(PROVIDER_GEMINI)
    if not keys:
        raise ProviderError(f"no API key configured for {GEMINI_BASE_URL}")

    last: Optional[BaseException] = None
    for index, api_key in enumerate(keys):
        try:
            client = _client(GEMINI_BASE_URL, api_key, transport)
            res = await client.embeddings.create(
                model=settings.ai_embedding_model,
                input=texts,
                dimensions=settings.ai_embedding_dim,
            )
        except (openai.OpenAIError, httpx.HTTPError) as e:
            last = e
            if not _should_rotate(e):
                raise ProviderError(f"{GEMINI_BASE_URL}: {e}") from e
            log.warning(
                "llm_key_rotated",
                provider=PROVIDER_GEMINI,
                key_index=index,
                key_count=len(keys),
                call="embeddings",
                error=type(e).__name__,
            )
            continue
        except Exception as e:
            # Everything leaving this function must be a ProviderError, same
            # rule as _complete_json: callers key their handling on that type.
            raise ProviderError(f"{GEMINI_BASE_URL}: {type(e).__name__}: {e}") from e

        # A short answer is the model's fault, not the key's: another key would
        # return the same thing, so fail instead of rotating.
        if len(res.data) != len(texts):
            raise ProviderError(
                f"{GEMINI_BASE_URL}: {len(res.data)} embeddings for {len(texts)} inputs"
            )
        # Gemini's compat layer returns `index: null` on every item, so an
        # unconditional sort crashes with TypeError (seen live). Sort only when
        # every index is present; otherwise response order IS input order per
        # the OpenAI contract.
        if all(d.index is not None for d in res.data):
            data = sorted(res.data, key=lambda d: d.index)
        else:
            data = list(res.data)
        return [
            _fit_embedding(list(d.embedding), settings.ai_embedding_dim) for d in data
        ]
    raise _exhausted(PROVIDER_GEMINI, len(keys), last) from last


# ===========================================================================
# Report clients — Instructor structured output + privacy-driven model routing
# ===========================================================================
#
# Reports return complete, Pydantic-validated JSON (not a token stream).
# Instructor wraps the same OpenAI-compatible clients above to give us schema
# validation + self-correcting retries, and drives both providers.
#
# Instructor mode per provider (swappable): Groq uses Mode.TOOLS (its Llama
# models have reliable native tool calling); Gemini uses Mode.JSON (its
# OpenAI-compat tool calling is flakier than JSON/response_format mode).
#
# Model names + routing come from env, so switching to a paid/ZDR tier is a
# config change, not a rewrite.

# PROVIDER_GROQ / PROVIDER_GEMINI / _PROVIDER_BASE_URL are defined at the top of
# this module — the key-pool machinery needs them too.

# The free Gemini AI Studio tier trains on prompts and allows human review, so
# confidential per-user data must NEVER route here. A future paid Gemini tier
# would be a different provider name and would not be in this set.
_GEMINI_FREE_PROVIDERS = frozenset({PROVIDER_GEMINI})

_INSTRUCTOR_MODE = {
    PROVIDER_GROQ: instructor.Mode.TOOLS,
    PROVIDER_GEMINI: instructor.Mode.JSON,
}

# AsyncOpenAI rejects an empty api_key at construction. We build clients eagerly
# (routing must work without live keys), so fall back to a sentinel; a real call
# with no key then surfaces a normal auth error.
_MISSING_KEY = "not-configured"

T = TypeVar("T", bound=BaseModel)


class ReportClient(NamedTuple):
    """What the engine needs to generate one structured report: the
    Instructor-patched client, the resolved model name, and the provider.

    `key_index` and `transport` are what generate_structured needs to rebuild
    this client on the next key of the pool; both default so existing callers
    (and tests) that construct a ReportClient by hand keep working."""

    client: instructor.AsyncInstructor
    model: str
    provider: str
    key_index: int = 0
    transport: Optional[httpx.AsyncBaseTransport] = None
    # The httpx client behind `client`, held so it can actually be closed.
    # AsyncOpenAI does not own its lifecycle when one is injected, so without
    # this handle every build leaked its connection pool. Optional so
    # hand-built ReportClients (tests) keep working.
    http_client: Optional[httpx.AsyncClient] = None


def _report_provider(*, confidential: bool) -> str:
    """Which provider a report routes to, env-driven. Confidential per-user
    reports default to Groq (doesn't train on inputs); shared/no-PII reports
    default to the free Gemini tier. Both overridable via env."""
    if confidential:
        return os.getenv("AI_REPORT_CONFIDENTIAL_PROVIDER", PROVIDER_GROQ).strip().lower()
    return os.getenv("AI_REPORT_SHARED_PROVIDER", PROVIDER_GEMINI).strip().lower()


def _report_model(provider: str) -> str:
    """Model name for a provider — env override, else free-tier default."""
    if provider == PROVIDER_GROQ:
        return os.getenv("AI_REPORT_MODEL_GROQ", settings.ai_tutor_model_fallback)
    if provider == PROVIDER_GEMINI:
        return os.getenv("AI_REPORT_MODEL_GEMINI", settings.ai_tutor_model_primary)
    raise ProviderError(f"unknown report provider: {provider!r}")


def _report_api_key(provider: str, key_index: int = 0) -> str:
    """The key at `key_index` in the provider's pool, or "" past the end."""
    keys = _keys_for(provider)
    return keys[key_index] if key_index < len(keys) else ""


def make_report_client(
    *,
    confidential: bool,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> ReportClient:
    """Build the Instructor-wrapped client + model for a report surface.
    confidential=True -> Groq; confidential=False -> a free tier.

    Hard privacy guard: if config would route confidential data to the free
    Gemini AI Studio tier, raise ProviderError — that tier trains on prompts and
    allows human review, so confidential data must never go there."""
    provider = _report_provider(confidential=confidential)

    if provider not in _PROVIDER_BASE_URL:
        raise ProviderError(f"unknown report provider: {provider!r}")

    if confidential and provider in _GEMINI_FREE_PROVIDERS:
        raise ProviderError(
            "refusing to route confidential per-user report data to the free "
            "Gemini AI Studio tier: it trains on prompts and permits human "
            "review (spec §4.5). Route confidential reports to Groq (or a paid "
            "ZDR tier)."
        )

    return _build_report_client(provider, key_index=0, transport=transport)


def _build_report_client(
    provider: str,
    *,
    key_index: int,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> ReportClient:
    """Instructor client for one provider pinned to one key of its pool."""
    api_key = _report_api_key(provider, key_index) or _MISSING_KEY
    http = httpx.AsyncClient(
        timeout=settings.ai_tutor_request_timeout_s, transport=transport
    )
    raw = AsyncOpenAI(
        base_url=_PROVIDER_BASE_URL[provider],
        api_key=api_key,
        max_retries=0,
        http_client=http,
    )
    client = instructor.from_openai(raw, mode=_INSTRUCTOR_MODE[provider])
    return ReportClient(
        client=client,
        model=_report_model(provider),
        provider=provider,
        key_index=key_index,
        transport=transport,
        http_client=http,
    )


async def aclose_report_client(report_client: ReportClient) -> None:
    """Release the connection pool behind a ReportClient.

    Every make_report_client() and every key rotation builds an
    httpx.AsyncClient; nothing else closes them, so each report generation
    leaked one for the process lifetime.

    getattr, not attribute access: callers hand-build stand-ins for this
    (tests pass a SimpleNamespace), and closing a client must never be the
    thing that breaks them.
    """
    http_client = getattr(report_client, "http_client", None)
    if http_client is not None:
        await http_client.aclose()


def log_report_generation(**fields: Any) -> None:
    """One structlog line per report generation, with whatever fields the caller
    has. A thin patchable seam so the generate helper and the engine both log
    through one place."""
    log.info("ai_report_generation", **fields)


async def generate_structured(
    report_client: ReportClient,
    *,
    response_model: Type[T],
    messages: list[dict[str, str]],
    report_type: str = "",
    lang: str = "en",
    max_retries: int = 2,
    **kwargs: Any,
) -> T:
    """Generate + validate a report against a Pydantic schema via Instructor.
    Instructor guarantees shape (self-correcting up to max_retries); the engine
    still runs numeric verification on top.

    A spent or dead key rotates to the next one in the provider's pool (the
    whole report is rebuilt from scratch, which is safe: nothing is emitted
    until the object validates). max_retries is Instructor's *schema* retry
    budget and is unrelated — it applies afresh to each key."""
    started = time.perf_counter()
    tokens: Optional[int] = None
    try:
        result: T = await _create_rotating(
            report_client,
            response_model=response_model,
            messages=messages,
            max_retries=max_retries,
            **kwargs,
        )
    finally:
        latency_ms = int((time.perf_counter() - started) * 1000)

    # Instructor attaches the raw completion (with usage) when available.
    raw = getattr(result, "_raw_response", None)
    usage = getattr(raw, "usage", None)
    if usage is not None:
        tokens = getattr(usage, "total_tokens", None)

    log_report_generation(
        report_type=report_type,
        provider=report_client.provider,
        model=report_client.model,
        lang=lang,
        latency_ms=latency_ms,
        tokens=tokens,
    )
    return result


async def _create_rotating(
    report_client: ReportClient,
    *,
    response_model: Type[T],
    messages: list[dict[str, str]],
    max_retries: int,
    **kwargs: Any,
) -> T:
    """One structured generation, walking the provider's key pool on quota/auth
    failures. Instructor wraps provider errors, so classification looks through
    the cause chain (see _should_rotate)."""
    provider = report_client.provider
    try:
        keys = _keys_for(provider)
    except ProviderError:
        # A hand-built ReportClient for an unknown provider (tests, future
        # providers): honour it as a single-shot client, no rotation.
        keys = []
    total = max(len(keys), 1)

    rc = report_client
    last: Optional[BaseException] = None
    try:
        for index in range(report_client.key_index, total):
            if index != report_client.key_index:
                # The previous key's client is dead to us — close it rather than
                # stranding its pool for the life of the process.
                if rc is not report_client:
                    await aclose_report_client(rc)
                rc = _build_report_client(provider, key_index=index, transport=report_client.transport)
            try:
                return await rc.client.chat.completions.create(  # type: ignore[no-any-return]
                    model=rc.model,
                    response_model=response_model,
                    messages=messages,  # type: ignore[arg-type]
                    max_retries=max_retries,
                    **kwargs,
                )
            except Exception as e:
                last = e
                if not _should_rotate(e):
                    if isinstance(e, openai.OpenAIError):
                        raise ProviderError(f"{provider}: {e}") from e
                    raise
                log.warning(
                    "llm_key_rotated",
                    provider=provider,
                    key_index=index,
                    key_count=total,
                    call="report",
                    error=type(e).__name__,
                )
        raise _exhausted(provider, total, last) from last
    finally:
        # Close the LAST client we built, on every exit path — success, raise,
        # or exhausted. The in-loop close above only reaches the intermediates,
        # and the caller's `finally` owns solely the client it passed in, so
        # without this every rotation strands one pool. Safe after `return`:
        # the response is fully materialised (non-streaming), so nothing reads
        # from the transport afterwards.
        if rc is not report_client:
            await aclose_report_client(rc)
