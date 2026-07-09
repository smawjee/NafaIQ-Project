"""Finance service: aggregation for income, expenses, savings, budgets, bills, goals."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from app.db.sqlalchemy import get_session_factory
from app.services import calculations as calc

log = logging.getLogger(__name__)


async def summary(user_id: str, month: str | None = None) -> dict[str, Any]:
    if month is None:
        month = calc.month_string()
    last_month = calc.previous_month_string(month)
    factory = get_session_factory()
    async with factory() as session:
        cur = await session.execute(
            text(
                "SELECT transaction_type, COALESCE(SUM(amount), 0)::numeric AS total "
                "FROM user_transactions "
                "WHERE user_id = :uid "
                "AND DATE_TRUNC('month', transaction_date) = "
                "    DATE_TRUNC('month', TO_DATE(:month, 'YYYY-MM')) "
                "GROUP BY transaction_type"
            ),
            {"uid": user_id, "month": month},
        )
        cur_rows = {r["transaction_type"].lower(): float(r["total"]) for r in cur}
        prev = await session.execute(
            text(
                "SELECT transaction_type, COALESCE(SUM(amount), 0)::numeric AS total "
                "FROM user_transactions "
                "WHERE user_id = :uid "
                "AND DATE_TRUNC('month', transaction_date) = "
                "    DATE_TRUNC('month', TO_DATE(:month, 'YYYY-MM')) "
                "GROUP BY transaction_type"
            ),
            {"uid": user_id, "month": last_month},
        )
        prev_rows = {r["transaction_type"].lower(): float(r["total"]) for r in prev}
    income = cur_rows.get("income", 0.0)
    expenses = cur_rows.get("expense", 0.0)
    savings = round(income - expenses, 2)
    rate = calc.savings_rate(income, expenses)
    last_income = prev_rows.get("income", 0.0)
    last_expense = prev_rows.get("expense", 0.0)
    return {
        "month": month,
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "savings": savings,
        "savings_rate": rate,
        "last_month_income": round(last_income, 2),
        "last_month_expense": round(last_expense, 2),
        "last_month_savings": round(last_income - last_expense, 2),
        "income_change": calc.compare_to_last_month(income, last_income),
        "expense_change": calc.compare_to_last_month(expenses, last_expense),
    }


async def income_expense_series(
    user_id: str, months: int = 6
) -> list[dict[str, Any]]:
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(
            text(
                "SELECT TO_CHAR(DATE_TRUNC('month', transaction_date), 'YYYY-MM') AS month, "
                "       transaction_type, COALESCE(SUM(amount), 0)::numeric AS total "
                "FROM user_transactions "
                "WHERE user_id = :uid "
                "AND transaction_date >= "
                "    DATE_TRUNC('month', CURRENT_DATE) - (:months - 1) * INTERVAL '1 month' "
                "GROUP BY 1, transaction_type ORDER BY 1 ASC"
            ),
            {"uid": user_id, "months": int(months)},
        )
    by_month: dict[str, dict[str, float]] = {}
    for r in rows.mappings().all():
        m = r["month"]
        by_month.setdefault(m, {"income": 0.0, "expense": 0.0})
        by_month[m][r["transaction_type"].lower()] = float(r["total"])
    return [
        {"month": m, "income": round(v["income"], 2), "expense": round(v["expense"], 2)}
        for m, v in by_month.items()
    ]


async def spending_by_category(user_id: str, days: int = 30) -> dict[str, Any]:
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(
            text(
                "SELECT category, COALESCE(SUM(amount), 0)::numeric AS amount "
                "FROM user_transactions "
                "WHERE user_id = :uid AND transaction_type = 'expense' "
                "AND transaction_date >= CURRENT_DATE - (:days * INTERVAL '1 day') "
                "GROUP BY category ORDER BY amount DESC"
            ),
            {"uid": user_id, "days": int(days)},
        )
        items = [
            {"category": r["category"], "amount": float(r["amount"])}
            for r in rows.mappings().all()
        ]
    total = round(sum(i["amount"] for i in items), 2)
    for i in items:
        i["pct"] = round((i["amount"] / total) * 100, 2) if total > 0 else 0.0
    return {"days": int(days), "total": total, "categories": items}


async def list_budgets(user_id: str) -> list[dict[str, Any]]:
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(
            text(
                "SELECT id, user_id, category, spent, limit_amount, period, tip "
                "FROM user_budgets WHERE user_id = :uid ORDER BY category"
            ),
            {"uid": user_id},
        )
        out: list[dict[str, Any]] = []
        for r in rows.mappings().all():
            limit_amt = float(r["limit_amount"])
            spent = float(r["spent"])
            out.append(
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "category": r["category"],
                    "spent": spent,
                    "limit_amount": limit_amt,
                    "period": r["period"],
                    "tip": r["tip"],
                    "usage_pct": calc.budget_usage(spent, limit_amt),
                }
            )
    return out


async def list_bills(user_id: str) -> list[dict[str, Any]]:
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(
            text(
                "SELECT id, user_id, name, amount, currency, due_date, status, "
                "recurring, paid_at "
                "FROM user_bills WHERE user_id = :uid "
                "ORDER BY due_date ASC NULLS LAST, created_at DESC"
            ),
            {"uid": user_id},
        )
        out: list[dict[str, Any]] = []
        for r in rows.mappings().all():
            due = r["due_date"]
            out.append(
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "name": r["name"],
                    "amount": float(r["amount"]),
                    "currency": r["currency"],
                    "due_date": str(due) if due is not None else None,
                    "status": r["status"],
                    "recurring": bool(r["recurring"]),
                    "paid_at": (
                        str(r["paid_at"]) if r["paid_at"] is not None else None
                    ),
                    "due_in_days": (
                        calc.bill_due_in_days(due) if due is not None else None
                    ),
                }
            )
    return out


async def list_goals(user_id: str) -> list[dict[str, Any]]:
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(
            text(
                "SELECT id, user_id, emoji, name, target, saved, color, ai_tip, "
                "target_date "
                "FROM user_goals WHERE user_id = :uid ORDER BY created_at DESC"
            ),
            {"uid": user_id},
        )
        out: list[dict[str, Any]] = []
        for r in rows.mappings().all():
            target = float(r["target"])
            saved = float(r["saved"])
            out.append(
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "emoji": r["emoji"],
                    "name": r["name"],
                    "target": target,
                    "saved": saved,
                    "color": r["color"],
                    "ai_tip": r["ai_tip"],
                    "target_date": (
                        str(r["target_date"]) if r["target_date"] is not None else None
                    ),
                    "progress_pct": calc.goal_progress(saved, target),
                }
            )
    return out


async def get_settings(user_id: str) -> dict[str, Any]:
    factory = get_session_factory()
    async with factory() as session:
        row = await session.execute(
            text(
                "SELECT monthly_income, currency, language, plan "
                "FROM user_settings WHERE user_id = :uid"
            ),
            {"uid": user_id},
        )
        r = row.mappings().first()
    if not r:
        return {
            "monthly_income": 0,
            "currency": "PKR",
            "language": "en",
            "plan": "Free",
        }
    return {
        "monthly_income": float(r["monthly_income"]),
        "currency": r["currency"],
        "language": r["language"],
        "plan": r["plan"],
    }
