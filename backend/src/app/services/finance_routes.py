from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import delete, insert, select, text, update

from app.db.orm import get_table
from app.db.sqlalchemy import ensure_reflected, get_engine
from app.models.finance import (
    BillCreate,
    BillUpdate,
    BudgetCreate,
    BudgetUpdate,
    FinanceSummaryResponse,
    GoalCreate,
    IncomeExpensePoint,
    IncomeExpenseResponse,
    SettingsUpdate,
    SpendingByCategoryResponse,
    SpendingCategory,
    TransactionCreate,
    TransactionUpdate,
)
from app.services.permissions import enforce_count_limit, limit_for


async def _table(name: str):
    await ensure_reflected()
    return get_table(name)


def _transaction_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"income", "expense"}:
        raise HTTPException(400, "transaction_type must be income or expense")
    return normalized


def _as_date(value: Any) -> Optional[date]:
    """Coerce an ISO date string to a date (asyncpg DATE columns reject strings)."""
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise HTTPException(400, f"Invalid date: {value!r} (expected YYYY-MM-DD)")


def _as_timestamp(value: Any) -> Optional[datetime]:
    """Coerce an ISO datetime/date string to a datetime for timestamptz columns."""
    if value is None or isinstance(value, datetime):
        return value
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, f"Invalid datetime: {value!r} (expected ISO 8601)")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _serialize_transaction(row: Any) -> dict[str, Any]:
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


def _serialize_goal(row: Any) -> dict[str, Any]:
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


def _serialize_budget(row: Any) -> dict[str, Any]:
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


def _serialize_bill(row: Any) -> dict[str, Any]:
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


async def list_transactions(uid: str, limit: int = 100) -> list[dict[str, Any]]:
    txns = await _table("user_transactions")
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            select(txns)
            .where(txns.c.user_id == uid)
            .order_by(txns.c.transaction_date.desc())
            .limit(max(1, min(limit, 500))),
        )
        rows = result.mappings().all()
    return [_serialize_transaction(r) for r in rows]


async def create_transaction(uid: str, body: TransactionCreate) -> dict[str, Any]:
    txns = await _table("user_transactions")
    values = {
        "user_id": uid,
        "merchant": body.merchant.strip(),
        "amount": abs(body.amount),
        "transaction_type": _transaction_type(body.transaction_type),
        "category": body.category.strip(),
        "source": body.source,
        "note": body.note,
    }
    if body.transaction_date is not None:
        values["transaction_date"] = _as_timestamp(body.transaction_date)
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(insert(txns).values(**values).returning(txns))
        row = result.mappings().first()
    return _serialize_transaction(row)


async def update_transaction(uid: str, txn_id: int, body: TransactionUpdate) -> dict[str, Any]:
    values = body.model_dump(exclude_unset=True)
    if "transaction_type" in values and values["transaction_type"] is not None:
        values["transaction_type"] = _transaction_type(values["transaction_type"])
    if "amount" in values and values["amount"] is not None:
        values["amount"] = abs(values["amount"])
    if "transaction_date" in values:
        values["transaction_date"] = _as_timestamp(values["transaction_date"])
    if not values:
        raise HTTPException(400, "No fields to update")
    txns = await _table("user_transactions")
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            update(txns)
            .where(txns.c.id == txn_id, txns.c.user_id == uid)
            .values(**values)
            .returning(txns),
        )
        row = result.mappings().first()
    if not row:
        raise HTTPException(404, "Transaction not found")
    return _serialize_transaction(row)


async def delete_transaction(uid: str, txn_id: int) -> dict[str, int]:
    txns = await _table("user_transactions")
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            delete(txns).where(txns.c.id == txn_id, txns.c.user_id == uid).returning(txns.c.id),
        )
        row = result.first()
    if not row:
        raise HTTPException(404, "Transaction not found")
    return {"deleted": txn_id}


