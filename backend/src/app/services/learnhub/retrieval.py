"""Hybrid retrieval over learnhub_knowledge_chunks.

Ranking is Reciprocal Rank Fusion over a vector arm and an FTS arm — rank
based, not score based, because cosine distance and ts_rank live on
incomparable scales and any weighted blend of them (e.g. 70/30) is calibration
guesswork that silently rots as the corpus changes.

Failure posture: every failure path returns fewer/no results rather than an
error. Retrieval feeds discovery surfaces; an empty result set renders as "no
results", which is a normal UI state. Specifically:
  * query embedding fails  -> FTS-only (keyword search still works)
  * DB/timeout/anything    -> []
Groq has no embeddings API, so there is no second embedding provider to rotate
to; FTS-only IS the fallback.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import structlog
from sqlalchemy import text

from app.config import settings
from app.repositories.base import connect
from app.services.ai.providers import embed_gemini

log = structlog.get_logger(__name__)

# Standard RRF constant. Small enough that top ranks dominate, large enough
# that a chunk found by BOTH arms reliably outranks either arm's #1.
_RRF_K = 60

# Per-arm candidate depth before fusion.
_ARM_LIMIT = 20

# Vector-arm floor: cosine distance above this is noise, not a match. Without
# it an off-topic query returns the least-irrelevant chunks, which is worse
# than an honest empty state.
#
# CALIBRATED against the live index (2026-07-16, gemini-embedding-001 @ 768,
# 86 chunks), not guessed. Two rounds, because the first was measured wrong:
#
#   Round 1 sampled DIRECT queries ("what is a dividend" -> 0.18) and landed on
#   0.42. That silently dropped "when prices keep rising" -> Bull Market at
#   0.4213 — missed by 0.0013. Direct queries are not what learners type.
#
#   Round 2 sampled PARAPHRASES, which is the real workload:
#     relevant   0.27 - 0.3989  (worst: "when prices keep rising")
#     irrelevant 0.4974 - 0.5456 (best: "premier league football scores")
#   Gap 0.098; 0.448 is its midpoint, ~0.05 clear on each side.
#
# Re-measure with PARAPHRASES (not doc wording) if the model or corpus changes
# materially. This number is empirical, not a law — test_relevance_floor pins it.
_MAX_COSINE_DISTANCE = 0.448

# Related-lessons floor: cosine SIMILARITY (not distance) below this is "these
# merely share a domain", not "related".
#
# MEASURED on the live 10-lesson index (2026-07-16): all 90 pairs score
# 0.558-0.865 because every lesson is finance education — some similarity is
# the floor of the domain, not a signal. Without a cut, "Related topics" always
# rendered `limit` lessons no matter how unrelated.
#   candlestick <-> patterns  0.865   genuinely related
#   pe-ratio    <-> psx       0.755
#   budget      <-> anything  0.616 MAX  (personal finance vs stock market —
#                                         budget legitimately has NO relatives)
# 0.65 sits above budget's best (0.616) and below every other lesson's best
# (0.684+), so budget correctly shows nothing and the rest keep real neighbours.
_MIN_RELATED_SCORE = 0.65

# Retrieval modes -> extra SQL predicate. `related` is served by a precomputed
# table, not this path.
MODE_ALL = "learnhub_all"
MODE_LESSON = "current_lesson"
MODE_GLOSSARY = "glossary_only"


def _mode_clause(mode: str, lesson_id: Optional[str]) -> tuple[str, dict[str, Any]]:
    if mode == MODE_GLOSSARY:
        return "AND source_type = 'glossary_term'", {}
    if mode == MODE_LESSON and lesson_id:
        return "AND lesson_id = :lesson_id", {"lesson_id": lesson_id}
    return "", {}


async def _vector_arm(query: str, clause: str, params: dict) -> list[dict]:
    try:
        [vec] = await embed_gemini([query])
    except Exception:
        # Keyword search still works; log and let the FTS arm carry it.
        log.warning("learn_query_embed_failed", exc_info=True)
        return []
    literal = "[" + ",".join(f"{x:.7f}" for x in vec) + "]"
    async with connect() as conn:
        res = await conn.execute(
            text(
                f"""
                SELECT id, source_type, source_id, lesson_id, section_id,
                       title, heading, text_en, text_ur,
                       embedding <=> CAST(:vec AS extensions.vector) AS distance
                FROM learnhub_knowledge_chunks
                WHERE is_active
                  AND embedding IS NOT NULL
                  AND embedding_model = :model
                  {clause}
                ORDER BY distance
                LIMIT :n
                """
            ),
            {"vec": literal, "model": settings.ai_embedding_model, "n": _ARM_LIMIT, **params},
        )
        rows = [dict(r._mapping) for r in res.fetchall()]
    return [r for r in rows if r["distance"] <= _MAX_COSINE_DISTANCE]


async def _fts_arm(query: str, clause: str, params: dict) -> list[dict]:
    async with connect() as conn:
        res = await conn.execute(
            text(
                f"""
                SELECT id, source_type, source_id, lesson_id, section_id,
                       title, heading, text_en, text_ur
                FROM learnhub_knowledge_chunks
                WHERE is_active
                  AND fts @@ websearch_to_tsquery('english', :q)
                  {clause}
                ORDER BY ts_rank(fts, websearch_to_tsquery('english', :q)) DESC
                LIMIT :n
                """
            ),
            {"q": query, "n": _ARM_LIMIT, **params},
        )
        return [dict(r._mapping) for r in res.fetchall()]


def _snippet(row: dict[str, Any], limit: int = 240) -> tuple[str, Optional[str]]:
    """(snippet_en, snippet_ur). Chunks carry a context prefix line; strip it —
    the caller already shows title/heading, so repeating them wastes the
    snippet. text_ur is all-or-nothing per the exporter, so it needs no
    separate completeness check here."""
    def _body(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        body = value.split("\n\n", 1)[-1].strip()
        return body[:limit] + ("…" if len(body) > limit else "")

    return _body(row.get("text_en")) or "", _body(row.get("text_ur"))


async def search(
    query: str,
    *,
    mode: str = MODE_ALL,
    lesson_id: Optional[str] = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Hybrid search. Returns [] on any failure — never raises to the caller."""
    q = (query or "").strip()
    if len(q) < 2:
        return []

    started = time.perf_counter()
    clause, params = _mode_clause(mode, lesson_id)
    try:
        async with asyncio.timeout(settings.learnhub_retrieval_timeout_s):
            vector_rows, fts_rows = await asyncio.gather(
                _vector_arm(q, clause, params),
                _fts_arm(q, clause, params),
            )
    except Exception:
        log.warning("learn_search_failed", mode=mode, exc_info=True)
        return []

    fused: dict[int, dict[str, Any]] = {}
    for rank, row in enumerate(vector_rows):
        fused.setdefault(row["id"], {"row": row, "score": 0.0})["score"] += 1.0 / (_RRF_K + rank + 1)
    for rank, row in enumerate(fts_rows):
        fused.setdefault(row["id"], {"row": row, "score": 0.0})["score"] += 1.0 / (_RRF_K + rank + 1)

    ranked = sorted(fused.values(), key=lambda e: e["score"], reverse=True)[:limit]
    results = []
    for entry in ranked:
        row = entry["row"]
        snippet_en, snippet_ur = _snippet(row)
        results.append(
            {
                "lesson_id": row.get("lesson_id"),
                "section_id": row.get("section_id"),
                "source_type": row["source_type"],
                "title": row.get("title") or "",
                "heading": row.get("heading"),
                "snippet_en": snippet_en,
                "snippet_ur": snippet_ur,
                # FULL chunk text, untruncated. snippet_* are DISPLAY values
                # (cut at 240 chars for the UI); grounding an LLM on them fed
                # the model ~53% of a lesson — each section's opening sentences
                # only, several ending mid-word. Callers that ground MUST read
                # text_en/text_ur; callers that render read snippet_*.
                "text_en": row.get("text_en") or "",
                "text_ur": row.get("text_ur"),
                "score": round(entry["score"], 6),
            }
        )

    # Metadata only — never log user query text or chunk bodies.
    log.info(
        "learn_search",
        mode=mode,
        hits=len(results),
        vector_hits=len(vector_rows),
        fts_hits=len(fts_rows),
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    return results


async def related_lessons(lesson_id: str, limit: int = 5) -> list[dict[str, Any]]:
    """Precomputed at ingestion (learnhub_related), so this is a plain indexed
    read — no embedding call, predictable UI latency."""
    try:
        async with connect() as conn:
            res = await conn.execute(
                text(
                    """
                    SELECT related_lesson_id, score
                    FROM learnhub_related
                    WHERE lesson_id = :lesson_id
                      AND score >= :floor
                    ORDER BY score DESC
                    LIMIT :n
                    """
                ),
                {"lesson_id": lesson_id, "n": limit, "floor": _MIN_RELATED_SCORE},
            )
            return [
                {"lesson_id": r[0], "score": float(r[1])} for r in res.fetchall()
            ]
    except Exception:
        log.warning("learn_related_failed", lesson_id=lesson_id, exc_info=True)
        return []
