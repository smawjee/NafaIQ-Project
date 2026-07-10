"""Portfolio & holding CRUD. Business logic over portfolio."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from app.repositories import portfolio as repo
from app.repositories.base import begin, connect
from app.schemas.portfolio import HoldingCreate, HoldingUpdate
from app.services.permissions import check_count_limit
from app.services.symbols import require_known_symbol


async def list_holdings(portfolio_id: int) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_holdings(conn, portfolio_id)


async def list_portfolios(user_id: str) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_portfolios(conn, user_id)


async def create_portfolio(user: dict, name: str) -> dict[str, Any]:
    user_id = user["user_id"]
    async with begin() as conn:
        current = await repo.count_user_portfolios(conn, user_id)
        check_count_limit(user, feature_key="max_portfolios", current=current, label="Portfolios")
        return await repo.insert_portfolio(conn, user_id, name)


async def list_holdings_owned(user_id: str, portfolio_id: int) -> list[dict[str, Any]]:
    async with connect() as conn:
        if not await repo.is_portfolio_owned(conn, user_id, portfolio_id):
            raise HTTPException(404, "Portfolio not found")
        return await repo.list_holdings(conn, portfolio_id)


async def add_holding(user: dict, portfolio_id: int, body: HoldingCreate) -> dict[str, Any]:
    user_id = user["user_id"]
    async with begin() as conn:
        if not await repo.is_portfolio_owned(conn, user_id, portfolio_id):
            raise HTTPException(404, "Portfolio not found")
        await require_known_symbol(conn, body.symbol)
        current = await repo.count_holdings(conn, portfolio_id, body.symbol)
        check_count_limit(
            user, feature_key="max_holdings_per_portfolio", current=current, label="Holdings"
        )
        return await repo.upsert_holding_add(
            conn, portfolio_id, body.symbol, body.shares, body.avg_cost, body.purchased_at
        )


async def update_holding(
    user_id: str, portfolio_id: int, holding_id: int, body: HoldingUpdate
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if body.shares is not None:
        fields["shares"] = body.shares
    if body.avg_cost is not None:
        fields["avg_cost"] = body.avg_cost
    if body.purchased_at is not None:
        fields["purchased_at"] = body.purchased_at
    if not fields:
        raise HTTPException(400, "No fields to update")

    async with begin() as conn:
        if not await repo.is_holding_owned(conn, user_id, portfolio_id, holding_id):
            raise HTTPException(404, "Holding not found")
        return await repo.update_holding_fields(conn, holding_id, fields)


async def delete_holding(user_id: str, portfolio_id: int, holding_id: int) -> dict[str, Any]:
    async with begin() as conn:
        deleted = await repo.delete_holding(conn, user_id, portfolio_id, holding_id)
    if deleted is None:
        raise HTTPException(404, "Holding not found")
    return {"deleted": holding_id}


async def resolve_owned_portfolio(user_id: str, portfolio_id: Optional[int]) -> Optional[int]:
    """None -> user's first portfolio (or None); an explicit id must be owned."""
    async with connect() as conn:
        if portfolio_id is None:
            return await repo.first_portfolio_id(conn, user_id)
        if not await repo.is_portfolio_owned(conn, user_id, portfolio_id):
            raise HTTPException(404, "Portfolio not found")
        return portfolio_id
