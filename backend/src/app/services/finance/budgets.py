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
    """Create a budget. `spent` is SERVER-OWNED and derived from transactions.

    `BudgetCreate.spent` is still accepted so existing clients keep working, but
    it is deliberately ignored: it used to be stored verbatim, which let any
    client post a fictional spend figure that the alert engine then trusted
    (audit 2026-07-22 §2.2).
    """
    async with begin() as conn:
        current = await repo.count_budgets(conn, uid)
        check_count_limit(user, feature_key="max_budgets", current=current, label="Budgets")
        row = await repo.insert_budget(
            conn,
            {
                "user_id": uid,
                "category": canonical_category(body.category),
                "spent": 0,  # placeholder; recomputed from transactions below
                "limit_amount": body.limit_amount,
                "period": body.period,
                "tip": body.tip,
            },
        )
        await repo.recompute_budget_spent(conn, uid)
        fresh = await repo.get_budget(conn, uid, row["id"])
    return fresh or row


async def update_budget(uid: str, budget_id: int, body: BudgetUpdate) -> dict[str, Any]:
    """Update a budget. `spent` is server-owned — see create_budget."""
    values = body.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(400, "No fields to update")
    # Never let a client write `spent`; it is derived from transactions.
    values.pop("spent", None)
    if "category" in values:
        values["category"] = canonical_category(values["category"])
    async with begin() as conn:
        if values:
            row = await repo.update_budget(conn, uid, budget_id, values)
        else:
            # A spent-only PATCH is now a no-op edit; still return the budget so
            # the caller sees the authoritative figure rather than a 400.
            row = await repo.get_budget(conn, uid, budget_id)
        if not row:
            raise HTTPException(404, "Budget not found")
        # The period or category may have changed, which changes the window.
        await repo.recompute_budget_spent(conn, uid)
        fresh = await repo.get_budget(conn, uid, budget_id)
    return fresh or row


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
