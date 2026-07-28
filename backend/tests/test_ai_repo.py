"""Integration tests for ai_repo against the live DB (pattern of
test_sqlalchemy_queries.py). Uses an existing profile row as the user and
cleans up everything it inserts."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.repositories.base import begin, connect

# Every test here reaches the SQLAlchemy engine; skipped automatically when
# SUPABASE_DATABASE_PASSWORD is unset (see tests/conftest.py).
pytestmark = pytest.mark.requires_db



async def _any_user_id() -> str | None:
    async with connect() as conn:
        result = await conn.execute(text("SELECT id FROM profiles LIMIT 1"))
        row = result.first()
    return str(row[0]) if row else None


async def _cleanup(user_id: str) -> None:
    async with begin() as conn:
        await conn.execute(
            text("DELETE FROM ai_chat_history WHERE user_id = :uid AND content LIKE 'TESTAI%'"),
            {"uid": user_id},
        )
        await conn.execute(
            text("DELETE FROM ai_usage WHERE user_id = :uid AND usage_date = (now() AT TIME ZONE 'utc')::date"),
            {"uid": user_id},
        )


@pytest.mark.asyncio
async def test_history_roundtrip_oldest_first():
    from app.repositories import ai_repo

    user_id = await _any_user_id()
    if not user_id:
        pytest.skip("no profiles row in DB")
    try:
        async with begin() as conn:
            await ai_repo.insert_message(
                conn, user_id, "user", "TESTAI question", lesson_title="PSX basics", lang="en"
            )
            await ai_repo.insert_message(
                conn, user_id, "assistant", "TESTAI answer",
                lesson_title="PSX basics", lang="en", provider="gemini", model="gemini-2.5-flash",
            )
        async with connect() as conn:
            rows = await ai_repo.recent_history(conn, user_id, limit=10)
        test_rows = [r for r in rows if str(r["content"]).startswith("TESTAI")]
        assert [r["role"] for r in test_rows] == ["user", "assistant"]  # oldest-first
        assert test_rows[0]["lesson_title"] == "PSX basics"
    finally:
        await _cleanup(user_id)


@pytest.mark.asyncio
async def test_usage_starts_at_zero_and_increments():
    from app.repositories import ai_repo

    user_id = await _any_user_id()
    if not user_id:
        pytest.skip("no profiles row in DB")
    try:
        async with begin() as conn:
            await conn.execute(
                text("DELETE FROM ai_usage WHERE user_id = :uid AND usage_date = (now() AT TIME ZONE 'utc')::date"),
                {"uid": user_id},
            )
        async with connect() as conn:
            assert await ai_repo.get_today_usage(conn, user_id) == 0
        async with begin() as conn:
            await ai_repo.increment_usage(conn, user_id)
        async with begin() as conn:
            await ai_repo.increment_usage(conn, user_id, tokens_in=10, tokens_out=20)
        async with connect() as conn:
            assert await ai_repo.get_today_usage(conn, user_id) == 2
    finally:
        await _cleanup(user_id)
