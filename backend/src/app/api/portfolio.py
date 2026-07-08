from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import require_user
from app.db.sqlalchemy import get_engine

router = APIRouter(tags=["portfolio"])


class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class HoldingCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    shares: int = Field(..., ge=0)
    avg_cost: float = Field(..., ge=0)
    purchased_at: str | None = None


class HoldingUpdate(BaseModel):
    shares: int | None = Field(None, ge=0)
    avg_cost: float | None = Field(None, ge=0)
    purchased_at: str | None = None


@router.get("/portfolio/list")
async def list_portfolios(user: Annotated[dict, Depends(require_user)]):
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT id, name, created_at
                FROM psx_portfolios
                WHERE user_id = :uid
                ORDER BY created_at ASC
            """),
            {"uid": user_id},
        )
        rows = result.mappings().all()
    return [
        {"id": r["id"], "name": r["name"], "created_at": str(r["created_at"])}
        for r in rows
    ]


@router.post("/portfolio/create")
async def create_portfolio(
    body: PortfolioCreate,
    user: Annotated[dict, Depends(require_user)],
):
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                INSERT INTO psx_portfolios (user_id, name)
                VALUES (:uid, :name)
                RETURNING id, name, created_at
            """),
            {"uid": user_id, "name": body.name},
        )
        row = result.mappings().first()
    return {"id": row["id"], "name": row["name"], "created_at": str(row["created_at"])}


@router.get("/portfolio/{portfolio_id}/holdings")
async def list_holdings(
    portfolio_id: int,
    user: Annotated[dict, Depends(require_user)],
):
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        own = await conn.execute(
            text("SELECT 1 FROM psx_portfolios WHERE id = :pid AND user_id = :uid"),
            {"pid": portfolio_id, "uid": user_id},
        )
        if not own.first():
            raise HTTPException(404, "Portfolio not found")
        result = await conn.execute(
            text("""
                SELECT id, portfolio_id, symbol, shares, avg_cost, purchased_at
                FROM psx_holdings
                WHERE portfolio_id = :pid
                ORDER BY symbol ASC
            """),
            {"pid": portfolio_id},
        )
        rows = result.mappings().all()
    return [
        {
            "id": r["id"],
            "portfolio_id": r["portfolio_id"],
            "symbol": r["symbol"],
            "shares": r["shares"],
            "avg_cost": float(r["avg_cost"]),
            "purchased_at": str(r["purchased_at"]) if r["purchased_at"] else None,
        }
        for r in rows
    ]


@router.post("/portfolio/{portfolio_id}/holdings")
async def add_holding(
    portfolio_id: int,
    body: HoldingCreate,
    user: Annotated[dict, Depends(require_user)],
):
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        own = await conn.execute(
            text("SELECT 1 FROM psx_portfolios WHERE id = :pid AND user_id = :uid"),
            {"pid": portfolio_id, "uid": user_id},
        )
        if not own.first():
            raise HTTPException(404, "Portfolio not found")
        result = await conn.execute(
            text("""
                INSERT INTO psx_holdings (portfolio_id, symbol, shares, avg_cost, purchased_at)
                VALUES (:pid, :sym, :shares, :cost, :pdate)
                ON CONFLICT (portfolio_id, symbol) DO UPDATE
                SET shares = psx_holdings.shares + EXCLUDED.shares,
                    avg_cost = EXCLUDED.avg_cost
                RETURNING id, portfolio_id, symbol, shares, avg_cost, purchased_at
            """),
            {
                "pid": portfolio_id,
                "sym": body.symbol.upper(),
                "shares": body.shares,
                "cost": body.avg_cost,
                "pdate": body.purchased_at,
            },
        )
        row = result.mappings().first()
    return {
        "id": row["id"],
        "portfolio_id": row["portfolio_id"],
        "symbol": row["symbol"],
        "shares": row["shares"],
        "avg_cost": float(row["avg_cost"]),
        "purchased_at": str(row["purchased_at"]) if row["purchased_at"] else None,
    }


