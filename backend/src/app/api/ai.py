"""AI tutor routes: SSE chat stream + history + usage (thin over services.ai).

Auth: require_user (Supabase JWT). Quota is checked BEFORE any provider call;
usage increments only after a fully successful reply, so failed generations
never burn quota. If the client disconnects mid-stream, the generator is
cancelled and nothing is persisted (by design)."""
from __future__ import annotations

import json
from typing import Annotated, Any, AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import require_user
from app.schemas.ai import TutorRequest
from app.services.ai import quota, tutor
from app.services.ai.observability import propagate_attributes
from app.services.ai.providers import ProviderError

router = APIRouter(tags=["ai"])

_QUOTA_MSG = {
    "en": "You've reached today's AI tutor limit. Upgrade your plan or come back tomorrow.",
    "ur": "آپ آج کی اے آئی ٹیوٹر حد تک پہنچ گئے ہیں۔ اپنا پلان اپ گریڈ کریں یا کل دوبارہ آئیں۔",
}
_PROVIDER_MSG = {
    "en": "Sorry, I couldn't reach the AI tutor just now. Please try again.",
    "ur": "معذرت، ابھی اے آئی ٹیوٹر تک رسائی نہیں ہو سکی۔ براہ کرم دوبارہ کوشش کریں۔",
}


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/ai/tutor")
async def tutor_stream(body: TutorRequest, user: Annotated[dict, Depends(require_user)]):
    allowed, used, limit = await quota.check_quota(user)

    async def events() -> AsyncIterator[str]:
        if not allowed:
            yield _sse({"type": "error", "code": "quota", "message": _QUOTA_MSG[body.lang]})
            return
        parts: list[str] = []
        provider: str | None = None
        model: str | None = None
        try:
            # Stamps the tutor turn's root span (stream_reply's @observe) and
            # its child generations with the user and feature tag.
            with propagate_attributes(user_id=user["user_id"], tags=["tutor"]):
                async for ev in tutor.stream_reply(body):
                    if ev["type"] == "token":
                        parts.append(ev["text"])
                        yield _sse(ev)
                    elif ev["type"] == "meta":
                        provider, model = ev["provider"], ev["model"]
        except ProviderError:
            yield _sse({"type": "error", "code": "provider", "message": _PROVIDER_MSG[body.lang]})
            return
        await tutor.persist_exchange(
            user["user_id"],
            body.messages[-1].content,
            "".join(parts),
            lesson_title=body.lessonTitle,
            lang=body.lang,
            provider=provider,
            model=model,
        )
        yield _sse({"type": "done", "usage": {"used": used + 1, "limit": limit}})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/ai/tutor/history")
async def tutor_history(user: Annotated[dict, Depends(require_user)], limit: int = 20):
    return await tutor.get_history(user["user_id"], limit)


@router.get("/ai/tutor/usage")
async def tutor_usage(user: Annotated[dict, Depends(require_user)]):
    return await quota.usage_summary(user)
