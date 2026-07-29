"""LearnHub hybrid retrieval — fusion, degradation, and the API contract.

No DB, no network: the two SQL arms are monkeypatched and the embedder is
faked. What these pin is the behaviour the UI depends on — that a failure
anywhere degrades to fewer/no results rather than an error, because search
feeds a discovery surface where "no results" is a normal state and a 500 is not.
"""
from __future__ import annotations

import asyncio

import pytest

from app.config import settings
from app.services.learnhub import retrieval


def _row(id_: int, *, source_type="lesson_section", lesson_id="dividends",
         section_id="what-is", title="Understanding Dividends",
         heading="What is a dividend?", ur=None, distance=0.3):
    return {
        "id": id_,
        "source_type": source_type,
        "source_id": f"sec:{lesson_id}:{section_id}",
        "lesson_id": lesson_id,
        "section_id": section_id,
        "title": title,
        "heading": heading,
        "text_en": f"{title} — {heading}\n\nA dividend is a share of profit paid to shareholders.",
        "text_ur": ur,
        "distance": distance,
    }


def _patch_arms(monkeypatch, vector_rows, fts_rows):
    async def _vec(query, clause, params):
        return vector_rows

    async def _fts(query, clause, params):
        return fts_rows

    monkeypatch.setattr(retrieval, "_vector_arm", _vec)
    monkeypatch.setattr(retrieval, "_fts_arm", _fts)


# --------------------------------------------------------------------------- #
# Fusion                                                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_chunk_found_by_both_arms_outranks_either_arms_top_hit(monkeypatch):
    """The point of RRF: agreement between arms beats a single arm's #1."""
    both = _row(1, section_id="both")
    vec_only = _row(2, section_id="vec")
    fts_only = _row(3, section_id="fts")
    _patch_arms(monkeypatch, [vec_only, both], [fts_only, both])

    out = await retrieval.search("dividend", limit=3)

    assert out[0]["section_id"] == "both"


@pytest.mark.asyncio
async def test_duplicate_across_arms_is_deduped(monkeypatch):
    row = _row(1)
    _patch_arms(monkeypatch, [row], [row])

    out = await retrieval.search("dividend", limit=5)

    assert len(out) == 1, "same chunk returned twice"


@pytest.mark.asyncio
async def test_limit_is_respected(monkeypatch):
    rows = [_row(i, section_id=f"s{i}") for i in range(10)]
    _patch_arms(monkeypatch, rows, [])

    assert len(await retrieval.search("dividend", limit=3)) == 3


# --------------------------------------------------------------------------- #
# Degradation — the invariant the UI relies on                                #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_embedding_failure_degrades_to_fts_only(monkeypatch):
    """Groq has no embeddings API, so there is no provider to rotate to —
    keyword search IS the fallback. It must still return results."""
    from app.services.ai.providers import ProviderError

    async def _boom(texts):
        raise ProviderError("all gemini keys exhausted")

    monkeypatch.setattr(retrieval, "embed_gemini", _boom)

    async def _fts(query, clause, params):
        return [_row(1)]

    monkeypatch.setattr(retrieval, "_fts_arm", _fts)

    async def _connect_unused():  # pragma: no cover - the vector arm must bail first
        raise AssertionError("vector arm queried the DB despite no embedding")

    out = await retrieval.search("dividend", limit=5)
    assert len(out) == 1, "FTS-only degradation returned nothing"


@pytest.mark.asyncio
async def test_db_failure_returns_empty_not_raise(monkeypatch):
    async def _boom(query, clause, params):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(retrieval, "_vector_arm", _boom)
    monkeypatch.setattr(retrieval, "_fts_arm", _boom)

    assert await retrieval.search("dividend") == []


@pytest.mark.asyncio
async def test_timeout_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "learnhub_retrieval_timeout_s", 0.05)

    async def _hang(query, clause, params):
        await asyncio.sleep(1.0)
        return []

    monkeypatch.setattr(retrieval, "_vector_arm", _hang)
    monkeypatch.setattr(retrieval, "_fts_arm", _hang)

    assert await retrieval.search("dividend") == []


@pytest.mark.asyncio
async def test_short_query_short_circuits(monkeypatch):
    async def _never(query, clause, params):  # pragma: no cover
        raise AssertionError("queried the DB for a 1-char query")

    monkeypatch.setattr(retrieval, "_vector_arm", _never)
    monkeypatch.setattr(retrieval, "_fts_arm", _never)

    assert await retrieval.search("a") == []
    assert await retrieval.search("   ") == []


# --------------------------------------------------------------------------- #
# Mode filters                                                                #
# --------------------------------------------------------------------------- #
def test_mode_clause_glossary_filters_source_type():
    clause, params = retrieval._mode_clause(retrieval.MODE_GLOSSARY, None)
    assert "source_type = 'glossary_term'" in clause
    assert params == {}