async def list_goals(uid: str) -> list[dict[str, Any]]:
    goals = await _table("user_goals")
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            select(goals).where(goals.c.user_id == uid).order_by(goals.c.created_at.desc()),
        )
        rows = result.mappings().all()
    return [_serialize_goal(r) for r in rows]


async def create_goal(uid: str, body: GoalCreate, user: dict) -> dict[str, Any]:
    goals = await _table("user_goals")
    engine = get_engine()
    async with engine.begin() as conn:
        await enforce_count_limit(
            conn,
            user,
            feature_key="max_goals",
            count_sql="SELECT COUNT(*) FROM user_goals WHERE user_id = :uid",
            params={"uid": uid},
            label="Savings goals",
        )
        result = await conn.execute(
            insert(goals)
            .values(
                user_id=uid,
                emoji=body.emoji,
                name=body.name.strip(),
                target=body.target,
                saved=body.saved,
                color=body.color,
                ai_tip=body.ai_tip,
                # target_date is timestamptz in the live schema: store midnight
                # UTC of the chosen date so the calendar date never shifts.
                target_date=_as_timestamp(body.target_date),
            )
            .returning(goals),
        )
        row = result.mappings().first()
    return _serialize_goal(row)


async def contribute_goal(uid: str, goal_id: int, amount: float) -> dict[str, Any]:
    if amount <= 0:
        raise HTTPException(400, "Contribution amount must be positive")
    goals = await _table("user_goals")
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            update(goals)
            .where(goals.c.id == goal_id, goals.c.user_id == uid)
            .values(saved=text("LEAST(saved + :amount, target)"))
            .returning(goals),
            {"amount": amount},
        )
        row = result.mappings().first()
    if not row:
        raise HTTPException(404, "Goal not found")
    return _serialize_goal(row)


async def delete_goal(uid: str, goal_id: int) -> dict[str, int]:
    goals = await _table("user_goals")
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            delete(goals).where(goals.c.id == goal_id, goals.c.user_id == uid).returning(goals.c.id),
        )
        row = result.first()
    if not row:
        raise HTTPException(404, "Goal not found")
    return {"deleted": goal_id}


async def list_budgets(uid: str) -> list[dict[str, Any]]:
    budgets = await _table("user_budgets")
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            select(budgets).where(budgets.c.user_id == uid).order_by(budgets.c.category),
        )
        rows = result.mappings().all()
    return [_serialize_budget(r) for r in rows]


async def create_budget(uid: str, body: BudgetCreate, user: dict) -> dict[str, Any]:
    budgets = await _table("user_budgets")
    engine = get_engine()
    async with engine.begin() as conn:
        await enforce_count_limit(
            conn,
            user,
            feature_key="max_budgets",
            count_sql="SELECT COUNT(*) FROM user_budgets WHERE user_id = :uid",
            params={"uid": uid},
            label="Budgets",
        )
        result = await conn.execute(
            insert(budgets)
            .values(
                user_id=uid,
                category=body.category.strip(),
                spent=body.spent,
                limit_amount=body.limit_amount,
                period=body.period,
                tip=body.tip,
            )
            .returning(budgets),
        )
        row = result.mappings().first()
    return _serialize_budget(row)


async def update_budget(uid: str, budget_id: int, body: BudgetUpdate) -> dict[str, Any]:
    values = body.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(400, "No fields to update")
    budgets = await _table("user_budgets")
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            update(budgets)
            .where(budgets.c.id == budget_id, budgets.c.user_id == uid)
            .values(**values)
            .returning(budgets),
        )
        row = result.mappings().first()
    if not row:
        raise HTTPException(404, "Budget not found")
    return _serialize_budget(row)


async def delete_budget(uid: str, budget_id: int) -> dict[str, int]:
    budgets = await _table("user_budgets")
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            delete(budgets).where(budgets.c.id == budget_id, budgets.c.user_id == uid).returning(budgets.c.id),
        )
        row = result.first()
    if not row:
        raise HTTPException(404, "Budget not found")
    return {"deleted": budget_id}


