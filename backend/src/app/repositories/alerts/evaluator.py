"""Source reads the alert evaluators run over (due bills, all budgets/goals)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

Executor = Any


async def fetch_due_bills(conn: Executor, days_ahead: int) -> list[dict[str, Any]]:
    rows = await conn.execute(
        text(
            "SELECT id, user_id, name, amount, due_date "
            "FROM user_bills "
            "WHERE status IN ('UPCOMING','DUE_SOON','DUE SOON') "
            "AND due_date IS NOT NULL "
            "AND due_date <= CURRENT_DATE + (:n * INTERVAL '1 day') "
            "AND due_date >= CURRENT_DATE - INTERVAL '7 days'"
        ),
        {"n": int(days_ahead)},
    )
    return [dict(r) for r in rows.mappings().all()]


async def fetch_all_budgets(conn: Executor) -> list[dict[str, Any]]:
    rows = await conn.execute(
        text(
            "SELECT b.id, b.user_id, b.category, b.spent, b.limit_amount, "
            "b.period, b.tip FROM user_budgets b"
        )
    )
    return [dict(r) for r in rows.mappings().all()]


async def fetch_all_goals(conn: Executor) -> list[dict[str, Any]]:
    rows = await conn.execute(
        text("SELECT id, user_id, name, target, saved FROM user_goals")
    )
    return [dict(r) for r in rows.mappings().all()]
