"""User/profile data access: plan + plan_features lookup, plan selection,
and finance/app settings not owned by other repos.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any


async def get_plan_features(conn: Executor, user_id: str) -> Optional[dict[str, Any]]:
    """Return {plan, ...feature flags} for a user, or None if no profile row."""
    row = (
        await conn.execute(
            text(
                """
                SELECT
                    COALESCE(p.plan, 'Free') AS plan,
                    COALESCE(f.max_watchlist, 10) AS max_watchlist,
                    COALESCE(f.max_price_alerts, 5) AS max_price_alerts,
                    COALESCE(f.max_portfolios, 1) AS max_portfolios,
                    COALESCE(f.max_holdings_per_portfolio, 20) AS max_holdings_per_portfolio,
                    COALESCE(f.max_budgets, 5) AS max_budgets,
                    COALESCE(f.max_bills, 5) AS max_bills,
                    COALESCE(f.max_goals, 3) AS max_goals,
                    COALESCE(f.max_finance_history_days, 30) AS max_finance_history_days,
                    COALESCE(f.has_email_alerts, FALSE) AS has_email_alerts,
                    COALESCE(f.has_push_alerts, FALSE) AS has_push_alerts,
                    COALESCE(f.has_export, FALSE) AS has_export,
                    COALESCE(f.has_multi_currency, FALSE) AS has_multi_currency,
                    COALESCE(f.has_realtime_psx, FALSE) AS has_realtime_psx,
                    COALESCE(f.has_screener_full, FALSE) AS has_screener_full,
                    -- NULL means unlimited (Pro/Premium), so no COALESCE; only a
                    -- plan_features join miss falls back to the Free cap of 10.
                    CASE WHEN f.plan IS NULL THEN 10
                         ELSE f.ai_tutor_daily_limit END AS ai_tutor_daily_limit,
                    -- Report quota (period-aware). NULL means unlimited
                    -- (Premium), so — like ai_tutor_daily_limit above — only a
                    -- plan_features join MISS (f.plan IS NULL) falls back to the
                    -- Free caps. A plain COALESCE would wrongly cap Premium at 3.
                    CASE WHEN f.plan IS NULL THEN 3
                         ELSE f.ai_reports_per_period END AS ai_reports_per_period,
                    CASE WHEN f.plan IS NULL THEN 'month'
                         ELSE f.ai_reports_period END AS ai_reports_period
                FROM profiles p
                LEFT JOIN plan_features f ON f.plan = p.plan
                WHERE p.id = :uid
                """
            ),
            {"uid": user_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def is_known_plan(conn: Executor, plan: str) -> bool:
    row = await conn.execute(
        text("SELECT 1 FROM plan_features WHERE plan = :p"), {"p": plan}
    )
    return row.first() is not None


async def update_plan(conn: Executor, user_id: str, plan: str) -> Optional[dict[str, Any]]:
    row = await conn.execute(
        text(
            "UPDATE profiles SET plan = :p, plan_selected_at = now() "
            "WHERE id = :uid RETURNING plan, plan_selected_at"
        ),
        {"p": plan, "uid": user_id},
    )
    r = row.mappings().first()
    if not r:
        return None
    return {"plan": r["plan"], "plan_selected_at": str(r["plan_selected_at"])}
