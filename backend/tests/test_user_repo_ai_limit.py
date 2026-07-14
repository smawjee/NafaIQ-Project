"""Regression: get_plan_features must expose ai_tutor_daily_limit.

The AI tutor quota (services.ai.quota) reads this key off the require_user
features dict; before this test existed the SELECT omitted the column, which
silently made every user's tutor quota unlimited.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.repositories import user_repo
from app.repositories.base import connect


@pytest.mark.asyncio
async def test_plan_features_include_ai_tutor_daily_limit():
    async with connect() as conn:
        row = (await conn.execute(text("SELECT id FROM profiles LIMIT 1"))).first()
        if not row:
            pytest.skip("no profiles row in DB")
        user_id = str(row[0])
        features = await user_repo.get_plan_features(conn, user_id)
    assert features is not None
    assert "ai_tutor_daily_limit" in features
    # Value must match the plan_features seed for the user's plan
    # (Free=10, Pro=100, Premium=NULL/unlimited).
    async with connect() as conn:
        expected = (
            await conn.execute(
                text("SELECT ai_tutor_daily_limit FROM plan_features WHERE plan = :p"),
                {"p": features["plan"]},
            )
        ).scalar()
    assert features["ai_tutor_daily_limit"] == expected


@pytest.mark.asyncio
async def test_plan_features_include_ai_report_quota_columns():
    """Regression companion to the tutor-limit bug: get_plan_features must also
    expose the period-aware report quota columns, or check_report_quota reads
    None and every user is silently unlimited for reports."""
    async with connect() as conn:
        row = (await conn.execute(text("SELECT id FROM profiles LIMIT 1"))).first()
        if not row:
            pytest.skip("no profiles row in DB")
        user_id = str(row[0])
        features = await user_repo.get_plan_features(conn, user_id)
    assert features is not None
    assert "ai_reports_per_period" in features
    assert "ai_reports_period" in features
    # Values must match the plan_features seed for the user's plan. NULL
    # (Premium/unlimited) must be preserved, not COALESCED to the Free cap.
    async with connect() as conn:
        seed = (
            await conn.execute(
                text(
                    "SELECT ai_reports_per_period, ai_reports_period "
                    "FROM plan_features WHERE plan = :p"
                ),
                {"p": features["plan"]},
            )
        ).mappings().first()
    assert seed is not None
    assert features["ai_reports_per_period"] == seed["ai_reports_per_period"]
    assert features["ai_reports_period"] == seed["ai_reports_period"]
