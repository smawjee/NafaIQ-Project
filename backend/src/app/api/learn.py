"""LearnHub RAG endpoints — semantic search over lesson content.

Public (no user token): this is published course material, the same content the
web app already ships in its bundle, so there is nothing to protect. LLM-backed
LearnHub features live under /api/learn/ai/* instead, which auth.py classifies
as user paths — the middleware checks USER_PATHS_PREFIXES before
PUBLIC_PATH_PREFIXES, so the /api/learn/ai prefix stays authenticated while
/api/learn is open.

Nothing here touches the AI tutor. See tests/test_tutor_isolation.py.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Query, Request

from app.config import settings
from app.middleware.rate_limit import limiter
from app.services.learnhub import retrieval

router = APIRouter(tags=["learn"])

# The frozen client contract. retrieval.search() also carries text_en/text_ur
# for the grounding path (services/learnhub/generation.py); those are full chunk
# bodies and must NOT ride the public search response — they would bloat every
# payload and hand the whole corpus to any caller of an unauthenticated
# endpoint. Project explicitly rather than deleting keys, so a new internal
# field can never leak by default.
_PUBLIC_RESULT_FIELDS = (
    "lesson_id",
    "section_id",
    "source_type",
    "title",
    "heading",
    "snippet_en",
    "snippet_ur",
    "score",
)


def _public_results(rows: list[dict]) -> list[dict]:
    return [{k: r.get(k) for k in _PUBLIC_RESULT_FIELDS} for r in rows]


@router.get("/learn/status")
@limiter.limit("60/minute")
async def learn_status(request: Request):
    """Whether the RAG surfaces are enabled. The web app calls this once and
    hides every RAG affordance when false — the flag hides UI rather than
    surfacing errors."""
    return {"enabled": settings.learnhub_rag_enabled}


@router.get("/learn/search")
@limiter.limit("30/minute")
async def learn_search(
    request: Request,
    q: str = Query(..., min_length=2, max_length=200),
    lang: Literal["en", "ur"] = "en",
    lesson_id: Optional[str] = Query(None, max_length=64),
    limit: int = Query(8, ge=1, le=20),
):
    """Hybrid (vector + keyword) search over LearnHub content.

    `lang` does not change retrieval — chunks are embedded in English and
    cross-lingual embeddings handle Urdu queries. It is accepted so the client
    contract is stable and so a future language-specific ranking has a home.
    Urdu output rides `snippet_ur` on each result.
    """
    if not settings.learnhub_rag_enabled:
        return {"results": []}
    results = await retrieval.search(
        q,
        mode=retrieval.MODE_LESSON if lesson_id else retrieval.MODE_ALL,
        lesson_id=lesson_id,
        limit=limit,
    )
    return {"results": _public_results(results)}


@router.get("/learn/glossary/search")
@limiter.limit("30/minute")
async def learn_glossary_search(
    request: Request,
    q: str = Query(..., min_length=2, max_length=200),
    lang: Literal["en", "ur"] = "en",
    limit: int = Query(5, ge=1, le=20),
):
    """Glossary-only search: exact terms land via FTS, concepts via vector."""
    if not settings.learnhub_rag_enabled:
        return {"results": []}
    results = await retrieval.search(
        q, mode=retrieval.MODE_GLOSSARY, limit=limit
    )
    return {"results": _public_results(results)}


@router.get("/learn/related")
@limiter.limit("60/minute")
async def learn_related(
    request: Request,
    lesson_id: str = Query(..., max_length=64),
    limit: int = Query(5, ge=1, le=10),
):
    """Related lessons by content similarity, precomputed at ingestion."""
    if not settings.learnhub_rag_enabled:
        return {"results": []}
    return {"results": await retrieval.related_lessons(lesson_id, limit=limit)}
