"""Finance budgets: business logic over finance (incl. spent recompute)."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.repositories import finance as repo
from app.repositories.base import begin, connect
from app.schemas.finance import BudgetCreate, BudgetUpdate
from app.services.finance.categories import canonical_category
from app.services.permissions import check_count_limit


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
                "category": canonical_category(body.category),
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
    if "category" in values:
        values["category"] = canonical_category(values["category"])
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


async def sync_budget_spent(user_id: str) -> dict[str, Any]:
    """Recalculate user_budgets.spent from actual user_transactions (current
    month, category-matched, case-insensitive). Keeps budget alerts/UI aligned."""
    async with begin() as conn:
        budgets = await repo.recompute_budget_spent(conn, user_id)
    return {"updated": len(budgets), "budgets": budgets}
