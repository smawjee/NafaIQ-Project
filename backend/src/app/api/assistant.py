"""NafaIQ Assistant routes — the voice-and-text agent behind "Ask NafaIQ AI".

Auth: require_user (Supabase JWT), enforced by the /api/assistant prefix in
middleware/auth.py — every route here reads or writes the caller's own finance
data, so the shared PSX API token must never satisfy it.

Deliberately separate from api/ai.py (the LearnHub tutor): different provider
routing, its own quota table, and a tool-calling loop rather than plain chat.
The tutor is not modified by this feature.
"""
from __future__ import annotations

import json
from typing import Annotated, Any, AsyncIterator, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import require_user
from app.config import settings
from app.repositories import assistant_usage
from app.schemas.assistant import AssistantExecuteRequest, AssistantChatRequest
from app.services.ai.observability import observation_span, propagate_attributes
from app.services.ai.providers import ProviderError, ProviderRateLimited, transcribe_audio
from app.services.assistant import agent
from app.services.assistant.execute import execute_draft

router = APIRouter(tags=["assistant"])

_QUOTA_MSG = {
    "en": "You've reached today's NafaIQ Assistant limit. It resets tomorrow.",
    "ur": "آپ آج کی نفع آئی کیو اسسٹنٹ حد تک پہنچ گئے ہیں۔ یہ کل دوبارہ سیٹ ہو جائے گی۔",
}
_PROVIDER_MSG = {
    "en": "Sorry, I couldn't reach the assistant just now. Please try again.",
    "ur": "معذرت، ابھی اسسٹنٹ تک رسائی نہیں ہو سکی۔ براہ کرم دوبارہ کوشش کریں۔",
}
# Distinct from _PROVIDER_MSG on purpose: "something went wrong" is both wrong
# and mildly alarming when the truth is "the AI provider is throttling us".
_BUSY_MSG = {
    "en": "The assistant is busy right now. Please try again {when}.",
    "ur": "اسسٹنٹ ابھی مصروف ہے۔ براہ کرم {when} دوبارہ کوشش کریں۔",
}
_BUSY_SOON = {"en": "in a moment", "ur": "تھوڑی دیر بعد"}


