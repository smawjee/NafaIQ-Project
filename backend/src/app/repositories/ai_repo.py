"""AI tutor data access: chat history + daily usage counters.

All writes run server-side with the service connection (bypasses RLS), so
user_id MUST always come from the verified JWT (require_user), never the client.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any


async def insert_message(
    conn: Executor,
    user_id: str,
    role: str,
    content: str,
    *,
    lesson_title: Optional[str] = None,
    lang: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO ai_chat_history
                (user_id, role, content, lesson_title, lang, provider, model)
            VALUES (:uid, :role, :content, :lesson_title, :lang, :provider, :model)
            """
        ),
        {
            "uid": user_id,
            "role": role,
            "content": content,
            "lesson_title": lesson_title,
            "lang": lang,
            "provider": provider,
            "model": model,
        },
    )


async def recent_history(conn: Executor, user_id: str, limit: int) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            """
            SELECT id, role, content, lesson_title, lang, created_at
            FROM ai_chat_history
            WHERE user_id = :uid
            ORDER BY created_at DESC, id DESC
            LIMIT :lim
            """
        ),
        {"uid": user_id, "lim": limit},
    )
    rows = [
        {
            "id": r["id"],
            "role": r["role"],
            "content": r["content"],
            "lesson_title": r["lesson_title"],
            "lang": r["lang"],
            "created_at": str(r["created_at"]),
        }
        for r in result.mappings().all()
    ]
    rows.reverse()  # oldest-first for direct rendering
    return rows


async def get_today_usage(conn: Executor, user_id: str) -> int:
    result = await conn.execute(
        text(
            """
            SELECT message_count FROM ai_usage
            WHERE user_id = :uid
              AND usage_date = (now() AT TIME ZONE 'utc')::date
            """
        ),
        {"uid": user_id},
    )
    row = result.first()
    return int(row[0]) if row else 0


async def increment_usage(
    conn: Executor, user_id: str, tokens_in: int = 0, tokens_out: int = 0
) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO ai_usage (user_id, usage_date, message_count, tokens_in, tokens_out)
            VALUES (:uid, (now() AT TIME ZONE 'utc')::date, 1, :tin, :tout)
            ON CONFLICT (user_id, usage_date) DO UPDATE SET
                message_count = ai_usage.message_count + 1,
                tokens_in = ai_usage.tokens_in + EXCLUDED.tokens_in,
                tokens_out = ai_usage.tokens_out + EXCLUDED.tokens_out,
                updated_at = now()
            """
        ),
        {"uid": user_id, "tin": tokens_in, "tout": tokens_out},
    )
