"""Overview metrics: real aggregate counts only. Each function is independently
callable so the service can degrade one metric to 'unavailable' without losing
the rest."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

Executor = Any


async def user_metrics(conn: Executor) -> dict[str, Any]:
    row = (
        await conn.execute(
            text(
                """
                SELECT
                    (SELECT count(*) FROM profiles) AS total_users,
                    (SELECT count(*) FROM auth.users
                        WHERE created_at >= now() - interval '7 days') AS new_users_7d,
                    (SELECT count(*) FROM auth.users
                        WHERE created_at >= now() - interval '30 days') AS new_users_30d,
                    (SELECT count(*) FROM auth.users
                        WHERE last_sign_in_at >= now() - interval '7 days') AS active_users_7d,
                    (SELECT count(*) FROM profiles
                        WHERE account_status = 'suspended') AS suspended_users
                """
            )
        )
    ).mappings().first()
    return {k: int(v) for k, v in dict(row).items()}


async def tier_distribution(conn: Executor) -> dict[str, int]:
    rows = (
        await conn.execute(
            text(
                "SELECT COALESCE(plan, 'Free') AS plan, count(*) AS n "
                "FROM profiles GROUP BY COALESCE(plan, 'Free')"
            )
        )
    ).mappings().all()
    return {r["plan"]: int(r["n"]) for r in rows}


async def engagement_metrics(conn: Executor) -> dict[str, Any]:
    row = (
        await conn.execute(
            text(
                """
                SELECT
                    (SELECT count(*) FROM psx_portfolios) AS portfolios,
                    (SELECT count(*) FROM user_watchlist) AS watchlist_entries,
                    (SELECT count(*) FROM price_alerts) AS price_alerts,
                    (SELECT count(*) FROM user_alerts) AS app_alerts,
                    (SELECT count(*) FROM ai_reports) AS ai_reports_total,
                    (SELECT count(*) FROM assistant_usage) AS assistant_events_total
                """
            )
        )
    ).mappings().first()
    return {k: int(v) for k, v in dict(row).items()}
