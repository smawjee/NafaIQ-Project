"""Aggregate alert metrics for the admin console.

Read-only and aggregate-only: the console reports on alert *volume and delivery
health* across the platform. It deliberately does not expose individual users'
alert contents — an admin has no operational need to read what a specific user
is watching, and the audit story is much simpler if that data never leaves the
user's own session.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

Executor = Any


async def price_alert_summary(conn: Executor) -> dict[str, Any]:
    row = (
        await conn.execute(
            text(
                """
                SELECT
                    count(*)                                          AS total,
                    count(*) FILTER (WHERE enabled)                   AS enabled,
                    count(*) FILTER (WHERE triggered_at IS NOT NULL)  AS ever_triggered,
                    count(*) FILTER (WHERE triggered_at >= now() - interval '24 hours')
                                                                      AS triggered_24h,
                    count(DISTINCT user_id)                           AS users_with_alerts,
                    count(DISTINCT symbol)                            AS symbols_watched
                FROM price_alerts
                """
            )
        )
    ).mappings().first()
    return {k: int(v or 0) for k, v in dict(row).items()}


async def app_alert_summary(conn: Executor) -> dict[str, Any]:
    row = (
        await conn.execute(
            text(
                """
                SELECT
                    count(*)                                         AS total,
                    count(*) FILTER (WHERE enabled)                  AS enabled,
                    count(*) FILTER (WHERE type = 'bill')            AS bill,
                    count(*) FILTER (WHERE type = 'budget')          AS budget,
                    count(*) FILTER (WHERE type = 'goal')            AS goal,
                    count(*) FILTER (WHERE type = 'stock_price')     AS stock_price,
                    count(DISTINCT user_id)                          AS users_with_alerts
                FROM user_alerts
                """
            )
        )
    ).mappings().first()
    return {k: int(v or 0) for k, v in dict(row).items()}


async def delivery_health(conn: Executor) -> dict[str, Any]:
    """Delivery outcomes over the last 7 days, by channel.

    `delivered_at IS NULL` on an older event means the evaluator created it but
    delivery never completed — that is the number worth watching.
    """
    row = (
        await conn.execute(
            text(
                """
                SELECT
                    count(*)                                            AS events_7d,
                    count(*) FILTER (WHERE delivered_at IS NOT NULL)    AS delivered,
                    count(*) FILTER (WHERE delivered_at IS NULL)        AS undelivered,
                    count(*) FILTER (WHERE read_at IS NOT NULL)         AS read,
                    count(*) FILTER (WHERE channel = 'in_app')          AS via_in_app,
                    count(*) FILTER (WHERE channel = 'email')           AS via_email,
                    count(*) FILTER (WHERE channel = 'push')            AS via_push
                FROM alert_events
                WHERE created_at >= now() - interval '7 days'
                """
            )
        )
    ).mappings().first()
    return {k: int(v or 0) for k, v in dict(row).items()}


async def events_by_day(conn: Executor) -> dict[str, Any]:
    """Daily alert-event counts for the last 14 days (PKT day boundaries)."""
    rows = (
        await conn.execute(
            text(
                """
                SELECT
                    to_char((created_at AT TIME ZONE 'Asia/Karachi')::date, 'Mon DD') AS label,
                    count(*) AS value
                FROM alert_events
                WHERE created_at >= now() - interval '14 days'
                GROUP BY 1, (created_at AT TIME ZONE 'Asia/Karachi')::date
                ORDER BY (created_at AT TIME ZONE 'Asia/Karachi')::date
                """
            )
        )
    ).mappings().all()
    return {"items": [{"label": r["label"], "value": int(r["value"])} for r in rows]}


async def top_symbols(conn: Executor, limit: int = 10) -> dict[str, Any]:
    """Most-watched symbols across all price alerts."""
    rows = (
        await conn.execute(
            text(
                """
                SELECT symbol,
                       count(*)                        AS alerts,
                       count(DISTINCT user_id)         AS users
                FROM price_alerts
                WHERE enabled
                GROUP BY symbol
                ORDER BY count(*) DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
    ).mappings().all()
    return {
        "items": [
            {"symbol": r["symbol"], "alerts": int(r["alerts"]), "users": int(r["users"])}
            for r in rows
        ]
    }
