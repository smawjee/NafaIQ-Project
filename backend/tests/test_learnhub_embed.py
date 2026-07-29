"""LearnHub embedding provider (embed_gemini), tested with httpx.MockTransport.

No network — the `transport=` kwarg providers.* already expose for test
injection is the seam here too. Keys are fake placeholders.

Two production regressions are pinned in this module:
  * Gemini's OpenAI-compat layer returns `index: null` on every embedding item,
    so an unconditional sort-by-index crashes with TypeError (observed live).
  * The compat layer's `dimensions` request param is undocumented and may be
    ignored, returning the model's native 3072 dims — vectors must be truncated
    to settings.ai_embedding_dim and re-normalized unconditionally.
"""
from __future__ import annotations

import math

import httpx
import pytest

from app.config import settings
from app.services.ai import providers
from app.services.ai.providers import ProviderError

TEXTS = ["what is the kse-100?", "define dividend yield"]


@pytest.fixture(autouse=True)
def _isolate_key_pools(monkeypatch):
    """Blank the multi-key pool vars for every test in this module.

    providers.py tries GEMINI_API_KEY first, then every key in GEMINI_API_KEYS.
    Any developer or CI box with those populated would make these tests exercise
    the real pool: the 429 test would rotate through live production keys
    instead of testing rotation, and the no-keys test could not reach the
    no-keys branch at all. Each test opts back in to exactly the keys it means
    to test.
    """
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_keys", "")
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "groq_api_keys", "")


def _use_keys(monkeypatch, *, gemini: str = "", gemini_pool: str = "") -> None:
    monkeypatch.setattr(settings, "gemini_api_key", gemini)
    monkeypatch.setattr(settings, "gemini_api_keys", gemini_pool)


def _key_of(request: httpx.Request) -> str:
    return request.headers.get("authorization", "").removeprefix("Bearer ")


def _embed_body(vectors: list[list[float]], indices: list | None = None) -> dict:
    """OpenAI embeddings response JSON. `indices=None` -> ascending 0..n-1;
    pass an explicit list (may contain None) to model the Gemini compat layer."""
    if indices is None:
        indices = list(range(len(vectors)))
    return {
        "object": "list",
        "model": "gemini-embedding-001",
        "data": [
            {"object": "embedding", "index": ix, "embedding": vec}
            for ix, vec in zip(indices, vectors)
        ],
        "usage": {"prompt_tokens": 8, "total_tokens": 8},
    }


def _routing_transport(responses: dict[str, httpx.Response], seen: list[str]) -> httpx.MockTransport:
    """Reply per-key, recording which keys were actually tried and in what order."""

    def handler(request: httpx.Request) -> httpx.Response:
        key = _key_of(request)
        seen.append(key)
        return responses[key]

    return httpx.MockTransport(handler)


def _norm(vec: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vec))


def _basis(dim: int, hot: int) -> list[float]:
    """Unit basis vector — distinguishable even after truncate + normalize."""
    vec = [0.0] * dim
    vec[hot] = 1.0
    return vec


# --- fit: truncate + normalize ----------------------------------------------
@pytest.mark.asyncio
async def test_embed_truncates_and_normalizes(monkeypatch):
    # The compat layer may ignore `dimensions` and return the native 3072 dims,
    # unnormalized. Output must still be exactly ai_embedding_dim long and unit.
    _use_keys(monkeypatch, gemini="k1")
    seen: list[str] = []
    native = [[3.0] * 3072, [0.25] * 3072]
    transport = _routing_transport({"k1": httpx.Response(200, json=_embed_body(native))}, seen)

    out = await providers.embed_gemini(TEXTS, transport=transport)

    assert len(out) == 2
    for vec in out:
        assert len(vec) == settings.ai_embedding_dim
        assert abs(_norm(vec) - 1.0) < 1e-6
    assert seen == ["k1"]


def test_fit_embedding_rejects_short_vectors():
    with pytest.raises(ProviderError):
        providers._fit_embedding([0.1] * 10, 768)


def test_fit_embedding_rejects_zero_norm():
    with pytest.raises(ProviderError):
        providers._fit_embedding([0.0] * 768, 768)


# --- null-index regression (the live crash) ---------------------------------
@pytest.mark.asyncio
async def test_embed_null_index_preserves_order(monkeypatch):
    # Gemini's compat layer returns index: null on EVERY item; an unconditional
    # sorted(..., key=lambda d: d.index) raised TypeError in production. When
    # any index is null, response order (== input order per the OpenAI
    # contract) must be preserved.
    _use_keys(monkeypatch, gemini="k1")
    texts = ["a", "b", "c"]
    dim = settings.ai_embedding_dim
    vectors = [_basis(dim, 0), _basis(dim, 1), _basis(dim, 2)]  # distinct per input
    seen: list[str] = []
    transport = _routing_transport(
        {"k1": httpx.Response(200, json=_embed_body(vectors, indices=[None, None, None]))},
        seen,
    )

    out = await providers.embed_gemini(texts, transport=transport)

    assert len(out) == 3
    for i, vec in enumerate(out):
        assert vec[i] == pytest.approx(1.0), f"vector {i} out of order"


