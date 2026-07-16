"""Tutor orchestration: system prompt, provider fallback, persistence.

Fallback contract: Gemini first; if it fails BEFORE any token was yielded,
retry transparently with Groq. Once a token has been yielded, a failure
propagates (the API layer ends the SSE stream with an error event) — we never
splice two providers' output into one reply.
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Optional

from app.config import settings
from app.repositories import ai_repo
from app.repositories.base import begin, connect
from app.schemas.ai import TutorRequest
from app.services.ai import providers
from app.services.ai.prompts import load_prompt

log = logging.getLogger(__name__)


def build_system_prompt(lesson_title: str, lesson_context: Optional[str], lang: str) -> str:
    is_urdu = lang == "ur"
    context = f' (currently in the "{lesson_context}" section)' if lesson_context else ""
    lang_rule = (
        "Reply entirely in Urdu, except stock symbols, app names, and market tickers."
        if is_urdu
        else "Reply in English."
    )
    return load_prompt("tutor").format(
        lesson_title=lesson_title, context=context, lang_rule=lang_rule
    )


async def stream_reply(
    body: TutorRequest, *, transport: Any = None
) -> AsyncIterator[dict[str, Any]]:
    """Yield {"type":"token","text":...} events, then a final
    {"type":"meta","provider":...,"model":...}. Raises ProviderError if all
    providers fail before the first token, or on mid-stream failure."""
    system = build_system_prompt(body.lessonTitle, body.lessonContext, body.lang)
    oai_messages = [{"role": "system", "content": system}] + [
        {"role": m.role, "content": m.content} for m in body.messages
    ]
    attempts = [
        ("gemini", settings.ai_tutor_model_primary, providers.stream_gemini),
        ("groq", settings.ai_tutor_model_fallback, providers.stream_groq),
    ]
    last_err: Exception | None = None
    for name, model, fn in attempts:
        started = False
        try:
            async for delta in fn(oai_messages, transport=transport):
                started = True
                yield {"type": "token", "text": delta}
            yield {"type": "meta", "provider": name, "model": model}
            return
        except providers.ProviderError as e:
            if started:
                raise  # mid-stream: never switch providers
            log.warning("tutor provider %s failed pre-stream, trying next: %s", name, e)
            last_err = e
            continue
    raise providers.ProviderError(f"all providers failed: {last_err}")


async def persist_exchange(
    user_id: str,
    question: str,
    reply: str,
    *,
    lesson_title: str,
    lang: str,
    provider: Optional[str],
    model: Optional[str],
) -> None:
    """One transaction: user turn + assistant turn + usage increment."""
    async with begin() as conn:
        await ai_repo.insert_message(
            conn, user_id, "user", question, lesson_title=lesson_title, lang=lang
        )
        await ai_repo.insert_message(
            conn, user_id, "assistant", reply,
            lesson_title=lesson_title, lang=lang, provider=provider, model=model,
        )
        await ai_repo.increment_usage(conn, user_id)


async def get_history(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 50))
    async with connect() as conn:
        return await ai_repo.recent_history(conn, user_id, limit)
