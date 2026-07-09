"""Finance data access: transactions, goals, budgets, bills, settings, and the
summary/series aggregations. All finance-domain SQL (SQLAlchemy Core + raw)
lives here. Functions take an executor and return plain Python data.

The service prepares/validates values (date coercion, type normalisation,
quota checks) and owns the transaction boundary; this module only persists.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import delete, insert, select, text, update

from app.db.orm import get_table
from app.db.sqlalchemy import ensure_reflected

Executor = Any


async def _table(name: str):
    await ensure_reflected()
    return get_table(name)


async def _count_owned(conn: Executor, table: str, uid: str) -> int:
    result = await conn.execute(
        text(f"SELECT COUNT(*) FROM {table} WHERE user_id = :uid"), {"uid": uid}
    )
    return int(result.scalar() or 0)


async def count_goals(conn: Executor, uid: str) -> int:
    return await _count_owned(conn, "user_goals", uid)


async def count_budgets(conn: Executor, uid: str) -> int:
    return await _count_owned(conn, "user_budgets", uid)


async def count_bills(conn: Executor, uid: str) -> int:
    return await _count_owned(conn, "user_bills", uid)


# ---------- serializers (row -> dict) ----------


def _transaction(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "merchant": row["merchant"],
        "amount": float(row["amount"]),
        "currency": row["currency"],
        "transaction_type": row["transaction_type"],
        "category": row["category"],
        "transaction_date": str(row["transaction_date"]),
        "source": row["source"],
        "note": row["note"],
        "created_at": str(row["created_at"]),
    }


def _goal(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": str(row["user_id"]),
        "emoji": row["emoji"],
        "name": row["name"],
        "target": float(row["target"]),
        "saved": float(row["saved"]),
        "color": row["color"],
        "ai_tip": row["ai_tip"],
        "target_date": str(row["target_date"])[:10] if row["target_date"] else None,
        "created_at": str(row["created_at"]),
    }


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


def _bill(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": str(row["user_id"]),
        "name": row["name"],
        "amount": float(row["amount"]),
        "currency": row["currency"],
        "due_date": str(row["due_date"]) if row["due_date"] else None,
        "status": row["status"],
        "recurring": row["recurring"],
        "paid_at": str(row["paid_at"]) if row["paid_at"] else None,
        "created_at": str(row["created_at"]),
    }


# ---------- transactions ----------


async def list_transactions(conn: Executor, uid: str, limit: int) -> list[dict[str, Any]]:
    txns = await _table("user_transactions")
    result = await conn.execute(
        select(txns)
        .where(txns.c.user_id == uid)
        .order_by(txns.c.transaction_date.desc())
        .limit(max(1, min(limit, 500)))
    )
    return [_transaction(r) for r in result.mappings().all()]


async def insert_transaction(conn: Executor, values: dict[str, Any]) -> dict[str, Any]:
    txns = await _table("user_transactions")
    result = await conn.execute(insert(txns).values(**values).returning(txns))
    return _transaction(result.mappings().first())


async def update_transaction(
    conn: Executor, uid: str, txn_id: int, values: dict[str, Any]
) -> Optional[dict[str, Any]]:
    txns = await _table("user_transactions")
    result = await conn.execute(
        update(txns)
        .where(txns.c.id == txn_id, txns.c.user_id == uid)
        .values(**values)
        .returning(txns)
    )
    row = result.mappings().first()
    return _transaction(row) if row else None


async def delete_transaction(conn: Executor, uid: str, txn_id: int) -> Optional[int]:
    txns = await _table("user_transactions")
    result = await conn.execute(
        delete(txns).where(txns.c.id == txn_id, txns.c.user_id == uid).returning(txns.c.id)
    )
    row = result.first()
    return txn_id if row else None


# ---------- goals ----------


async def list_goals(conn: Executor, uid: str) -> list[dict[str, Any]]:
    goals = await _table("user_goals")
    result = await conn.execute(
        select(goals).where(goals.c.user_id == uid).order_by(goals.c.created_at.desc())
    )
    return [_goal(r) for r in result.mappings().all()]


async def insert_goal(conn: Executor, values: dict[str, Any]) -> dict[str, Any]:
    goals = await _table("user_goals")
    result = await conn.execute(insert(goals).values(**values).returning(goals))
    return _goal(result.mappings().first())


async def contribute_goal(
    conn: Executor, uid: str, goal_id: int, amount: float
) -> Optional[dict[str, Any]]:
    goals = await _table("user_goals")
    result = await conn.execute(
        update(goals)
        .where(goals.c.id == goal_id, goals.c.user_id == uid)
        .values(saved=text("LEAST(saved + :amount, target)"))
        .returning(goals),
        {"amount": amount},
    )
    row = result.mappings().first()
    return _goal(row) if row else None


async def delete_goal(conn: Executor, uid: str, goal_id: int) -> Optional[int]:
    goals = await _table("user_goals")
    result = await conn.execute(
        delete(goals).where(goals.c.id == goal_id, goals.c.user_id == uid).returning(goals.c.id)
    )
    row = result.first()
    return goal_id if row else None


# ---------- budgets ----------


async def list_budgets(conn: Executor, uid: str) -> list[dict[str, Any]]:
    budgets = await _table("user_budgets")
    result = await conn.execute(
        select(budgets).where(budgets.c.user_id == uid).order_by(budgets.c.category)
    )
    return [_budget(r) for r in result.mappings().all()]


async def insert_budget(conn: Executor, values: dict[str, Any]) -> dict[str, Any]:
    budgets = await _table("user_budgets")
    result = await conn.execute(insert(budgets).values(**values).returning(budgets))
    return _budget(result.mappings().first())


async def update_budget(
    conn: Executor, uid: str, budget_id: int, values: dict[str, Any]
) -> Optional[dict[str, Any]]:
    budgets = await _table("user_budgets")
    result = await conn.execute(
        update(budgets)
        .where(budgets.c.id == budget_id, budgets.c.user_id == uid)
        .values(**values)
        .returning(budgets)
    )
    row = result.mappings().first()
    return _budget(row) if row else None


async def delete_budget(conn: Executor, uid: str, budget_id: int) -> Optional[int]:
    budgets = await _table("user_budgets")
    result = await conn.execute(
        delete(budgets).where(budgets.c.id == budget_id, budgets.c.user_id == uid).returning(budgets.c.id)
    )
    row = result.first()
    return budget_id if row else None


# ---------- bills ----------


async def list_bills(conn: Executor, uid: str) -> list[dict[str, Any]]:
    bills = await _table("user_bills")
    result = await conn.execute(
        select(bills)
        .where(bills.c.user_id == uid)
        .order_by(bills.c.due_date.asc().nulls_last(), bills.c.created_at.desc())
    )
    return [_bill(r) for r in result.mappings().all()]


async def insert_bill(conn: Executor, values: dict[str, Any]) -> dict[str, Any]:
    bills = await _table("user_bills")
    result = await conn.execute(insert(bills).values(**values).returning(bills))
    return _bill(result.mappings().first())


async def update_bill(
    conn: Executor, uid: str, bill_id: int, values: dict[str, Any]
) -> Optional[dict[str, Any]]:
    bills = await _table("user_bills")
    result = await conn.execute(
        update(bills)
        .where(bills.c.id == bill_id, bills.c.user_id == uid)
        .values(**values)
        .returning(bills)
    )
    row = result.mappings().first()
    return _bill(row) if row else None


async def mark_bill_paid(conn: Executor, uid: str, bill_id: int) -> Optional[dict[str, Any]]:
    bills = await _table("user_bills")
    result = await conn.execute(
        update(bills)
        .where(bills.c.id == bill_id, bills.c.user_id == uid)
        .values(status="PAID", paid_at=text("now()"))
        .returning(bills)
    )
    row = result.mappings().first()
    return _bill(row) if row else None


async def delete_bill(conn: Executor, uid: str, bill_id: int) -> Optional[int]:
    bills = await _table("user_bills")
    result = await conn.execute(
        delete(bills).where(bills.c.id == bill_id, bills.c.user_id == uid).returning(bills.c.id)
    )
    row = result.first()
    return bill_id if row else None


# ---------- settings ----------


async def get_settings_row(conn: Executor, uid: str) -> Optional[dict[str, Any]]:
    result = await conn.execute(
        text("SELECT monthly_income, currency, language, plan FROM user_settings WHERE user_id = :uid"),
        {"uid": uid},
    )
    row = result.mappings().first()
    if not row:
        return None
    return {
        "monthly_income": float(row["monthly_income"]),
        "currency": row["currency"],
        "language": row["language"],
        "plan": row["plan"],
    }


async def upsert_settings(
    conn: Executor,
    uid: str,
    *,
    monthly_income: Optional[float],
    currency: Optional[str],
    language: Optional[str],
) -> None:
    sets = []
    params: dict[str, Any] = {
        "uid": uid,
        "income": monthly_income,
        "cur": currency,
        "lang": language,
        "plan": None,
    }
    if monthly_income is not None:
        sets.append("monthly_income = :income")
    if currency is not None:
        sets.append("currency = :cur")
    if language is not None:
        sets.append("language = :lang")
    if not sets:
        return
    sets.append("updated_at = now()")
    update_clause = ", ".join(sets)
    await conn.execute(
        text(
            "INSERT INTO user_settings (user_id, monthly_income, currency, language, plan) "
            "VALUES (:uid, COALESCE(:income, 0), COALESCE(:cur, 'PKR'), COALESCE(:lang, 'en'), COALESCE(:plan, 'Free')) "
            f"ON CONFLICT (user_id) DO UPDATE SET {update_clause}"
        ),
        params,
    )


# ---------- summary / series aggregations (raw rows; service shapes) ----------


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


# ---------- sync ----------


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
    return [
        {
            "id": r["id"],
            "category": r["category"],
            "spent": float(r["spent"]),
            "limit": float(r["limit_amount"]),
        }
        for r in result.mappings().all()
    ]