async def list_bills(uid: str) -> list[dict[str, Any]]:
    bills = await _table("user_bills")
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            select(bills)
            .where(bills.c.user_id == uid)
            .order_by(bills.c.due_date.asc().nulls_last(), bills.c.created_at.desc()),
        )
        rows = result.mappings().all()
    return [_serialize_bill(r) for r in rows]


async def create_bill(uid: str, body: BillCreate, user: dict) -> dict[str, Any]:
    bills = await _table("user_bills")
    engine = get_engine()
    async with engine.begin() as conn:
        await enforce_count_limit(
            conn,
            user,
            feature_key="max_bills",
            count_sql="SELECT COUNT(*) FROM user_bills WHERE user_id = :uid",
            params={"uid": uid},
            label="Bills",
        )
        result = await conn.execute(
            insert(bills)
            .values(
                user_id=uid,
                name=body.name.strip(),
                amount=body.amount,
                due_date=_as_date(body.due_date),
                status=body.status,
                recurring=body.recurring,
            )
            .returning(bills),
        )
        row = result.mappings().first()
    return _serialize_bill(row)


async def update_bill(uid: str, bill_id: int, body: BillUpdate) -> dict[str, Any]:
    values = body.model_dump(exclude_unset=True)
    if "due_date" in values:
        values["due_date"] = _as_date(values["due_date"])
    if not values:
        raise HTTPException(400, "No fields to update")
    bills = await _table("user_bills")
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            update(bills)
            .where(bills.c.id == bill_id, bills.c.user_id == uid)
            .values(**values)
            .returning(bills),
        )
        row = result.mappings().first()
    if not row:
        raise HTTPException(404, "Bill not found")
    return _serialize_bill(row)


async def mark_bill_paid(uid: str, bill_id: int) -> dict[str, Any]:
    bills = await _table("user_bills")
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            update(bills)
            .where(bills.c.id == bill_id, bills.c.user_id == uid)
            .values(status="PAID", paid_at=text("now()"))
            .returning(bills),
        )
        row = result.mappings().first()
    if not row:
        raise HTTPException(404, "Bill not found")
    return _serialize_bill(row)


async def delete_bill(uid: str, bill_id: int) -> dict[str, int]:
    bills = await _table("user_bills")
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            delete(bills).where(bills.c.id == bill_id, bills.c.user_id == uid).returning(bills.c.id),
        )
        row = result.first()
    if not row:
        raise HTTPException(404, "Bill not found")
    return {"deleted": bill_id}


async def get_settings(uid: str) -> dict[str, Any]:
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT monthly_income, currency, language, plan FROM user_settings WHERE user_id = :uid"),
            {"uid": uid},
        )
        row = result.mappings().first()
    if not row:
        return {"monthly_income": 0, "currency": "PKR", "language": "en", "plan": "Free"}
    return {"monthly_income": float(row["monthly_income"]), "currency": row["currency"], "language": row["language"], "plan": row["plan"]}


async def update_settings(uid: str, body: SettingsUpdate) -> dict[str, Any]:
    sets = []
    params: dict[str, Any] = {"uid": uid, "income": None, "cur": None, "lang": None, "plan": None}
    if body.monthly_income is not None:
        sets.append("monthly_income = :income")
        params["income"] = body.monthly_income
    if body.currency is not None:
        sets.append("currency = :cur")
        params["cur"] = body.currency
    if body.language is not None:
        sets.append("language = :lang")
        params["lang"] = body.language
    if sets:
        sets.append("updated_at = now()")
        update_clause = ", ".join(sets)
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"INSERT INTO user_settings (user_id, monthly_income, currency, language, plan) "
                    f"VALUES (:uid, COALESCE(:income, 0), COALESCE(:cur, 'PKR'), COALESCE(:lang, 'en'), COALESCE(:plan, 'Free')) "
                    f"ON CONFLICT (user_id) DO UPDATE SET {update_clause}"
                ),
                params,
            )
    return {"ok": True}


