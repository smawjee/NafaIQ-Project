"""Periodic sync endpoints for finance data.

Recomputes derived values (e.g. budget.spent from actual transactions)
so alerts and UI reflect real spending.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.api.deps import require_user
from app.db.sqlalchemy import get_engine

router = APIRouter(tags=["finance-sync"])


@router.post("/finance/sync-budgets")
async def sync_budget_spent(user: Annotated[dict, Depends(require_user)]):
    """Recalculate user_budgets.spent from actual user_transactions.

    For each budget row, sum all expense transactions in the current month
    that match the budget's category (case-insensitive). Updates spent
    to reflect actual spending.
    """
    uid = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        # Update spent from transactions for current month
        result = await conn.execute(
            text(
                """
                UPDATE user_budgets b
                SET spent = COALESCE((
                    SELECT SUM(t.amount)
                    FROM user_transactions t
                    WHERE t.user_id = b.user_id
                      AND t.transaction_type = 'expense'
                      AND LOWER(t.category) = LOWER(b.category)
                      AND DATE_TRUNC('month', t.transaction_date)
                          = DATE_TRUNC('month', CURRENT_DATE)
                ), 0)
                WHERE b.user_id = :uid
                RETURNING b.id, b.category, b.spent, b.limit_amount
                """
            ),
            {"uid": uid},
        )
        rows = result.mappings().all()

    return {
        "updated": len(rows),
        "budgets": [
            {
                "id": r["id"],
                "category": r["category"],
                "spent": float(r["spent"]),
                "limit": float(r["limit_amount"]),
            }
            for r in rows
        ],
    }
