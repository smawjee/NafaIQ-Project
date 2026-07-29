"""Verifies the 20260712000000_ai_tutor_history_usage migration is applied.

Inspects the live schema, so it is guarded like the other live-database suites
(see tests/test_sell_holding.py) and skips on a credential-free CI run instead
of failing with a socket error.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.config import settings

pytestmark = pytest.mark.skipif(
    not (settings.supabase_url and settings.supabase_service_key),
    reason="Supabase credentials not configured",
)


async def _scalar(sql: str, **params):
    from app.db.sqlalchemy import get_engine

    async with get_engine().connect() as conn:
        result = await conn.execute(text(sql), params)
        return result.scalar()


@pytest.mark.asyncio
async def test_ai_chat_history_table_exists():
    assert await _scalar("SELECT to_regclass('public.ai_chat_history')") is not None


@pytest.mark.asyncio
async def test_ai_usage_table_exists():
    assert await _scalar("SELECT to_regclass('public.ai_usage')") is not None


@pytest.mark.asyncio
async def test_ai_usage_pk_is_user_and_date():
    count = await _scalar(
        """
        SELECT COUNT(*) FROM information_schema.key_column_usage
        WHERE table_schema = 'public' AND table_name = 'ai_usage'
          AND constraint_name IN (
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'ai_usage' AND constraint_type = 'PRIMARY KEY'
          )
        """
    )
    assert count == 2  # (user_id, usage_date)


@pytest.mark.asyncio
async def test_plan_tutor_limits():
    free = await _scalar("SELECT ai_tutor_daily_limit FROM plan_features WHERE plan = 'Free'")
    pro = await _scalar("SELECT ai_tutor_daily_limit FROM plan_features WHERE plan = 'Pro'")
    premium = await _scalar("SELECT ai_tutor_daily_limit FROM plan_features WHERE plan = 'Premium'")
    assert free == 10
    assert pro == 100
    assert premium is None
