"""Finance budgets data access (user_budgets), incl. live-spent computation."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import delete, insert, text, update

from app.repositories.finance._common import count_owned, table

Executor = Any

# --------------------------------------------------------------------------
# THE definition of "money spent against a budget". Correlated on alias `b`,
# so every consumer must alias user_budgets as `b`.
#
# This exists as one shared string because the 2026-07-22 audit found FOUR
# copies of this logic with THREE different behaviours: the budgets screen and
# the alert engine matched categories differently (case-sensitive vs not), and
# the alert engine's bulk fetch read a stale stored column entirely. Two users
# were ~50k over budget with no alert firing. Divergence was the defect, so the
# fix is a single definition — do not inline a variant of this anywhere.
#
# Semantics:
#   - expenses only; stock trades are never budget spend (they are reflections
#     of a portfolio buy, and the finance aggregates exclude them too)
#   - category matched case- and whitespace-insensitively, because budgets and
#     transactions are written by different forms ("bills" vs "Bills")
#   - the window follows b.period. It used to be hardcoded to the calendar
#     month, so a weekly budget silently reported monthly spend.
# --------------------------------------------------------------------------
_PERIOD_START = """
        CASE lower(b.period)
            WHEN 'weekly'    THEN date_trunc('week',    CURRENT_DATE)
            WHEN 'quarterly' THEN date_trunc('quarter', CURRENT_DATE)
            WHEN 'yearly'    THEN date_trunc('year',    CURRENT_DATE)
            ELSE                  date_trunc('month',   CURRENT_DATE)
        END"""

_PERIOD_END = """
        CASE lower(b.period)
            WHEN 'weekly'    THEN date_trunc('week',    CURRENT_DATE) + INTERVAL '1 week'
            WHEN 'quarterly' THEN date_trunc('quarter', CURRENT_DATE) + INTERVAL '3 months'
            WHEN 'yearly'    THEN date_trunc('year',    CURRENT_DATE) + INTERVAL '1 year'
            ELSE                  date_trunc('month',   CURRENT_DATE) + INTERVAL '1 month'
        END"""

BUDGET_SPENT_SQL = f"""COALESCE((
        SELECT SUM(t.amount)
        FROM user_transactions t
        WHERE t.user_id = b.user_id
          AND t.transaction_type = 'expense'
          AND (t.source IS DISTINCT FROM 'stock_trade')
          AND lower(btrim(t.category)) = lower(btrim(b.category))
          AND t.transaction_date >= {_PERIOD_START}
          AND t.transaction_date <  {_PERIOD_END}
    ), 0)::numeric"""


def _budget(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": str(row["user_id"]),
        "category": row["category"],
        "spent": float(row["spent"]),
        "limit_amount": float(row["limit_amount"]),
        "period": row["period"],
        "tip": row["tip"],
        "created_at": str(row["created_at"]),
    }


async def count_budgets(conn: Executor, uid: str) -> int:
    return await count_owned(conn, "user_budgets", uid)


async def list_budgets(conn: Executor, uid: str) -> list[dict[str, Any]]:
    # `spent` is computed live via the shared BUDGET_SPENT_SQL definition, so the
    # screen never depends on the stored column being in sync.
    result = await conn.execute(
        text(
            f"""
            SELECT
                b.id, b.user_id, b.category,
                {BUDGET_SPENT_SQL} AS spent,
                b.limit_amount, b.period, b.tip, b.created_at
            FROM user_budgets b
            WHERE b.user_id = :uid
            ORDER BY b.category
            """
        ),
        {"uid": uid},
    )
    return [_budget(r) for r in result.mappings().all()]


async def get_budget(conn: Executor, uid: str, budget_id: int) -> Optional[dict[str, Any]]:
    """One budget with live-computed spent."""
    result = await conn.execute(
        text(
            f"""
            SELECT b.id, b.user_id, b.category,
                   {BUDGET_SPENT_SQL} AS spent,
                   b.limit_amount, b.period, b.tip, b.created_at
            FROM user_budgets b
            WHERE b.user_id = :uid AND b.id = :bid
            """
        ),
        {"uid": uid, "bid": budget_id},
    )
    row = result.mappings().first()
    return _budget(row) if row else None


async def insert_budget(conn: Executor, values: dict[str, Any]) -> dict[str, Any]:
    budgets = await table("user_budgets")
    result = await conn.execute(insert(budgets).values(**values).returning(budgets))
    return _budget(result.mappings().first())


async def update_budget(
    conn: Executor, uid: str, budget_id: int, values: dict[str, Any]
) -> Optional[dict[str, Any]]:
    budgets = await table("user_budgets")
    result = await conn.execute(
        update(budgets)
        .where(budgets.c.id == budget_id, budgets.c.user_id == uid)
        .values(**values)
        .returning(budgets)
    )
    row = result.mappings().first()
    return _budget(row) if row else None


async def delete_budget(conn: Executor, uid: str, budget_id: int) -> Optional[int]:
    budgets = await table("user_budgets")
    result = await conn.execute(
        delete(budgets).where(budgets.c.id == budget_id, budgets.c.user_id == uid).returning(budgets.c.id)
    )
    row = result.first()
    return budget_id if row else None


async def recompute_budget_spent(conn: Executor, uid: str) -> list[dict[str, Any]]:
    """Refresh the stored `spent` column from real transactions.

    Called after every transaction write (and by POST /finance/sync-budgets), so
    the stored column stays usable by anything reading it directly.
    """
    result = await conn.execute(
        text(
            f"""
            UPDATE user_budgets b
            SET spent = {BUDGET_SPENT_SQL}
            WHERE b.user_id = :uid
            RETURNING b.id, b.category, b.spent, b.limit_amount
            """
        ),
        {"uid": uid},
    )
    return [
        {
            "id": r["id"],
            "category": r["category"],
            "spent": float(r["spent"]),
            "limit": float(r["limit_amount"]),
        }
        for r in result.mappings().all()
    ]
