"""/api/learn/ai/* — the LLM-backed LearnHub surfaces.

Authenticated, unlike the rest of /api/learn: these spend tokens and burn a
per-user daily allowance. middleware/auth.py already carries the "/api/learn/ai"
prefix in USER_PATHS_PREFIXES, ahead of the public "/api/learn" — dispatch checks
user paths first, which is what keeps these gated while search stays open.

The fallback contract: when generation cannot ground an answer or the provider
is down, these return HTTP 200 with a null payload, NOT an error. The client
already ships static explanations and summaries; a null tells it to show them.
A 5xx would turn a handled degradation into an error toast.

Usage is counted in learnhub_ai_usage — never the AI tutor's counter. The two
features have separate allowances by project decision.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import require_user
from app.config import settings
from app.middleware.rate_limit import limiter
from app.repositories import learnhub_usage
from app.services.learnhub import generation

router = APIRouter(tags=["learn"])


class QuizExplanationRequest(BaseModel):
    # extra="forbid" + bounded lengths: this body reaches an LLM prompt, so
    # unbounded free text is a token-cost amplification vector even behind auth.
    model_config = ConfigDict(extra="forbid")

    lessonId: str = Field(..., min_length=1, max_length=64)
    question: str = Field(..., min_length=1, max_length=500)
    # min_length=0: an empty selection is a REAL state, not a bad request — the
    # quiz has a 30s timer and answer(null) leaves nothing selected. Requiring
    # 1 char 422'd every timed-out question, which the client swallows into
    # "no explanation", so the feature was silently dead exactly when a learner
    # most needed it. generation.py renders "" as "ran out of time".
    selectedOption: str = Field("", max_length=300)
    correctOption: str = Field(..., min_length=1, max_length=300)
    lang: Literal["en", "ur"] = "en"


class SummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lessonId: str = Field(..., min_length=1, max_length=64)
    sectionId: Optional[str] = Field(None, max_length=64)
    lang: Literal["en", "ur"] = "en"


def _require_enabled() -> None:
    """503, not a null payload: the flag being off is a server state, and the
    client's status check already hides these affordances entirely. A silent
    null here would look like a permanent generation failure instead."""
    if not settings.learnhub_rag_enabled:
        raise HTTPException(503, "LearnHub AI is not enabled")


async def _consume_allowance(user: dict) -> None:
    """Take one of the user's daily calls, or 429 with a clean message.

    Counted BEFORE generating and not refunded when generation returns None:
    the call is what costs tokens, and a refund-on-failure rule would let a
    failing provider be retried without limit — exactly when the provider can
    least afford it.
    """
    limit = settings.learn_ai_daily_limit
    allowed, used = await learnhub_usage.check_and_increment(user["user_id"], limit)
    if not allowed:
        raise HTTPException(
            429,
            f"Daily limit reached: you've used all {used} LearnHub AI requests "
            "for today. This resets tomorrow, and the rest of LearnHub — "
            "lessons, search and the AI tutor — is unaffected.",
        )


@router.post("/learn/ai/quiz-explanation")
@limiter.limit("10/minute")
async def quiz_explanation(
    request: Request,
    body: QuizExplanationRequest,
    user: dict = Depends(require_user),
):
    """Explain a quiz answer, grounded in the lesson's own content.

    `explanation: null` means "use the quiz's bundled static explanation".
    """
    _require_enabled()
    await _consume_allowance(user)

    result = await generation.explain_quiz_answer(
        lesson_id=body.lessonId,
        question=body.question,
        selected_option=body.selectedOption,
        correct_option=body.correctOption,
        lang=body.lang,
    )
    if result is None:
        return {"explanation": None, "sources": []}
    return {"explanation": result.explanation, "sources": result.sources}


@router.post("/learn/ai/summary")
@limiter.limit("10/minute")
async def summary(
    request: Request,
    body: SummaryRequest,
    user: dict = Depends(require_user),
):
    """Summarize a lesson or one of its sections, grounded in its content.

    Empty `key_ideas` means "use the lesson's bundled static summary".
    """
    _require_enabled()
    await _consume_allowance(user)

    result = await generation.summarize(
        lesson_id=body.lessonId,
        section_id=body.sectionId,
        lang=body.lang,
    )
    if result is None:
        return {"key_ideas": [], "terms": [], "pitfall": None, "sources": []}
    return {
        "key_ideas": result.key_ideas,
        "terms": result.terms,
        "pitfall": result.pitfall,
        "sources": result.sources,
    }
