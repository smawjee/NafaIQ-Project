"""Plan entitlement data access (`plan_features`).

`plan_features` is live configuration, not a lookup of static copy: every column
here is read on the request path by `repositories/user_repo.py:get_plan_features`
and enforces a real limit. Editing it changes what users can do, which is why the
writable surface is pinned down in this module rather than being derived from
whatever a request body happens to contain.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any

# ---------------------------------------------------------------------------
# Writable surface. The UPDATE statement is built from THIS tuple, never from
# caller-supplied keys, so an unexpected field can't reach a column.
#
# Excluded on purpose:
#   plan       - the primary key / identity of the row
#   rank       - orders upgrade logic elsewhere; re-ranking plans from a settings
#                screen would silently reorder entitlement comparisons
#   updated_at - set by this module
# ---------------------------------------------------------------------------
INT_COLUMNS: tuple[str, ...] = (
    "max_watchlist",
    "max_price_alerts",
    "max_portfolios",
    "max_holdings_per_portfolio",
    "max_budgets",
    "max_bills",
    "max_goals",
    "max_finance_history_days",
)

# Nullable integers where NULL carries meaning: "no limit".
NULLABLE_INT_COLUMNS: tuple[str, ...] = (
    "ai_tutor_daily_limit",
    "ai_reports_per_period",
)

BOOL_COLUMNS: tuple[str, ...] = (
    "has_email_alerts",
    "has_push_alerts",
    "has_export",
    "has_multi_currency",
    "has_realtime_psx",
    "has_screener_full",
    "has_webhook_integration",
    "has_api_access",
)

ENUM_COLUMNS: dict[str, tuple[str, ...]] = {
    "ai_reports_period": ("day", "week", "month"),
}

TEXT_COLUMNS: tuple[str, ...] = ("description",)

EDITABLE_COLUMNS: frozenset[str] = frozenset(
    INT_COLUMNS + NULLABLE_INT_COLUMNS + BOOL_COLUMNS + TEXT_COLUMNS + tuple(ENUM_COLUMNS)
)

# Every column the API returns, in display order.
_SELECT = (
    "plan, rank, "
    + ", ".join(INT_COLUMNS + NULLABLE_INT_COLUMNS)
    + ", ai_reports_period, "
    + ", ".join(BOOL_COLUMNS)
    + ", description, updated_at"
)


async def list_plans(conn: Executor) -> list[dict[str, Any]]:
    """All plans, cheapest first (rank ascending)."""
    rows = (
        await conn.execute(text(f"SELECT {_SELECT} FROM plan_features ORDER BY rank"))
    ).mappings().all()
    return [dict(r) for r in rows]


async def get_plan(conn: Executor, plan: str) -> Optional[dict[str, Any]]:
    row = (
        await conn.execute(
            text(f"SELECT {_SELECT} FROM plan_features WHERE plan = :plan"), {"plan": plan}
        )
    ).mappings().first()
    return dict(row) if row else None


async def update_plan(
    conn: Executor, *, plan: str, changes: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """Apply a validated partial update.

    `changes` must already have been validated AND filtered to EDITABLE_COLUMNS by
    the service layer. Column names are still re-checked here so this function is
    safe on its own terms: they are interpolated into the SQL text (bind params
    cannot name a column), so an unchecked key would be an injection point.
    """
    cols = [c for c in changes if c in EDITABLE_COLUMNS]
    if not cols:
        return await get_plan(conn, plan)

    assignments = ", ".join(f"{c} = :{c}" for c in cols)
    params: dict[str, Any] = {c: changes[c] for c in cols}
    params["plan"] = plan

    row = (
        await conn.execute(
            text(
                f"""
                UPDATE plan_features
                   SET {assignments}, updated_at = now()
                 WHERE plan = :plan
             RETURNING {_SELECT}
                """
            ),
            params,
        )
    ).mappings().first()
    return dict(row) if row else None
