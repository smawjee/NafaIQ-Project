"""Admin user data access: listing, detail, status, tier, notes, lookup.

Reads join public.profiles with auth.users. Writes to profiles are performed
here (privileged pooler role), never by the browser.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any

# Whitelisted sort columns — the API maps a client sort key to one of these.
# Never interpolate a raw client string into ORDER BY.
_SORT_COLUMNS: dict[str, str] = {
    "created_at": "u.created_at",
    "last_sign_in_at": "u.last_sign_in_at",
    "email": "u.email",
    "display_name": "p.display_name",
    "plan": "p.plan",
    "account_status": "p.account_status",
}

# Per-user activity counts. Every table is user_id-scoped (RLS enforces it).
_ACTIVITY_TABLES: dict[str, str] = {
    "portfolios": "psx_portfolios",
    "transactions": "user_transactions",
    "stock_trades": "stock_transactions",
    "watchlist": "user_watchlist",
    "price_alerts": "price_alerts",
    "app_alerts": "user_alerts",
    "budgets": "user_budgets",
    "bills": "user_bills",
    "goals": "user_goals",
    "ai_reports": "ai_reports",
    "assistant_messages": "assistant_usage",
}


async def find_by_email(conn: Executor, email: str) -> Optional[dict[str, Any]]:
    row = (
        await conn.execute(
            text("SELECT id, email FROM auth.users WHERE lower(email) = lower(:e)"),
            {"e": email},
        )
    ).mappings().first()
    return dict(row) if row else None


async def list_users(
    conn: Executor,
    *,
    query: Optional[str] = None,
    status: Optional[str] = None,
    plan: Optional[str] = None,
    sort: str = "created_at",
    descending: bool = True,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    where = ["TRUE"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if query:
        where.append("(u.email ILIKE :q OR p.display_name ILIKE :q)")
        params["q"] = f"%{query}%"
    if status:
        where.append("COALESCE(p.account_status, 'active') = :status")
        params["status"] = status
    if plan:
        where.append("p.plan = :plan")
        params["plan"] = plan
    clause = " AND ".join(where)

    order_col = _SORT_COLUMNS.get(sort, "u.created_at")
    order_dir = "DESC" if descending else "ASC"

    total = (
        await conn.execute(
            text(
                f"SELECT count(*) FROM profiles p "
                f"JOIN auth.users u ON u.id = p.id WHERE {clause}"
            ),
            params,
        )
    ).scalar() or 0

    rows = (
        await conn.execute(
            text(
                f"""
                SELECT p.id, u.email, p.display_name, p.plan,
                       COALESCE(p.account_status, 'active') AS account_status,
                       u.created_at, u.last_sign_in_at
                FROM profiles p
                JOIN auth.users u ON u.id = p.id
                WHERE {clause}
                ORDER BY {order_col} {order_dir} NULLS LAST
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
    ).mappings().all()
    return [dict(r) for r in rows], int(total)


async def get_user(conn: Executor, user_id: str) -> Optional[dict[str, Any]]:
    row = (
        await conn.execute(
            text(
                """
                SELECT p.id, u.email, p.display_name, p.plan,
                       COALESCE(p.account_status, 'active') AS account_status,
                       p.status_reason, p.status_changed_at, p.status_changed_by,
                       p.plan_selected_at, p.avatar_url,
                       u.created_at, u.last_sign_in_at, u.email_confirmed_at
                FROM profiles p
                JOIN auth.users u ON u.id = p.id
                WHERE p.id = :uid
                """
            ),
            {"uid": user_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def activity_counts(conn: Executor, user_id: str) -> dict[str, int]:
    """One-shot activity aggregate via scalar subqueries. Every table is
    user_id-scoped. Raises if a table/column is missing — the caller treats a
    failure as 'unavailable' rather than fabricating a number."""
    selects = ",\n".join(
        f"(SELECT count(*) FROM {tbl} WHERE user_id = :uid) AS {key}"
        for key, tbl in _ACTIVITY_TABLES.items()
    )
    row = (
        await conn.execute(text(f"SELECT {selects}"), {"uid": user_id})
    ).mappings().first()
    return {k: int(v) for k, v in dict(row).items()}


async def set_status(
    conn: Executor,
    *,
    user_id: str,
    status: str,
    reason: Optional[str],
    changed_by: Optional[str],
) -> Optional[dict[str, Any]]:
    row = (
        await conn.execute(
            text(
                """
                UPDATE profiles
                SET account_status = :status,
                    status_reason = :reason,
                    status_changed_at = now(),
                    status_changed_by = :by
                WHERE id = :uid
                RETURNING id, account_status, status_reason
                """
            ),
            {"status": status, "reason": reason, "by": changed_by, "uid": user_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def set_plan(
    conn: Executor, *, user_id: str, plan: str
) -> Optional[dict[str, Any]]:
    row = (
        await conn.execute(
            text(
                "UPDATE profiles SET plan = :p, plan_selected_at = now() "
                "WHERE id = :uid RETURNING id, plan"
            ),
            {"p": plan, "uid": user_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def add_note(
    conn: Executor, *, user_id: str, author_id: Optional[str], note: str
) -> dict[str, Any]:
    row = (
        await conn.execute(
            text(
                "INSERT INTO admin_user_notes (user_id, author_id, note) "
                "VALUES (:uid, :author, :note) RETURNING id, created_at"
            ),
            {"uid": user_id, "author": author_id, "note": note},
        )
    ).mappings().first()
    return dict(row)


async def list_notes(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    rows = (
        await conn.execute(
            text(
                "SELECT id, author_id, note, created_at FROM admin_user_notes "
                "WHERE user_id = :uid ORDER BY created_at DESC"
            ),
            {"uid": user_id},
        )
    ).mappings().all()
    return [dict(r) for r in rows]
