"""User-scoped portfolio extensions: allocation, performance, stock transactions."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_user
from app.schemas.portfolio import AllocationResponse, StockTransactionCreate
from app.services import portfolio as portfolio_service

router = APIRouter(tags=["portfolio-extended"])


@router.get("/portfolio/allocation")
async def allocation(
    user: Annotated[dict, Depends(require_user)],
    portfolio_id: Optional[int] = None,
    by: str = "stock",
):
    """Allocation by stock or sector. If portfolio_id is None, uses the user's
    first portfolio.
    """
    if by not in ("stock", "sector"):
        raise HTTPException(400, "by must be 'stock' or 'sector'")
    resolved = await portfolio_service.resolve_owned_portfolio(
        user["user_id"], portfolio_id
    )
    if resolved is None:
        return AllocationResponse(by=by, items=[]).model_dump()
    items = await portfolio_service.allocation(resolved, by=by)
    return AllocationResponse(by=by, items=items).model_dump()


@router.get("/portfolio/performance")
async def performance(
    user: Annotated[dict, Depends(require_user)],
    days: int = 180,
):
    """Historical portfolio performance + KSE-100 benchmark overlay."""
    bounded = max(7, min(int(days), 365))
    series = await portfolio_service.performance_vs_kse100(
        user["user_id"], days=bounded
    )
    return {"days": bounded, "points": series}


@router.get("/portfolio/transactions")
async def list_stock_transactions(
    user: Annotated[dict, Depends(require_user)],
    limit: int = 100,
):
    return await portfolio_service.list_stock_transactions(user["user_id"], limit)


@router.post("/portfolio/transactions")
async def create_stock_transaction(
    body: StockTransactionCreate,
    user: Annotated[dict, Depends(require_user)],
):
    """Create a stock transaction; buys/sells also upsert the holding and
    reflect the cash movement into personal finance."""
    return await portfolio_service.create_stock_transaction(user, body)
