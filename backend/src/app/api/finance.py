from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, insert, select, text, update

from app.api.deps import require_user
from app.db.orm import get_table
from app.db.sqlalchemy import ensure_reflected, get_engine

router = APIRouter(tags=["finance"])


class TransactionCreate(BaseModel):
    merchant: str = Field(..., min_length=1, max_length=120)
    amount: float = Field(..., gt=0)
    transaction_type: str = Field(..., min_length=1, max_length=20)
    category: str = Field(..., min_length=1, max_length=80)
    transaction_date: str | None = None
    source: str = "manual"
    note: str | None = None


class TransactionUpdate(BaseModel):
    merchant: str | None = Field(None, min_length=1, max_length=120)
    amount: float | None = Field(None, gt=0)
    transaction_type: str | None = Field(None, min_length=1, max_length=20)
    category: str | None = Field(None, min_length=1, max_length=80)
    transaction_date: str | None = None
    source: str | None = None
    note: str | None = None


class GoalCreate(BaseModel):
    emoji: str = "\U0001F3AF"
    name: str = Field(..., min_length=1, max_length=120)
    target: float = Field(..., gt=0)
    saved: float = Field(0, ge=0)
    color: str = "bull"
    ai_tip: str | None = None
    target_date: str | None = None


class BudgetCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=80)
    spent: float = Field(0, ge=0)
    limit_amount: float = Field(..., ge=0)
    period: str = "monthly"
    tip: str | None = None


class BudgetUpdate(BaseModel):
    spent: float | None = Field(None, ge=0)
    limit_amount: float | None = Field(None, ge=0)
    tip: str | None = None


class BillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    amount: float = Field(..., gt=0)
    due_date: str | None = None
    status: str = "UPCOMING"
    recurring: bool = False


class BillUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    amount: float | None = Field(None, gt=0)
    due_date: str | None = None
    status: str | None = None
    recurring: bool | None = None


class SettingsUpdate(BaseModel):
    monthly_income: float | None = None
    currency: str | None = None
    language: str | None = None
    plan: str | None = None


async def _table(name: str):
    await ensure_reflected()
    return get_table(name)


def _transaction_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"income", "expense"}:
        raise HTTPException(400, "transaction_type must be income or expense")
    return normalized


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
        "target_date": str(row["target_date"]) if row["target_date"] else None,
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


# ---- transactions ----

@router.get("/finance/transactions")
async def list_transactions(user: Annotated[dict, Depends(require_user)], limit: int = 100):
    uid = user["user_id"]
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


