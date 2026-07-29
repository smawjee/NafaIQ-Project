"""Periodic sync endpoints for finance data (thin HTTP layer).

Recomputes derived values (e.g. budget.spent from actual transactions) so
alerts and UI reflect real spending.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_user
from app.services import finance as finance_service

router = APIRouter(tags=["finance-sync"])


@router.post("/finance/sync-budgets")
async def sync_budget_spent(user: Annotated[dict, Depends(require_user)]):
    """Recalculate user_budgets.spent from actual user_transactions."""
    return await finance_service.sync_budget_spent(user["user_id"])
