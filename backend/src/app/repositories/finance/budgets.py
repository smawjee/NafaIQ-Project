"""Finance budgets data access (user_budgets), incl. live-spent computation."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import delete, insert, text, update

from app.repositories.finance._common import count_owned, table

Executor = Any


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
    # `spent` is computed live from the current month's expense transactions
    # (category-matched, case-insensitive, excluding stock trades) so budget
    # usage always reflects real spending without depending on a sync call.
    result = await conn.execute(
        text(
            """
            SELECT
                b.id, b.user_id, b.category,
                COALESCE((
                    SELECT SUM(t.amount)
                    FROM user_transactions t
                    WHERE t.user_id = b.user_id
                      AND t.transaction_type = 'expense'
                      AND (t.source IS DISTINCT FROM 'stock_trade')
                      AND lower(t.category) = lower(b.category)
                      AND DATE_TRUNC('month', t.transaction_date)
                          = DATE_TRUNC('month', CURRENT_DATE)
                ), 0)::numeric AS spent,
                b.limit_amount, b.period, b.tip, b.created_at
            FROM user_budgets b
            WHERE b.user_id = :uid
            ORDER BY b.category
            """
        ),
        {"uid": uid},
    )
    return [_budget(r) for r in result.mappings().all()]


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
    result = await conn.execute(
        text(
            """
            UPDATE user_budgets b
            SET spent = COALESCE((
                SELECT SUM(t.amount)
                FROM user_transactions t
                WHERE t.user_id = b.user_id
                  AND t.transaction_type = 'expense'
                  -- Stock trades never count toward category budgets.
                  AND (t.source IS DISTINCT FROM 'stock_trade')
                  AND lower(t.category) = lower(b.category)
                  AND DATE_TRUNC('month', t.transaction_date)
                      = DATE_TRUNC('month', CURRENT_DATE)
            ), 0)
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
