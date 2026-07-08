from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import require_user
from app.db.sqlalchemy import get_engine

router = APIRouter(tags=["finance"])


class TransactionCreate(BaseModel):
    merchant: str
    amount: float
    transaction_type: str
    category: str
    transaction_date: str | None = None
    source: str = "manual"
    note: str | None = None


class GoalCreate(BaseModel):
    emoji: str = "🎯"
    name: str
    target: float
    saved: float = 0
    color: str = "bull"
    ai_tip: str | None = None
    target_date: str | None = None


class BudgetCreate(BaseModel):
    category: str
    spent: float = 0
    limit_amount: float = 0
    period: str = "monthly"
    tip: str | None = None


class BudgetUpdate(BaseModel):
    spent: float | None = None
    limit_amount: float | None = None
    tip: str | None = None


class BillCreate(BaseModel):
    name: str
    amount: float
    due_date: str | None = None
    status: str = "UPCOMING"
    recurring: bool = False


class SettingsUpdate(BaseModel):
    monthly_income: float | None = None
    currency: str | None = None
    language: str | None = None
    plan: str | None = None


# ---- transactions ----

@router.get("/finance/transactions")
async def list_transactions(user: Annotated[dict, Depends(require_user)], limit: int = 100):
    uid = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT id, merchant, amount, currency, transaction_type, category,
                       transaction_date, source, note, created_at
                FROM user_transactions
                WHERE user_id = :uid
                ORDER BY transaction_date DESC
                LIMIT :lim
            """),
            {"uid": uid, "lim": limit},
        )
        rows = result.mappings().all()
    return [
        {
            "id": r["id"], "merchant": r["merchant"], "amount": float(r["amount"]),
            "currency": r["currency"], "transaction_type": r["transaction_type"],
            "category": r["category"], "transaction_date": str(r["transaction_date"]),
            "source": r["source"], "note": r["note"], "created_at": str(r["created_at"]),
        }
        for r in rows
    ]


@router.post("/finance/transactions")
async def create_transaction(body: TransactionCreate, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                INSERT INTO user_transactions (user_id, merchant, amount, transaction_type, category, transaction_date, source, note)
                VALUES (:uid, :merchant, :amount, :tt, :cat, COALESCE(:tdate, now()), :source, :note)
                RETURNING id, merchant, amount, transaction_type, category, transaction_date, created_at
            """),
            {"uid": uid, "merchant": body.merchant, "amount": body.amount,
             "tt": body.transaction_type, "cat": body.category,
             "tdate": body.transaction_date, "source": body.source, "note": body.note},
        )
        row = result.mappings().first()
    return {"id": row["id"], "merchant": row["merchant"], "amount": float(row["amount"]),
            "transaction_type": row["transaction_type"], "category": row["category"],
            "transaction_date": str(row["transaction_date"]), "created_at": str(row["created_at"])}


@router.delete("/finance/transactions/{txn_id}")
async def delete_transaction(txn_id: int, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("DELETE FROM user_transactions WHERE id = :tid AND user_id = :uid RETURNING id"),
            {"tid": txn_id, "uid": uid},
        )
        row = result.first()
    if not row:
        raise HTTPException(404, "Transaction not found")
    return {"deleted": txn_id}


# ---- goals ----

@router.get("/finance/goals")
async def list_goals(user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT id, emoji, name, target, saved, color, ai_tip, target_date, created_at FROM user_goals WHERE user_id = :uid ORDER BY created_at DESC"),
            {"uid": uid},
        )
        rows = result.mappings().all()
    return [
        {"id": r["id"], "emoji": r["emoji"], "name": r["name"], "target": float(r["target"]),
         "saved": float(r["saved"]), "color": r["color"], "ai_tip": r["ai_tip"],
         "target_date": str(r["target_date"]) if r["target_date"] else None, "created_at": str(r["created_at"])}
        for r in rows
    ]


