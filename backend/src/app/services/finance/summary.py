"""Finance overview: settings, monthly summary, income/expense series, and
spending-by-category. Business logic over finance."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.repositories import finance as repo
from app.repositories.base import begin, connect
from app.schemas.finance import (
    FinanceSummaryResponse,
    IncomeExpensePoint,
    IncomeExpenseResponse,
    SettingsUpdate,
    SpendingByCategoryResponse,
    SpendingCategory,
)
from app.services.permissions import limit_for


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


def _fixed_income(settings_row) -> float:
    """The user's recurring monthly income (salary) from settings, as a float.

    Counted as income for EVERY month (it's a standing salary, not a one-off),
    so it lands in both the monthly summary and every point of the trend chart.
    0 when unset — so nothing changes for a user who never enters one."""
    if not settings_row:
        return 0.0
    val = (
        settings_row.get("monthly_income")
        if hasattr(settings_row, "get")
        else getattr(settings_row, "monthly_income", 0)
    )
    try:
        return max(0.0, float(val or 0.0))
    except (TypeError, ValueError):
        return 0.0


async def summary(uid: str, month: str | None = None) -> FinanceSummaryResponse:
    if month is None:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
    year_i, m_i = (int(p) for p in month.split("-"))
    last_month_date = datetime(year_i, m_i, 1) - timedelta(days=1)
    last_month = f"{last_month_date.year:04d}-{last_month_date.month:02d}"

    async with connect() as conn:
        rows = await repo.fetch_month_totals(conn, uid, month)
        last_rows = await repo.fetch_month_totals(conn, uid, last_month)
        settings_row = await repo.get_settings_row(conn, uid)

    fixed_income = _fixed_income(settings_row)
    income = rows.get("income", 0.0)  # earned this month (transactions)
    total_income = income + fixed_income
    expenses = rows.get("expense", 0.0)
    savings = total_income - expenses
    savings_rate = round((savings / total_income) * 100, 1) if total_income > 0 else 0.0
    # The fixed salary applies to last month too, so the "vs last month" deltas
    # compare like with like (a change reflects real earning/spending, not the
    # salary appearing out of nowhere).
    last_income = last_rows.get("income", 0.0) + fixed_income
    last_expense = last_rows.get("expense", 0.0)
    return FinanceSummaryResponse(
        month=month,
        income=income,
        fixed_income=fixed_income,
        total_income=total_income,
        expenses=expenses,
        savings=savings,
        savings_rate=savings_rate,
        last_month_income=last_income,
        last_month_expense=last_expense,
        last_month_savings=last_income - last_expense,
    )


async def income_expense_series(uid: str, months: int = 6, user: dict | None = None) -> IncomeExpenseResponse:
    # The monthly income/expense chart is a coarse aggregate, decoupled from the
    # per-transaction history-day quota (which still gates granular views like
    # spending-by-category). Cap at 12 months.
    months = max(1, min(months, 12))
    async with connect() as conn:
        rows = await repo.fetch_income_expense(conn, uid, months)
        settings_row = await repo.get_settings_row(conn, uid)
    fixed_income = _fixed_income(settings_row)
    by_month: dict[str, dict[str, float]] = {}
    for r in rows:
        m = r["month"]
        by_month.setdefault(m, {"income": 0.0, "expense": 0.0})
        txn_type = r["transaction_type"].lower() if r["transaction_type"] else r["transaction_type"]
        by_month[m][txn_type] = r["total"]
    # Zero-fill the month grid so the chart always shows `months` ordered bars,
    # even for months with no activity (avoids gaps / misleading captions).
    now = datetime.now(timezone.utc)
    grid: list[str] = []
    y, mo = now.year, now.month
    for _ in range(months):
        grid.append(f"{y:04d}-{mo:02d}")
        mo -= 1
        if mo == 0:
            mo = 12
            y -= 1
    grid.reverse()
    series = [
        IncomeExpensePoint(
            month=m,
            # Fixed salary is standing income, so add it to every month's bar.
            income=by_month.get(m, {}).get("income", 0.0) + fixed_income,
            expense=by_month.get(m, {}).get("expense", 0.0),
        )
        for m in grid
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