@router.patch("/portfolio/{portfolio_id}/holdings/{holding_id}")
async def update_holding(
    portfolio_id: int,
    holding_id: int,
    body: HoldingUpdate,
    user: Annotated[dict, Depends(require_user)],
):
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        own = await conn.execute(
            text("""
                SELECT h.id FROM psx_holdings h
                JOIN psx_portfolios p ON p.id = h.portfolio_id
                WHERE h.id = :hid AND p.id = :pid AND p.user_id = :uid
            """),
            {"hid": holding_id, "pid": portfolio_id, "uid": user_id},
        )
        if not own.first():
            raise HTTPException(404, "Holding not found")

        sets = []
        params: dict = {"hid": holding_id}
        if body.shares is not None:
            sets.append("shares = :shares")
            params["shares"] = body.shares
        if body.avg_cost is not None:
            sets.append("avg_cost = :cost")
            params["cost"] = body.avg_cost
        if body.purchased_at is not None:
            sets.append("purchased_at = :pdate")
            params["pdate"] = body.purchased_at
        if not sets:
            raise HTTPException(400, "No fields to update")

        result = await conn.execute(
            text(f"""
                UPDATE psx_holdings SET {", ".join(sets)}
                WHERE id = :hid
                RETURNING id, portfolio_id, symbol, shares, avg_cost, purchased_at
            """),
            params,
        )
        row = result.mappings().first()
    return {
        "id": row["id"],
        "portfolio_id": row["portfolio_id"],
        "symbol": row["symbol"],
        "shares": row["shares"],
        "avg_cost": float(row["avg_cost"]),
        "purchased_at": str(row["purchased_at"]) if row["purchased_at"] else None,
    }


@router.delete("/portfolio/{portfolio_id}/holdings/{holding_id}")
async def delete_holding(
    portfolio_id: int,
    holding_id: int,
    user: Annotated[dict, Depends(require_user)],
):
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                DELETE FROM psx_holdings h
                USING psx_portfolios p
                WHERE h.id = :hid
                  AND h.portfolio_id = p.id
                  AND p.id = :pid
                  AND p.user_id = :uid
                RETURNING h.id
            """),
            {"hid": holding_id, "pid": portfolio_id, "uid": user_id},
        )
        deleted = result.first()
    if not deleted:
        raise HTTPException(404, "Holding not found")
    return {"deleted": holding_id}


@router.get("/portfolio/{portfolio_id}/value")
async def portfolio_value(
    portfolio_id: int,
    user: Annotated[dict, Depends(require_user)],
):
    """Live P&L: join holdings with current market prices."""
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        own = await conn.execute(
            text("SELECT name FROM psx_portfolios WHERE id = :pid AND user_id = :uid"),
            {"pid": portfolio_id, "uid": user_id},
        )
        port = own.mappings().first()
        if not port:
            raise HTTPException(404, "Portfolio not found")

        result = await conn.execute(
            text("""
                SELECT
                    h.id, h.symbol, h.shares, h.avg_cost,
                    s.price AS current_price,
                    (h.shares * COALESCE(s.price, 0))::numeric AS market_value,
                    (h.shares * h.avg_cost)::numeric AS cost_basis,
                    (h.shares * COALESCE(s.price, 0) - h.shares * h.avg_cost)::numeric AS unrealized_pnl,
                    CASE WHEN (h.shares * h.avg_cost) > 0 AND s.price IS NOT NULL
                        THEN ROUND(
                            ((h.shares * s.price - h.shares * h.avg_cost) / (h.shares * h.avg_cost)) * 100,
                            2
                        )
                        ELSE 0
                    END AS pnl_pct
                FROM psx_holdings h
                LEFT JOIN psx_market_snapshot s ON s.symbol = h.symbol
                WHERE h.portfolio_id = :pid
                ORDER BY h.symbol ASC
            """),
            {"pid": portfolio_id},
        )
        rows = result.mappings().all()

    holdings = [
        {
            "id": r["id"],
            "symbol": r["symbol"],
            "shares": r["shares"],
            "avg_cost": float(r["avg_cost"]),
            "current_price": float(r["current_price"]) if r["current_price"] else None,
            "market_value": float(r["market_value"]),
            "cost_basis": float(r["cost_basis"]),
            "unrealized_pnl": float(r["unrealized_pnl"]),
            "pnl_pct": float(r["pnl_pct"]),
        }
        for r in rows
    ]
    totals = {
        "market_value": sum(h["market_value"] for h in holdings),
        "cost_basis": sum(h["cost_basis"] for h in holdings),
        "unrealized_pnl": sum(h["unrealized_pnl"] for h in holdings),
    }
    totals["pnl_pct"] = (
        round((totals["unrealized_pnl"] / totals["cost_basis"]) * 100, 2)
        if totals["cost_basis"] > 0
        else 0.0
    )
    return {
        "portfolio_id": portfolio_id,
        "name": port["name"],
        "holdings": holdings,
        "totals": totals,
    }