@router.post("/finance/transactions")
async def create_transaction(body: TransactionCreate, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
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
        values["transaction_date"] = body.transaction_date

    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(insert(txns).values(**values).returning(txns))
        row = result.mappings().first()
    return _serialize_transaction(row)


@router.patch("/finance/transactions/{txn_id}")
async def update_transaction(
    txn_id: int,
    body: TransactionUpdate,
    user: Annotated[dict, Depends(require_user)],
):
    uid = user["user_id"]
    values = body.model_dump(exclude_unset=True)
    if "transaction_type" in values and values["transaction_type"] is not None:
        values["transaction_type"] = _transaction_type(values["transaction_type"])
    if "amount" in values and values["amount"] is not None:
        values["amount"] = abs(values["amount"])
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


@router.delete("/finance/transactions/{txn_id}")
async def delete_transaction(txn_id: int, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
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


# ---- goals ----

@router.get("/finance/goals")
async def list_goals(user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    goals = await _table("user_goals")
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            select(goals).where(goals.c.user_id == uid).order_by(goals.c.created_at.desc()),
        )
        rows = result.mappings().all()
    return [_serialize_goal(r) for r in rows]


@router.post("/finance/goals")
async def create_goal(body: GoalCreate, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    goals = await _table("user_goals")
    engine = get_engine()
    async with engine.begin() as conn:
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
                target_date=body.target_date,
            )
            .returning(goals),
        )
        row = result.mappings().first()
    return _serialize_goal(row)


@router.patch("/finance/goals/{goal_id}/contribute")
async def contribute_goal(goal_id: int, body: dict, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    amount = float(body.get("amount", 0))
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


@router.delete("/finance/goals/{goal_id}")
async def delete_goal(goal_id: int, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
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


# ---- budgets ----

@router.get("/finance/budgets")
async def list_budgets(user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    budgets = await _table("user_budgets")
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            select(budgets).where(budgets.c.user_id == uid).order_by(budgets.c.category),
        )
        rows = result.mappings().all()
    return [_serialize_budget(r) for r in rows]


@router.post("/finance/budgets")
async def create_budget(body: BudgetCreate, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    budgets = await _table("user_budgets")
    engine = get_engine()
    async with engine.begin() as conn:
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


@router.patch("/finance/budgets/{budget_id}")
async def update_budget(budget_id: int, body: BudgetUpdate, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
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


@router.delete("/finance/budgets/{budget_id}")
async def delete_budget(budget_id: int, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
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


# ---- bills ----

@router.get("/finance/bills")
async def list_bills(user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
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


@router.post("/finance/bills")
async def create_bill(body: BillCreate, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    bills = await _table("user_bills")
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            insert(bills)
            .values(
                user_id=uid,
                name=body.name.strip(),
                amount=body.amount,
                due_date=body.due_date,
                status=body.status,
                recurring=body.recurring,
            )
            .returning(bills),
        )
        row = result.mappings().first()
    return _serialize_bill(row)


@router.patch("/finance/bills/{bill_id}")
async def update_bill(bill_id: int, body: BillUpdate, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    values = body.model_dump(exclude_unset=True)
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


@router.patch("/finance/bills/{bill_id}/paid")
async def mark_bill_paid(bill_id: int, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
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


@router.delete("/finance/bills/{bill_id}")
async def delete_bill(bill_id: int, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
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


# ---- settings ----

@router.get("/finance/settings")
async def get_settings(user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT monthly_income, currency, language, plan FROM user_settings WHERE user_id = :uid"),
            {"uid": uid},
        )
        row = result.mappings().first()
    if not row:
        return {"monthly_income": 0, "currency": "PKR", "language": "en", "plan": "Free"}
    return {"monthly_income": float(row["monthly_income"]), "currency": row["currency"],
            "language": row["language"], "plan": row["plan"]}


@router.patch("/finance/settings")
async def update_settings(body: SettingsUpdate, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    sets = []
    params: dict[str, Any] = {"uid": uid, "income": None, "cur": None, "lang": None, "plan": None}
    if body.monthly_income is not None:
        sets.append("monthly_income = :income"); params["income"] = body.monthly_income
    if body.currency is not None:
        sets.append("currency = :cur"); params["cur"] = body.currency
    if body.language is not None:
        sets.append("language = :lang"); params["lang"] = body.language
    if body.plan is not None:
        sets.append("plan = :plan"); params["plan"] = body.plan
    if sets:
        sets.append("updated_at = now()")
        update_clause = ", ".join(sets)
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text(f"INSERT INTO user_settings (user_id, monthly_income, currency, language, plan) VALUES (:uid, COALESCE(:income, 0), COALESCE(:cur, 'PKR'), COALESCE(:lang, 'en'), COALESCE(:plan, 'Free')) ON CONFLICT (user_id) DO UPDATE SET {update_clause}"),
                params,
            )
    return {"ok": True}


class FinanceSummaryResponse(BaseModel):
    month: str
    income: float
    expenses: float
    savings: float
    savings_rate: float
    last_month_income: float
    last_month_expense: float
    last_month_savings: float


@router.get("/finance/summary")
async def finance_summary(
    month: str | None = None,
    user: Annotated[dict, Depends(require_user)] = ...,
):
    """Aggregate income, expenses, and savings for a given month."""
    user_id = user["user_id"]
    if month is None:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
    year_s, m_s = month.split("-")
    year_i, m_i = int(year_s), int(m_s)

    last_month_date = (datetime(year_i, m_i, 1) - timedelta(days=1))
    last_year_i, last_m_i = last_month_date.year, last_month_date.month
    last_month = f"{last_year_i:04d}-{last_m_i:02d}"

    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT
                    transaction_type,
                    COALESCE(SUM(amount), 0)::numeric AS total
                FROM user_transactions
                WHERE user_id = :uid
                  AND DATE_TRUNC('month', transaction_date) = DATE_TRUNC('month', TO_DATE(:month, 'YYYY-MM'))
                GROUP BY transaction_type
            """),
            {"uid": user_id, "month": month},
        )
        rows_raw = {r["transaction_type"]: float(r["total"]) for r in result.mappings().all()}
        rows = {k.lower(): v for k, v in rows_raw.items()}

        last_result = await conn.execute(
            text("""
                SELECT
                    transaction_type,
                    COALESCE(SUM(amount), 0)::numeric AS total
                FROM user_transactions
                WHERE user_id = :uid
                  AND DATE_TRUNC('month', transaction_date) = DATE_TRUNC('month', TO_DATE(:month, 'YYYY-MM'))
                GROUP BY transaction_type
            """),
            {"uid": user_id, "month": last_month},
        )
        last_rows_raw = {r["transaction_type"]: float(r["total"]) for r in last_result.mappings().all()}
        last_rows = {k.lower(): v for k, v in last_rows_raw.items()}

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


class IncomeExpensePoint(BaseModel):
    month: str
    income: float
    expense: float


class IncomeExpenseResponse(BaseModel):
    months: int
    series: list[IncomeExpensePoint]


@router.get("/finance/income-expense")
async def finance_income_expense(
    months: int = 6,
    user: Annotated[dict, Depends(require_user)] = ...,
):
    """Return the last N months of income/expense series, ordered ASC by month."""
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT
                    TO_CHAR(DATE_TRUNC('month', transaction_date), 'YYYY-MM') AS month,
                    transaction_type,
                    COALESCE(SUM(amount), 0)::numeric AS total
                FROM user_transactions
                WHERE user_id = :uid
                  AND transaction_date >= DATE_TRUNC('month', CURRENT_DATE) - (:months - 1) * INTERVAL '1 month'
                GROUP BY 1, transaction_type
                ORDER BY 1 ASC
            """),
            {"uid": user_id, "months": months},
        )
        rows = result.mappings().all()

    by_month: dict[str, dict[str, float]] = {}
    for r in rows:
        m = r["month"]
        if m not in by_month:
            by_month[m] = {"income": 0.0, "expense": 0.0}
        txn_type = r["transaction_type"].lower() if r["transaction_type"] else r["transaction_type"]
        by_month[m][txn_type] = float(r["total"])

    series = [
        IncomeExpensePoint(month=m, income=v.get("income", 0.0), expense=v.get("expense", 0.0))
        for m, v in by_month.items()
    ]
    return IncomeExpenseResponse(months=months, series=series)


class SpendingCategory(BaseModel):
    category: str
    amount: float
    pct: float


class SpendingByCategoryResponse(BaseModel):
    days: int
    total: float
    categories: list[SpendingCategory]


@router.get("/finance/spending-by-category")
async def finance_spending_by_category(
    days: int = 30,
    user: Annotated[dict, Depends(require_user)] = ...,
):
    """Aggregate spending by category for the last N days, ordered by amount DESC."""
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT
                    category,
                    COALESCE(SUM(amount), 0)::numeric AS amount
                FROM user_transactions
                WHERE user_id = :uid
                  AND transaction_type = 'expense'
                  AND transaction_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
                GROUP BY category
                ORDER BY amount DESC
            """),
            {"uid": user_id, "days": days},
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
