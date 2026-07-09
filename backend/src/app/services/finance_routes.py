"""Finance service: business logic for transactions, goals, budgets, bills,
settings, summary and series. All DB access is delegated to
app.repositories.finance_repo; this module holds no SQL.

(Filename kept as finance_routes.py to avoid churn; imported as the finance
service by app.api.finance and app.api.finance_sync.)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException

from app.repositories import finance_repo as repo
from app.repositories.base import begin, connect
from app.schemas.finance import (
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
from app.services.permissions import check_count_limit, limit_for


# ---------- validation / coercion helpers (business rules) ----------


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


# ---------- transactions ----------


async def list_transactions(uid: str, limit: int = 100) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_transactions(conn, uid, limit)


async def create_transaction(uid: str, body: TransactionCreate) -> dict[str, Any]:
    values: dict[str, Any] = {
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
    async with begin() as conn:
        return await repo.insert_transaction(conn, values)


async def update_transaction(uid: str, txn_id: int, body: TransactionUpdate) -> dict[str, Any]:
    values = body.model_dump(exclude_unset=True)
    if values.get("transaction_type") is not None:
        values["transaction_type"] = _transaction_type(values["transaction_type"])
    if values.get("amount") is not None:
        values["amount"] = abs(values["amount"])
    if "transaction_date" in values:
        values["transaction_date"] = _as_timestamp(values["transaction_date"])
    if not values:
        raise HTTPException(400, "No fields to update")
    async with begin() as conn:
        row = await repo.update_transaction(conn, uid, txn_id, values)
    if not row:
        raise HTTPException(404, "Transaction not found")
    return row


async def delete_transaction(uid: str, txn_id: int) -> dict[str, int]:
    async with begin() as conn:
        deleted = await repo.delete_transaction(conn, uid, txn_id)
    if deleted is None:
        raise HTTPException(404, "Transaction not found")
    return {"deleted": txn_id}


# ---------- goals ----------


async def list_goals(uid: str) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_goals(conn, uid)


async def create_goal(uid: str, body: GoalCreate, user: dict) -> dict[str, Any]:
    async with begin() as conn:
        current = await repo.count_goals(conn, uid)
        check_count_limit(user, feature_key="max_goals", current=current, label="Savings goals")
        return await repo.insert_goal(
            conn,
            {
                "user_id": uid,
                "emoji": body.emoji,
                "name": body.name.strip(),
                "target": body.target,
                "saved": body.saved,
                "color": body.color,
                "ai_tip": body.ai_tip,
                # target_date is timestamptz in the live schema: store midnight
                # UTC of the chosen date so the calendar date never shifts.
                "target_date": _as_timestamp(body.target_date),
            },
        )


async def contribute_goal(uid: str, goal_id: int, amount: float) -> dict[str, Any]:
    if amount <= 0:
        raise HTTPException(400, "Contribution amount must be positive")
    async with begin() as conn:
        row = await repo.contribute_goal(conn, uid, goal_id, amount)
    if not row:
        raise HTTPException(404, "Goal not found")
    return row


async def delete_goal(uid: str, goal_id: int) -> dict[str, int]:
    async with begin() as conn:
        deleted = await repo.delete_goal(conn, uid, goal_id)
    if deleted is None:
        raise HTTPException(404, "Goal not found")
    return {"deleted": goal_id}


# ---------- budgets ----------


async def list_budgets(uid: str) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_budgets(conn, uid)


async def create_budget(uid: str, body: BudgetCreate, user: dict) -> dict[str, Any]:
    async with begin() as conn:
        current = await repo.count_budgets(conn, uid)
        check_count_limit(user, feature_key="max_budgets", current=current, label="Budgets")
        return await repo.insert_budget(
            conn,
            {
                "user_id": uid,
                "category": body.category.strip(),
                "spent": body.spent,
                "limit_amount": body.limit_amount,
                "period": body.period,
                "tip": body.tip,
            },
        )


async def update_budget(uid: str, budget_id: int, body: BudgetUpdate) -> dict[str, Any]:
    values = body.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(400, "No fields to update")
    async with begin() as conn:
        row = await repo.update_budget(conn, uid, budget_id, values)
    if not row:
        raise HTTPException(404, "Budget not found")
    return row


async def delete_budget(uid: str, budget_id: int) -> dict[str, int]:
    async with begin() as conn:
        deleted = await repo.delete_budget(conn, uid, budget_id)
    if deleted is None:
        raise HTTPException(404, "Budget not found")
    return {"deleted": budget_id}


# ---------- bills ----------


async def list_bills(uid: str) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_bills(conn, uid)


async def create_bill(uid: str, body: BillCreate, user: dict) -> dict[str, Any]:
    async with begin() as conn:
        current = await repo.count_bills(conn, uid)
        check_count_limit(user, feature_key="max_bills", current=current, label="Bills")
        return await repo.insert_bill(
            conn,
            {
                "user_id": uid,
                "name": body.name.strip(),
                "amount": body.amount,
                "due_date": _as_date(body.due_date),
                "status": body.status,
                "recurring": body.recurring,
            },
        )


async def update_bill(uid: str, bill_id: int, body: BillUpdate) -> dict[str, Any]:
    values = body.model_dump(exclude_unset=True)
    if "due_date" in values:
        values["due_date"] = _as_date(values["due_date"])
    if not values:
        raise HTTPException(400, "No fields to update")
    async with begin() as conn:
        row = await repo.update_bill(conn, uid, bill_id, values)
    if not row:
        raise HTTPException(404, "Bill not found")
    return row


async def mark_bill_paid(uid: str, bill_id: int) -> dict[str, Any]:
    async with begin() as conn:
        row = await repo.mark_bill_paid(conn, uid, bill_id)
    if not row:
        raise HTTPException(404, "Bill not found")
    return row


async def delete_bill(uid: str, bill_id: int) -> dict[str, int]:
    async with begin() as conn:
        deleted = await repo.delete_bill(conn, uid, bill_id)
    if deleted is None:
        raise HTTPException(404, "Bill not found")
    return {"deleted": bill_id}


# ---------- settings ----------


async def get_settings(uid: str) -> dict[str, Any]:
    async with connect() as conn:
        row = await repo.get_settings_row(conn, uid)
    if not row:
        return {"monthly_income": 0, "currency": "PKR", "language": "en", "plan": "Free"}
    return row


async def update_settings(uid: str, body: SettingsUpdate) -> dict[str, Any]:
    async with begin() as conn:
        await repo.upsert_settings(
            conn,
            uid,
            monthly_income=body.monthly_income,
            currency=body.currency,
            language=body.language,
        )
    return {"ok": True}


# ---------- summary / series ----------


async def summary(uid: str, month: str | None = None) -> FinanceSummaryResponse:
    if month is None:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
    year_i, m_i = (int(p) for p in month.split("-"))
    last_month_date = datetime(year_i, m_i, 1) - timedelta(days=1)
    last_month = f"{last_month_date.year:04d}-{last_month_date.month:02d}"

    async with connect() as conn:
        rows = await repo.fetch_month_totals(conn, uid, month)
        last_rows = await repo.fetch_month_totals(conn, uid, last_month)

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
    async with connect() as conn:
        rows = await repo.fetch_income_expense(conn, uid, months)
    by_month: dict[str, dict[str, float]] = {}
    for r in rows:
        m = r["month"]
        by_month.setdefault(m, {"income": 0.0, "expense": 0.0})
        txn_type = r["transaction_type"].lower() if r["transaction_type"] else r["transaction_type"]
        by_month[m][txn_type] = r["total"]
    series = [
        IncomeExpensePoint(month=m, income=v.get("income", 0.0), expense=v.get("expense", 0.0))
        for m, v in by_month.items()
    ]
    return IncomeExpenseResponse(months=months, series=series)


async def spending_by_category(uid: str, days: int = 30, user: dict | None = None) -> SpendingByCategoryResponse:
    days = max(1, min(days, limit_for(user or {"features": {}}, "max_finance_history_days")))
    async with connect() as conn:
        rows = await repo.fetch_spending(conn, uid, days)
    total = sum(r["amount"] for r in rows)
    categories = [
        SpendingCategory(
            category=r["category"],
            amount=r["amount"],
            pct=round((r["amount"] / total) * 100, 1) if total > 0 else 0.0,
        )
        for r in rows
    ]
    return SpendingByCategoryResponse(days=days, total=total, categories=categories)


# ---------- sync ----------


async def sync_budget_spent(user_id: str) -> dict[str, Any]:
    """Recalculate user_budgets.spent from actual user_transactions (current
    month, category-matched, case-insensitive). Keeps budget alerts/UI aligned."""
    async with begin() as conn:
        budgets = await repo.recompute_budget_spent(conn, user_id)
    return {"updated": len(budgets), "budgets": budgets}