def _busy_message(lang: str, retry_after_s: float | None) -> str:
    if not retry_after_s or retry_after_s <= 0:
        when = _BUSY_SOON[lang]
    elif retry_after_s < 90:
        when = (
            f"in {int(retry_after_s)}s"
            if lang == "en"
            else f"{int(retry_after_s)} سیکنڈ بعد"
        )
    else:
        minutes = int(retry_after_s // 60)
        when = f"in {minutes} min" if lang == "en" else f"{minutes} منٹ بعد"
    return _BUSY_MSG[lang].format(when=when)


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

# Containers a browser MediaRecorder or an Expo recorder actually produces,
# plus the codecs suffix Chrome appends ("audio/webm;codecs=opus"). Checked by
# prefix so the suffix does not have to be enumerated.
_ALLOWED_AUDIO_PREFIXES = (
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/m4a",
    "audio/x-m4a",
    "audio/wav",
    "audio/x-wav",
)


async def _consume_allowance(user: dict) -> int:
    """Take one of the user's daily assistant turns, or 429.

    Counted BEFORE the provider call and not refunded on failure — same rule as
    LearnHub AI: the call is what costs tokens, and a refund-on-failure rule
    would let a failing provider be retried without limit, exactly when it can
    least afford it.
    """
    limit = settings.ai_assistant_daily_limit
    allowed, used = await assistant_usage.check_and_increment(user["user_id"], limit)
    if not allowed:
        raise HTTPException(
            429,
            f"Daily limit reached: you've used all {used} NafaIQ Assistant "
            "requests for today. This resets tomorrow, and the rest of the app "
            "— including the AI tutor — is unaffected.",
        )
    return used


@router.post("/assistant/transcribe")
async def transcribe(
    user: Annotated[dict, Depends(require_user)],
    file: UploadFile = File(...),
    lang: Literal["en", "ur"] = Form("en"),
):
    """Transcribe one short spoken command to text.

    The transcript is returned to the client and placed in the composer — it is
    NOT auto-sent to the agent. The user sees what was heard and can correct it
    before acting, which is what makes a misheard amount a visible edit rather
    than a wrong ledger row.
    """
    content_type = (file.content_type or "").lower()
    if not content_type.startswith(_ALLOWED_AUDIO_PREFIXES):
        raise HTTPException(415, f"Unsupported audio type '{file.content_type}'")

    # Read with one byte of headroom past the cap so an oversized upload is
    # detected rather than silently truncated into a half-sentence transcript.
    audio = await file.read(settings.ai_stt_max_bytes + 1)
    if not audio:
        raise HTTPException(400, "Empty audio upload")
    if len(audio) > settings.ai_stt_max_bytes:
        raise HTTPException(
            413,
            f"Audio too large (limit {settings.ai_stt_max_bytes // (1024 * 1024)}MB, "
            f"about {settings.ai_stt_max_seconds}s of speech). Record a shorter command.",
        )

    await _consume_allowance(user)

    # The langfuse openai wrapper does not auto-trace audio.transcriptions, so
    # this manual span is what makes voice commands visible at all. Input is
    # metadata only — never the raw audio bytes.
    with propagate_attributes(user_id=user["user_id"], tags=["assistant", "transcribe"]):
        with observation_span(
            "assistant_transcribe", input={"lang": lang, "bytes": len(audio)}
        ) as span:
            try:
                text = await transcribe_audio(
                    audio,
                    filename=file.filename or "audio.webm",
                    content_type=content_type,
                    language=lang,
                )
            except ProviderRateLimited as e:
                # 503 + Retry-After is the honest status for throttling, and
                # lets the client say how long rather than "unavailable".
                raise HTTPException(
                    503,
                    _busy_message(lang, e.retry_after_s),
                    headers={"Retry-After": str(int(e.retry_after_s or 30))},
                ) from e
            except ProviderError as e:
                # 502, not 500: the failure is upstream, and the client
                # distinguishes "try again" from "this request was wrong".
                raise HTTPException(502, f"Speech recognition unavailable: {e}") from e
            if span is not None:
                span.update(output={"chars": len(text)})

    return {"text": text, "lang": lang}


@router.post("/assistant/chat")
async def chat(body: AssistantChatRequest, user: Annotated[dict, Depends(require_user)]):
    """Run one assistant turn, streaming events as SSE.

    Quota is consumed BEFORE the provider call, matching the transcribe route
    and LearnHub AI. Write tools never execute here — a `draft` event is the
    end of the road until the client posts it back to /assistant/execute.
    """
    limit = settings.ai_assistant_daily_limit
    allowed, used = await assistant_usage.check_and_increment(user["user_id"], limit)

    async def events() -> AsyncIterator[str]:
        if not allowed:
            yield _sse({"type": "error", "code": "quota", "message": _QUOTA_MSG[body.lang]})
            return
        # Wraps the creation of the turn's root span (run_turn's @observe), so
        # the trace and every child generation/tool span carry the user and
        # conversation. session_id=None is accepted and simply left unset.
        with propagate_attributes(
            user_id=user["user_id"],
            session_id=body.conversation_id,
            tags=["assistant"],
        ):
            try:
                async for event in agent.run_turn(
                    user,
                    [{"role": m.role, "content": m.content} for m in body.messages],
                    body.lang,
                ):
                    yield _sse(event)
            except ProviderRateLimited as e:
                yield _sse(
                    {
                        "type": "error",
                        "code": "busy",
                        "message": _busy_message(body.lang, e.retry_after_s),
                        "retryAfter": e.retry_after_s,
                    }
                )
                return
            except ProviderError:
                yield _sse(
                    {"type": "error", "code": "provider", "message": _PROVIDER_MSG[body.lang]}
                )
                return
        yield _sse({"type": "done", "usage": {"used": used, "limit": limit}})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        # X-Accel-Buffering: nginx/Railway would otherwise buffer the whole
        # stream and deliver it as one blob at the end.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/assistant/execute")
async def execute(
    body: AssistantExecuteRequest, user: Annotated[dict, Depends(require_user)]
):
    """Perform one confirmed draft.

    Free of quota: the turn that produced the draft already paid, and charging
    again would penalise the user for confirming. Every guard the REST API
    applies still applies, because this dispatches to the same services.
    """
    with propagate_attributes(
        user_id=user["user_id"],
        session_id=body.conversation_id,
        tags=["assistant", "execute"],
    ):
        return await execute_draft(user, body.action, body.args)


@router.get("/assistant/usage")
async def usage(user: Annotated[dict, Depends(require_user)]):
    used = await assistant_usage.get_today_usage(user["user_id"])
    limit = settings.ai_assistant_daily_limit
    return {"used": used, "limit": limit, "remaining": max(0, limit - used)}
