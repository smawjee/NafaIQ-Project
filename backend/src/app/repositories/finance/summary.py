"""Finance summary / series aggregations (raw rows; the service shapes them)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

Executor = Any


async def fetch_month_totals(conn: Executor, uid: str, month: str) -> dict[str, float]:
    """{transaction_type: total} for one YYYY-MM, excluding stock trades."""
    result = await conn.execute(
        text(
            """
            SELECT transaction_type, COALESCE(SUM(amount), 0)::numeric AS total
            FROM user_transactions
            WHERE user_id = :uid
              AND (source IS DISTINCT FROM 'stock_trade')
              AND DATE_TRUNC('month', transaction_date) = DATE_TRUNC('month', TO_DATE(:month, 'YYYY-MM'))
            GROUP BY transaction_type
            """
        ),
        {"uid": uid, "month": month},
    )
    return {r["transaction_type"].lower(): float(r["total"]) for r in result.mappings().all()}


async def fetch_income_expense(conn: Executor, uid: str, months: int) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            """
            SELECT
                TO_CHAR(DATE_TRUNC('month', transaction_date), 'YYYY-MM') AS month,
                transaction_type,
                COALESCE(SUM(amount), 0)::numeric AS total
            FROM user_transactions
            WHERE user_id = :uid
              -- Stock trades are investment activity, not income/expense:
              -- keep them out of the income/expense chart.
              AND (source IS DISTINCT FROM 'stock_trade')
              AND transaction_date >= DATE_TRUNC('month', CURRENT_DATE) - (:months - 1) * INTERVAL '1 month'
            GROUP BY 1, transaction_type
            ORDER BY 1 ASC
            """
        ),
        {"uid": uid, "months": months},
    )
    return [
        {"month": r["month"], "transaction_type": r["transaction_type"], "total": float(r["total"])}
        for r in result.mappings().all()
    ]


async def fetch_spending(conn: Executor, uid: str, days: int) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            """
            SELECT category, COALESCE(SUM(amount), 0)::numeric AS amount
            FROM user_transactions
            WHERE user_id = :uid
              AND transaction_type = 'expense'
              -- Exclude stock purchases (category 'Investment') from the
              -- spending breakdown: they are investment activity, not spending.
              AND (source IS DISTINCT FROM 'stock_trade')
              AND transaction_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
            GROUP BY category
            ORDER BY amount DESC
            """
        ),
        {"uid": uid, "days": days},
    )
    return [{"category": r["category"], "amount": float(r["amount"])} for r in result.mappings().all()]
