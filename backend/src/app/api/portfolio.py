"""Portfolio routes: thin HTTP layer over services.portfolio."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_user
from app.schemas.portfolio import (
    HoldingCreate,
    HoldingUpdate,
    NetworthHolding,
    NetworthResponse,
    PortfolioCreate,
    PortfolioHistoryPoint,
    PortfolioHistoryResponse,
)
from app.services import portfolio as portfolio_service

router = APIRouter(tags=["portfolio"])


@router.get("/portfolio/list")
async def list_portfolios(user: Annotated[dict, Depends(require_user)]):
    return await portfolio_service.list_portfolios(user["user_id"])


@router.post("/portfolio/create")
async def create_portfolio(
    body: PortfolioCreate,
    user: Annotated[dict, Depends(require_user)],
):
    return await portfolio_service.create_portfolio(user, body.name)


@router.get("/portfolio/{portfolio_id}/holdings")
async def list_holdings(
    portfolio_id: int,
    user: Annotated[dict, Depends(require_user)],
):
    return await portfolio_service.list_holdings_owned(user["user_id"], portfolio_id)


@router.post("/portfolio/{portfolio_id}/holdings")
async def add_holding(
    portfolio_id: int,
    body: HoldingCreate,
    user: Annotated[dict, Depends(require_user)],
):
    return await portfolio_service.add_holding(user, portfolio_id, body)


@router.patch("/portfolio/{portfolio_id}/holdings/{holding_id}")
async def update_holding(
    portfolio_id: int,
    holding_id: int,
    body: HoldingUpdate,
    user: Annotated[dict, Depends(require_user)],
):
    return await portfolio_service.update_holding(
        user["user_id"], portfolio_id, holding_id, body
    )


@router.delete("/portfolio/{portfolio_id}/holdings/{holding_id}")
async def delete_holding(
    portfolio_id: int,
    holding_id: int,
    user: Annotated[dict, Depends(require_user)],
):
    return await portfolio_service.delete_holding(
        user["user_id"], portfolio_id, holding_id
    )


@router.get("/portfolio/{portfolio_id}/value")
async def portfolio_value(
    portfolio_id: int,
    user: Annotated[dict, Depends(require_user)],
):
    """Live P&L: join holdings with current market prices."""
    return await portfolio_service.portfolio_value(user["user_id"], portfolio_id)


@router.get("/portfolio/networth")
async def portfolio_networth(
    user: Annotated[dict, Depends(require_user)],
):
    """Sum totals across all user portfolios with buy-date-aware today P&L."""
    data = await portfolio_service.networth(user["user_id"])
    return NetworthResponse(
        total_market_value=data["total_market_value"],
        total_cost_basis=data["total_cost_basis"],
        total_unrealized_pnl=data["total_unrealized_pnl"],
        total_unrealized_pnl_pct=data["total_unrealized_pnl_pct"],
        today_pnl=data["today_pnl"],
        today_pnl_pct=data["today_pnl_pct"],
        portfolio_count=data["portfolio_count"],
        holding_count=data["holding_count"],
        by_holding=[NetworthHolding(**h) for h in data["by_holding"]],
    )


@router.get("/portfolio/history")
async def portfolio_history(
    user: Annotated[dict, Depends(require_user)],
    days: int = 180,
):
    """Historical portfolio value based on current holdings and PSX closes."""
    data = await portfolio_service.portfolio_history(user["user_id"], days)
    return PortfolioHistoryResponse(
        days=data["days"],
        points=[PortfolioHistoryPoint(**p) for p in data["points"]],
    )


@router.get("/watchlist")
async def get_watchlist(
    user: Annotated[dict, Depends(require_user)],
):
    """Return user's watchlist with real-time price and company name enrichment."""
    return await portfolio_service.enriched_watchlist(user["user_id"])