def test_mode_clause_lesson_binds_lesson_id():
    clause, params = retrieval._mode_clause(retrieval.MODE_LESSON, "dividends")
    assert "lesson_id = :lesson_id" in clause
    assert params == {"lesson_id": "dividends"}


def test_mode_clause_all_is_unfiltered():
    assert retrieval._mode_clause(retrieval.MODE_ALL, None) == ("", {})


def test_lesson_mode_without_lesson_id_does_not_emit_an_unbound_param():
    """A bound :lesson_id with no value would raise at execute time."""
    clause, params = retrieval._mode_clause(retrieval.MODE_LESSON, None)
    assert clause == "" and params == {}


# --------------------------------------------------------------------------- #
# Snippets — the Urdu rule                                                     #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_snippet_strips_the_context_prefix(monkeypatch):
    """Chunks carry a 'Lesson — Section' prefix for standalone retrieval; the
    UI already renders title/heading, so repeating them wastes the snippet."""
    _patch_arms(monkeypatch, [_row(1)], [])

    out = await retrieval.search("dividend")

    assert out[0]["snippet_en"].startswith("A dividend is a share of profit")
    assert "Understanding Dividends —" not in out[0]["snippet_en"]


@pytest.mark.asyncio
async def test_snippet_ur_is_null_when_no_translation(monkeypatch):
    """text_ur is all-or-nothing from the exporter; None must surface as None
    so the client falls back to the English snippet rather than showing blank."""
    _patch_arms(monkeypatch, [_row(1, ur=None)], [])

    out = await retrieval.search("dividend")

    assert out[0]["snippet_ur"] is None


@pytest.mark.asyncio
async def test_snippet_ur_returned_when_present(monkeypatch):
    _patch_arms(monkeypatch, [_row(1, ur="عنوان — ذیلی\n\nمنافع منقسم حصص داروں کو ادا کیا جاتا ہے۔")], [])

    out = await retrieval.search("dividend")

    assert out[0]["snippet_ur"] is not None
    assert "منافع" in out[0]["snippet_ur"]


@pytest.mark.asyncio
async def test_result_carries_both_display_snippets_and_full_grounding_text(monkeypatch):
    """search() serves two different consumers and must not conflate them.

    snippet_* are DISPLAY values (240-char cut for the search UI). text_* are
    the FULL chunk bodies that generation.py grounds the LLM on. Grounding on
    the snippet gave the model ~53% of a lesson — opening sentences only. The
    public API projects to the display fields (see test_learnhub_api).
    """
    _patch_arms(monkeypatch, [_row(1)], [])

    out = await retrieval.search("dividend")

    assert set(out[0]) == {
        "lesson_id", "section_id", "source_type", "title",
        "heading", "snippet_en", "snippet_ur", "text_en", "text_ur", "score",
    }


@pytest.mark.asyncio
async def test_full_text_is_not_truncated_like_the_snippet(monkeypatch):
    """The regression: a long section must reach grounding intact."""
    long_body = "A dividend is a share of profit. " * 40  # ~1300 chars
    row = _row(1)
    row["text_en"] = "Understanding Dividends — What is a dividend?\n\n" + long_body
    _patch_arms(monkeypatch, [row], [])

    out = await retrieval.search("dividend")

    assert len(out[0]["snippet_en"]) <= 241, "display snippet should stay short"
    assert out[0]["snippet_en"].endswith("…"), "display snippet should be elided"
    assert len(out[0]["text_en"]) > 1000, "grounding text must NOT be truncated"
    assert "…" not in out[0]["text_en"]


# --------------------------------------------------------------------------- #
# Relevance floor — calibrated live, pinned here                              #
# --------------------------------------------------------------------------- #
def test_relevance_floor_sits_inside_the_measured_gap():
    """The floor separates real matches from noise, measured on the live index
    (2026-07-16, gemini-embedding-001@768) using PARAPHRASE queries — the real
    workload, not the docs' own wording:

        worst relevant   0.3989  ("when prices keep rising" -> Bull Market)
        best irrelevant  0.4974  ("premier league football scores")

    Two earlier values were wrong and both are worth remembering: 0.60 (a
    guess) let every nonsense query through, and 0.42 (calibrated on DIRECT
    queries only) silently dropped Bull Market by 0.0013. Calibrate on
    paraphrases or this number lies to you.
    """
    assert 0.3989 < retrieval._MAX_COSINE_DISTANCE < 0.4974, (
        f"floor {retrieval._MAX_COSINE_DISTANCE} is outside the measured "
        "relevant/irrelevant gap — re-calibrate with PARAPHRASE queries "
        "before changing it"
    )


