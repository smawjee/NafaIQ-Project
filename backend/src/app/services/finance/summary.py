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


def month_income(recorded: float, fixed: float) -> float:
    """Income for one month, reconciling recorded transactions with the salary.

    The problem this solves: the standing salary from settings and the imported
    bank credits describe the SAME money whenever the salary lands as an email
    the importer picks up — but describe DIFFERENT money when it doesn't. With
    only per-month aggregates available, the amounts themselves are the evidence.

    If recorded income already meets or exceeds the salary, the salary is
    evidently inside it, so it is not added again. If recorded income falls
    short, the salary plainly did not arrive as a transaction, so it is added on
    top of whatever else was recorded.

    Both simpler rules are wrong on real data:
      - Adding unconditionally double-counted any user whose salary IS imported,
        and drew every month of the trend chart as the same salary figure.
      - Treating the salary as a pure fallback let a single incidental credit
        suppress it entirely: one user with PKR 32,887 of incidental income
        against a 215,000 salary was reported at a -22% savings rate.

    Residual limitation, accepted deliberately: a user whose salary is NOT
    imported but who records more than their salary from other sources has the
    salary omitted. That needs per-transaction evidence to detect, which this
    aggregate cannot carry.
    """
    if fixed <= 0:
        return recorded
    return recorded if recorded >= fixed else recorded + fixed


def _fixed_income(settings_row) -> float:
    """The user's recurring monthly income (salary) from settings, as a float.

    Used as the fallback in `month_income` for months with no recorded income.
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
        opening_date = (settings_row or {}).get("opening_balance_date")
        prior_months = await repo.fetch_month_nets_before(
            conn, uid, month, since=opening_date
        )

    fixed_income = _fixed_income(settings_row)
    income = rows.get("income", 0.0)  # earned this month (transactions)
    total_income = month_income(income, fixed_income)
    expenses = rows.get("expense", 0.0)
    savings = total_income - expenses
    savings_rate = round((savings / total_income) * 100, 1) if total_income > 0 else 0.0
    # Last month resolves by the same rule, so the "vs last month" deltas
    # compare like with like rather than a measured month against a salary.
    last_income = month_income(last_rows.get("income", 0.0), fixed_income)
    last_expense = last_rows.get("expense", 0.0)

    # Carried-forward balance. Every prior month's net rolls into this one, on
    # top of the opening balance the user recorded — without this the app reset
    # to zero each month and could only ever describe the current one, so money
    # left unspent in July simply vanished on 1 August.
    opening_balance = float((settings_row or {}).get("opening_balance") or 0.0)
    carried_over = opening_balance + sum(
        month_income(m["income"], fixed_income) - m["expense"] for m in prior_months
    )
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
        opening_balance=opening_balance,
        carried_over=round(carried_over, 2),
        # What the user actually has to work with this month.
        available_balance=round(carried_over + savings, 2),
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
            # Salary is a fallback, not an addend — see `month_income`. Adding
            # it to every month double-counted an imported salary credit and
            # drew six identical bars regardless of what each month did.
            income=month_income(by_month.get(m, {}).get("income", 0.0), fixed_income),
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