@pytest.mark.asyncio
async def test_embed_sorts_by_index_when_all_present(monkeypatch):
    # The flip side of the rule: when every index IS non-null, honour it —
    # a provider that reorders items must not corrupt text->vector pairing.
    _use_keys(monkeypatch, gemini="k1")
    dim = settings.ai_embedding_dim
    # response arrives out of order: item for input 1 first, then input 0
    vectors = [_basis(dim, 1), _basis(dim, 0)]
    transport = _routing_transport(
        {"k1": httpx.Response(200, json=_embed_body(vectors, indices=[1, 0]))}, []
    )

    out = await providers.embed_gemini(TEXTS, transport=transport)

    assert out[0][0] == pytest.approx(1.0)
    assert out[1][1] == pytest.approx(1.0)


# --- key pool ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_embed_rotates_on_429(monkeypatch):
    _use_keys(monkeypatch, gemini="spent", gemini_pool="fresh")
    dim = settings.ai_embedding_dim
    seen: list[str] = []
    transport = _routing_transport(
        {
            "spent": httpx.Response(429, json={"error": {"message": "quota exceeded"}}),
            "fresh": httpx.Response(200, json=_embed_body([_basis(dim, 0), _basis(dim, 1)])),
        },
        seen,
    )

    out = await providers.embed_gemini(TEXTS, transport=transport)

    assert len(out) == 2
    assert seen == ["spent", "fresh"]  # two requests, each under its own key


@pytest.mark.asyncio
async def test_embed_raises_when_all_keys_exhausted(monkeypatch):
    _use_keys(monkeypatch, gemini="k1", gemini_pool="k2")
    seen: list[str] = []
    spent = lambda: httpx.Response(429, json={"error": {"message": "quota exceeded"}})  # noqa: E731
    transport = _routing_transport({"k1": spent(), "k2": spent()}, seen)

    with pytest.raises(ProviderError) as ei:
        await providers.embed_gemini(TEXTS, transport=transport)

    assert seen == ["k1", "k2"]
    assert "all 2 gemini keys exhausted" in str(ei.value)


@pytest.mark.asyncio
async def test_embed_with_no_keys_raises(monkeypatch):
    _use_keys(monkeypatch, gemini="", gemini_pool="")
    with pytest.raises(ProviderError) as ei:
        await providers.embed_gemini(TEXTS, transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    assert "no API key configured" in str(ei.value)


# --- response validation -----------------------------------------------------
@pytest.mark.asyncio
async def test_embed_count_mismatch_raises_without_rotating(monkeypatch):
    # A short answer is the model's fault, not the key's: another key would
    # return the same thing, so fail instead of burning the spare.
    _use_keys(monkeypatch, gemini="k1", gemini_pool="k2")
    dim = settings.ai_embedding_dim
    seen: list[str] = []
    transport = _routing_transport(
        {
            "k1": httpx.Response(200, json=_embed_body([_basis(dim, 0)])),  # 1 vector for 2 texts
            "k2": httpx.Response(200, json=_embed_body([_basis(dim, 0), _basis(dim, 1)])),
        },
        seen,
    )

    with pytest.raises(ProviderError):
        await providers.embed_gemini(TEXTS, transport=transport)
    assert seen == ["k1"]


@pytest.mark.asyncio
async def test_embed_empty_input_returns_empty_without_calls(monkeypatch):
    _use_keys(monkeypatch, gemini="k1")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=_embed_body([]))

    out = await providers.embed_gemini([], transport=httpx.MockTransport(handler))

    assert out == []
    assert calls["n"] == 0


# --------------------------------------------------------------------------- #
# Ingest freshness — the rule that decides what gets (re-)embedded.            #
#                                                                              #
# Every miss here is silent: ingest prints "unchanged", exits 0, and the chunk #
# is simply not retrievable. Two of the three clauses below were real bugs.    #
# --------------------------------------------------------------------------- #
def _load_is_fresh():
    """scripts/ is not a package — load the module by path."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "data" / "ingest_learnhub.py"
    spec = importlib.util.spec_from_file_location("ingest_learnhub", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.is_fresh


_CHUNK = {"source_id": "gloss:bull-market", "content_hash": "abc123"}
_MODEL = "gemini-embedding-001"


def test_unchanged_active_chunk_is_fresh():
    """The idempotency guarantee: a re-run on an unchanged corpus embeds nothing."""
    existing = {"gloss:bull-market": ("abc123", _MODEL, True)}
    assert _load_is_fresh()(_CHUNK, existing, _MODEL) is True


def test_changed_content_is_not_fresh():
    existing = {"gloss:bull-market": ("OLD-HASH", _MODEL, True)}
    assert _load_is_fresh()(_CHUNK, existing, _MODEL) is False


def test_a_new_chunk_is_not_fresh():
    assert _load_is_fresh()(_CHUNK, {}, _MODEL) is False


def test_a_different_embedding_model_is_not_fresh():
    """retrieval._vector_arm filters on `embedding_model = :model`, so a row
    embedded by another model is dead weight — changing AI_EMBEDDING_MODEL must
    re-embed, not report 'unchanged' and leave the vector arm empty."""
    existing = {"gloss:bull-market": ("abc123", "some-older-model", True)}
    assert _load_is_fresh()(_CHUNK, existing, _MODEL) is False


def test_a_soft_deleted_chunk_is_not_fresh():
    """A chunk that left the corpus and came back. The soft delete leaves the
    hash intact, so on content alone this looks unchanged — and the row would
    stay is_active=false forever, invisible to retrieval, while ingest reported
    success. Re-running ingest is the recovery the soft delete promises; that
    promise IS this assertion."""
    existing = {"gloss:bull-market": ("abc123", _MODEL, False)}
    assert _load_is_fresh()(_CHUNK, existing, _MODEL) is False