@router.post("/finance/goals")
async def create_goal(body: GoalCreate, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                INSERT INTO user_goals (user_id, emoji, name, target, saved, color, ai_tip, target_date)
                VALUES (:uid, :emoji, :name, :target, :saved, :color, :tip, :tdate)
                RETURNING id, name, target, saved
            """),
            {"uid": uid, "emoji": body.emoji, "name": body.name, "target": body.target,
             "saved": body.saved, "color": body.color, "tip": body.ai_tip,
             "tdate": body.target_date},
        )
        row = result.mappings().first()
    return {"id": row["id"], "name": row["name"], "target": float(row["target"]), "saved": float(row["saved"])}


@router.patch("/finance/goals/{goal_id}/contribute")
async def contribute_goal(goal_id: int, body: dict, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    amount = float(body.get("amount", 0))
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("UPDATE user_goals SET saved = LEAST(saved + :amt, target) WHERE id = :gid AND user_id = :uid RETURNING id, saved, target"),
            {"gid": goal_id, "uid": uid, "amt": amount},
        )
        row = result.mappings().first()
    if not row:
        raise HTTPException(404, "Goal not found")
    return {"id": row["id"], "saved": float(row["saved"]), "target": float(row["target"])}


@router.delete("/finance/goals/{goal_id}")
async def delete_goal(goal_id: int, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("DELETE FROM user_goals WHERE id = :gid AND user_id = :uid RETURNING id"),
            {"gid": goal_id, "uid": uid},
        )
        row = result.first()
    if not row:
        raise HTTPException(404, "Goal not found")
    return {"deleted": goal_id}


# ---- budgets ----

@router.get("/finance/budgets")
async def list_budgets(user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT id, category, spent, limit_amount, period, tip, created_at FROM user_budgets WHERE user_id = :uid ORDER BY category"),
            {"uid": uid},
        )
        rows = result.mappings().all()
    return [
        {"id": r["id"], "category": r["category"], "spent": float(r["spent"]),
         "limit_amount": float(r["limit_amount"]), "period": r["period"], "tip": r["tip"],
         "created_at": str(r["created_at"])}
        for r in rows
    ]


@router.post("/finance/budgets")
async def create_budget(body: BudgetCreate, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("INSERT INTO user_budgets (user_id, category, spent, limit_amount, period, tip) VALUES (:uid, :cat, :spent, :limit, :period, :tip) RETURNING id, category, limit_amount"),
            {"uid": uid, "cat": body.category, "spent": body.spent, "limit": body.limit_amount, "period": body.period, "tip": body.tip},
        )
        row = result.mappings().first()
    return {"id": row["id"], "category": row["category"], "limit_amount": float(row["limit_amount"])}


@router.patch("/finance/budgets/{budget_id}")
async def update_budget(budget_id: int, body: BudgetUpdate, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    sets = []
    params: dict[str, Any] = {"bid": budget_id, "uid": uid}
    if body.spent is not None:
        sets.append("spent = :spent"); params["spent"] = body.spent
    if body.limit_amount is not None:
        sets.append("limit_amount = :limit"); params["limit"] = body.limit_amount
    if body.tip is not None:
        sets.append("tip = :tip"); params["tip"] = body.tip
    if not sets:
        raise HTTPException(400, "No fields to update")
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text(f"UPDATE user_budgets SET {', '.join(sets)} WHERE id = :bid AND user_id = :uid RETURNING id, category, spent, limit_amount"),
            params,
        )
        row = result.mappings().first()
    if not row:
        raise HTTPException(404, "Budget not found")
    return {"id": row["id"], "category": row["category"], "spent": float(row["spent"]), "limit_amount": float(row["limit_amount"])}


@router.delete("/finance/budgets/{budget_id}")
async def delete_budget(budget_id: int, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("DELETE FROM user_budgets WHERE id = :bid AND user_id = :uid RETURNING id"),
            {"bid": budget_id, "uid": uid},
        )
        row = result.first()
    if not row:
        raise HTTPException(404, "Budget not found")
    return {"deleted": budget_id}


# ---- bills ----

@router.get("/finance/bills")
async def list_bills(user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT id, name, amount, currency, due_date, status, recurring, paid_at, created_at FROM user_bills WHERE user_id = :uid ORDER BY due_date ASC NULLS LAST, created_at DESC"),
            {"uid": uid},
        )
        rows = result.mappings().all()
    return [
        {"id": r["id"], "name": r["name"], "amount": float(r["amount"]), "currency": r["currency"],
         "due_date": str(r["due_date"]) if r["due_date"] else None, "status": r["status"],
         "recurring": r["recurring"], "paid_at": str(r["paid_at"]) if r["paid_at"] else None,
         "created_at": str(r["created_at"])}
        for r in rows
    ]


@router.post("/finance/bills")
async def create_bill(body: BillCreate, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("INSERT INTO user_bills (user_id, name, amount, due_date, status, recurring) VALUES (:uid, :name, :amt, :due, :status, :rec) RETURNING id, name, amount, status"),
            {"uid": uid, "name": body.name, "amt": body.amount, "due": body.due_date, "status": body.status, "rec": body.recurring},
        )
        row = result.mappings().first()
    return {"id": row["id"], "name": row["name"], "amount": float(row["amount"]), "status": row["status"]}


@router.patch("/finance/bills/{bill_id}/paid")
async def mark_bill_paid(bill_id: int, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("UPDATE user_bills SET status = 'PAID', paid_at = now() WHERE id = :bid AND user_id = :uid RETURNING id, name, amount, status"),
            {"bid": bill_id, "uid": uid},
        )
        row = result.mappings().first()
    if not row:
        raise HTTPException(404, "Bill not found")
    return {"id": row["id"], "name": row["name"], "amount": float(row["amount"]), "status": row["status"]}


@router.delete("/finance/bills/{bill_id}")
async def delete_bill(bill_id: int, user: Annotated[dict, Depends(require_user)]):
    uid = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("DELETE FROM user_bills WHERE id = :bid AND user_id = :uid RETURNING id"),
            {"bid": bill_id, "uid": uid},
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
    params: dict[str, Any] = {"uid": uid}
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