@pytest.mark.asyncio
async def test_vector_arm_drops_rows_beyond_the_floor(monkeypatch):
    """Rows past the floor must never reach fusion — an off-topic query has to
    return nothing rather than the least-irrelevant chunk."""
    near = _row(1, section_id="near", distance=0.25)
    far = _row(2, section_id="far", distance=0.53)   # nonsense range (measured 0.4974+)

    async def _fake_embed(texts):
        return [[0.1] * 768]

    monkeypatch.setattr(retrieval, "embed_gemini", _fake_embed)

    captured = {}

    class _FakeConn:
        async def execute(self, stmt, params=None):
            captured["ran"] = True

            class _R:
                @staticmethod
                def fetchall():
                    class _Row:
                        def __init__(self, d):
                            self._mapping = d
                    return [_Row(near), _Row(far)]
            return _R()

    class _Ctx:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(retrieval, "connect", lambda: _Ctx())

    rows = await retrieval._vector_arm("q", "", {})

    assert [r["section_id"] for r in rows] == ["near"], "floor did not drop the far row"


def test_related_floor_sits_above_the_domain_baseline():
    """All 90 live pairs score 0.558-0.865 — every lesson is finance education,
    so a floor of similarity is the domain itself, not a signal. Measured
    2026-07-16: budget's BEST match is 0.616 (it is personal finance, the rest
    are stock market), every other lesson's best is >= 0.684. The floor must
    fall in that gap or 'Related topics' shows 4 unrelated lessons for budget.
    """
    assert 0.616 < retrieval._MIN_RELATED_SCORE < 0.684, (
        f"floor {retrieval._MIN_RELATED_SCORE} outside the measured gap — "
        "re-measure against learnhub_related before changing it"
    )


# --------------------------------------------------------------------------- #
# Off-topic verdict vs embedding outage                                       #
# --------------------------------------------------------------------------- #
async def test_off_topic_query_returns_empty_even_when_fts_matches_a_keyword(
    monkeypatch,
):
    """The vector arm ran and cleared nothing: that is a verdict, not an outage.

    The FTS arm has no relevance floor, so "the price of milk" still matches the
    word "price" in the P/E lesson. Serving that is worse than nothing — it is
    what generation.py would then ground an answer on.
    """
    _patch_arms(monkeypatch, [], [_row(1, lesson_id="pe-ratio")])
    assert await retrieval.search("what is the price of milk") == []


async def test_embedding_outage_still_serves_fts_only(monkeypatch):
    """None (couldn't embed) must NOT be read as the off-topic verdict above —
    keyword search is the designed fallback and has to survive."""
    async def _vec(query, clause, params):
        return None

    async def _fts(query, clause, params):
        return [_row(1)]

    monkeypatch.setattr(retrieval, "_vector_arm", _vec)
    monkeypatch.setattr(retrieval, "_fts_arm", _fts)
    assert len(await retrieval.search("dividend")) == 1


# --------------------------------------------------------------------------- #
# Query-embedding cache                                                       #
# --------------------------------------------------------------------------- #
async def test_repeat_query_does_not_re_embed(monkeypatch):
    """search is public and unauthenticated; the same query must cost one
    embedding, not one per request."""
    retrieval._QUERY_VEC_CACHE.clear()
    calls = []

    async def _embed(texts):
        calls.append(texts)
        return [[0.1] * settings.ai_embedding_dim]

    monkeypatch.setattr(retrieval, "embed_gemini", _embed)
    for _ in range(3):
        await retrieval._embed_query("what is a dividend")
    assert len(calls) == 1


async def test_query_cache_is_bounded(monkeypatch):
    """A flood of unique queries must evict, not grow forever."""
    retrieval._QUERY_VEC_CACHE.clear()

    async def _embed(texts):
        return [[0.1] * settings.ai_embedding_dim]

    monkeypatch.setattr(retrieval, "embed_gemini", _embed)
    for i in range(retrieval._QUERY_VEC_CACHE_MAX + 25):
        await retrieval._embed_query(f"query number {i}")
    assert len(retrieval._QUERY_VEC_CACHE) <= retrieval._QUERY_VEC_CACHE_MAX


# --------------------------------------------------------------------------- #
# Relevance-floor calibration guard                                            #
# --------------------------------------------------------------------------- #
def test_calibration_guard_silent_when_config_matches(monkeypatch):
    monkeypatch.setattr(settings, "ai_embedding_model", retrieval._CALIBRATED_MODEL)
    monkeypatch.setattr(settings, "ai_embedding_dim", retrieval._CALIBRATED_DIM)
    assert retrieval.check_relevance_floor_calibration() is None


def test_calibration_guard_fires_when_model_or_dim_drifts(monkeypatch):
    """0.448 is empirical. Changing the model/dim in Railway moves every distance
    in the index while the floor stays put — that must not be silent."""
    monkeypatch.setattr(settings, "ai_embedding_model", "some-other-embedder")
    monkeypatch.setattr(settings, "ai_embedding_dim", retrieval._CALIBRATED_DIM)
    assert "unverified" in (retrieval.check_relevance_floor_calibration() or "")

    monkeypatch.setattr(settings, "ai_embedding_model", retrieval._CALIBRATED_MODEL)
    monkeypatch.setattr(settings, "ai_embedding_dim", 1536)
    assert "unverified" in (retrieval.check_relevance_floor_calibration() or "")
