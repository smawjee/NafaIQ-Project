"""Source reads the alert evaluators run over: the user's enabled alerts and
the finance rows they reference (budget by category, goal by name, bill by
name), plus a per-alert dedup check."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

from app.repositories.alerts._common import jsonb

Executor = Any


async def fetch_enabled_user_alerts(conn: Executor) -> list[dict[str, Any]]:
    """All enabled app-created alerts (the opt-in source: bill/budget/goal/
    stock_price), with meta parsed to a dict."""
    rows = await conn.execute(
        text(
            "SELECT id, user_id, type, title, meta, enabled "
            "FROM user_alerts WHERE enabled = TRUE"
        )
    )
    out: list[dict[str, Any]] = []
    for r in rows.mappings().all():
        d = dict(r)
        d["meta"] = jsonb(r["meta"])
        out.append(d)
    return out


async def get_budget_by_category(
    conn: Executor, user_id: str, category: str
) -> Optional[dict[str, Any]]:
    """One budget with live-computed current-month spent (excluding stock trades)."""
    rows = await conn.execute(
        text(
            """
            SELECT b.category, b.limit_amount,
                COALESCE((
                    SELECT SUM(t.amount) FROM user_transactions t
                    WHERE t.user_id = b.user_id
                      AND t.transaction_type = 'expense'
                      AND (t.source IS DISTINCT FROM 'stock_trade')
                      AND LOWER(t.category) = LOWER(b.category)
                      AND DATE_TRUNC('month', t.transaction_date)
                          = DATE_TRUNC('month', CURRENT_DATE)
                ), 0)::numeric AS spent
            FROM user_budgets b
            WHERE b.user_id = :uid AND LOWER(b.category) = LOWER(:cat)
            LIMIT 1
            """
        ),
        {"uid": user_id, "cat": category},
    )
    r = rows.mappings().first()
    if not r:
        return None
    return {"category": r["category"], "limit_amount": float(r["limit_amount"]), "spent": float(r["spent"])}


async def get_goal_by_name(
    conn: Executor, user_id: str, name: str
) -> Optional[dict[str, Any]]:
    rows = await conn.execute(
        text(
            "SELECT name, saved, target FROM user_goals "
            "WHERE user_id = :uid AND LOWER(name) = LOWER(:name) LIMIT 1"
        ),
        {"uid": user_id, "name": name},
    )
    r = rows.mappings().first()
    if not r:
        return None
    return {"name": r["name"], "saved": float(r["saved"]), "target": float(r["target"])}


async def get_bill_by_name(
    conn: Executor, user_id: str, name: str
) -> Optional[dict[str, Any]]:
    rows = await conn.execute(
        text(
            "SELECT name, amount, due_date, status FROM user_bills "
            "WHERE user_id = :uid AND LOWER(name) = LOWER(:name) LIMIT 1"
        ),
        {"uid": user_id, "name": name},
    )
    r = rows.mappings().first()
    if not r:
        return None
    return {
        "name": r["name"],
        "amount": float(r["amount"]),
        "due_date": r["due_date"],
        "status": r["status"],
    }


async def recent_event_for_alert(conn: Executor, alert_id: int) -> bool:
    """24h dedup for a specific user_alert (one notification per alert per day)."""
    rows = await conn.execute(
        text(
            "SELECT id FROM alert_events "
            "WHERE alert_id = :aid AND created_at > now() - INTERVAL '24 hours' LIMIT 1"
        ),
        {"aid": alert_id},
    )
    return rows.first() is not None


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