async def summary(uid: str, month: str | None = None) -> FinanceSummaryResponse:
    if month is None:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
    year_s, m_s = month.split("-")
    year_i, m_i = int(year_s), int(m_s)
    last_month_date = datetime(year_i, m_i, 1) - timedelta(days=1)
    last_month = f"{last_month_date.year:04d}-{last_month_date.month:02d}"
    engine = get_engine()
    async with engine.connect() as conn:
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
        rows = {r["transaction_type"].lower(): float(r["total"]) for r in result.mappings().all()}
        last_result = await conn.execute(
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
            {"uid": uid, "month": last_month},
        )
        last_rows = {r["transaction_type"].lower(): float(r["total"]) for r in last_result.mappings().all()}
    income = rows.get("income", 0.0)
    expenses = rows.get("expense", 0.0)
    savings = income - expenses
    savings_rate = round((savings / income) * 100, 1) if income > 0 else 0.0
    last_income = last_rows.get("income", 0.0)
    last_expense = last_rows.get("expense", 0.0)
    return FinanceSummaryResponse(
        month=month,
        income=income,
        expenses=expenses,
        savings=savings,
        savings_rate=savings_rate,
        last_month_income=last_income,
        last_month_expense=last_expense,
        last_month_savings=last_income - last_expense,
    )


async def income_expense_series(uid: str, months: int = 6, user: dict | None = None) -> IncomeExpenseResponse:
    max_days = limit_for(user or {"features": {}}, "max_finance_history_days")
    max_months = max(1, min(1200, (max_days + 29) // 30))
    months = max(1, min(months, max_months))
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT
                    TO_CHAR(DATE_TRUNC('month', transaction_date), 'YYYY-MM') AS month,
                    transaction_type,
                    COALESCE(SUM(amount), 0)::numeric AS total
                FROM user_transactions
                WHERE user_id = :uid
                  AND transaction_date >= DATE_TRUNC('month', CURRENT_DATE) - (:months - 1) * INTERVAL '1 month'
                GROUP BY 1, transaction_type
                ORDER BY 1 ASC
                """
            ),
            {"uid": uid, "months": months},
        )
        rows = result.mappings().all()
    by_month: dict[str, dict[str, float]] = {}
    for r in rows:
        m = r["month"]
        by_month.setdefault(m, {"income": 0.0, "expense": 0.0})
        txn_type = r["transaction_type"].lower() if r["transaction_type"] else r["transaction_type"]
        by_month[m][txn_type] = float(r["total"])
    series = [
        IncomeExpensePoint(month=m, income=v.get("income", 0.0), expense=v.get("expense", 0.0))
        for m, v in by_month.items()
    ]
    return IncomeExpenseResponse(months=months, series=series)


async def spending_by_category(uid: str, days: int = 30, user: dict | None = None) -> SpendingByCategoryResponse:
    days = max(1, min(days, limit_for(user or {"features": {}}, "max_finance_history_days")))
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT category, COALESCE(SUM(amount), 0)::numeric AS amount
                FROM user_transactions
                WHERE user_id = :uid
                  AND transaction_type = 'expense'
                  AND transaction_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
                GROUP BY category
                ORDER BY amount DESC
                """
            ),
            {"uid": uid, "days": days},
        )
        rows = result.mappings().all()
    total = sum(float(r["amount"]) for r in rows)
    categories = [
        SpendingCategory(
            category=r["category"],
            amount=float(r["amount"]),
            pct=round((float(r["amount"]) / total) * 100, 1) if total > 0 else 0.0,
        )
        for r in rows
    ]
    return SpendingByCategoryResponse(days=days, total=total, categories=categories)
