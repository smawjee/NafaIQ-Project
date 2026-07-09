from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import require_user
from app.db.sqlalchemy import get_engine
from app.services import portfolio as portfolio_service
from app.services.permissions import enforce_count_limit
from app.services.symbols import require_known_symbol

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
        await enforce_count_limit(
            conn,
            user,
            feature_key="max_portfolios",
            count_sql="SELECT COUNT(*) FROM psx_portfolios WHERE user_id = :uid",
            params={"uid": user_id},
            label="Portfolios",
        )
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
        await require_known_symbol(conn, body.symbol)
        await enforce_count_limit(
            conn,
            user,
            feature_key="max_holdings_per_portfolio",
            count_sql="SELECT COUNT(*) FROM psx_holdings WHERE portfolio_id = :pid AND symbol <> :sym",
            params={"pid": portfolio_id, "sym": body.symbol.upper()},
            label="Holdings",
        )
        result = await conn.execute(
            text("""
                INSERT INTO psx_holdings (portfolio_id, symbol, shares, avg_cost, purchased_at)
                VALUES (:pid, :sym, :shares, :cost, :pdate)
                ON CONFLICT (portfolio_id, symbol) DO UPDATE
                SET shares = psx_holdings.shares + EXCLUDED.shares,
                    avg_cost = (psx_holdings.avg_cost * psx_holdings.shares + EXCLUDED.avg_cost * EXCLUDED.shares)
                               / NULLIF(psx_holdings.shares + EXCLUDED.shares, 0)
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
                -- Resolve current price: live snapshot -> latest EOD close.
                -- Market value falls back to cost basis when a symbol cannot be
                -- priced at all, so unpriceable holdings read flat (0 gain)
                -- instead of a spurious -100% loss.
                SELECT
                    h.id, h.symbol, h.shares, h.avg_cost,
                    COALESCE(s.price, o.close) AS current_price,
                    (h.shares * COALESCE(s.price, o.close, h.avg_cost))::numeric AS market_value,
                    (h.shares * h.avg_cost)::numeric AS cost_basis,
                    (h.shares * COALESCE(s.price, o.close, h.avg_cost) - h.shares * h.avg_cost)::numeric AS unrealized_pnl,
                    CASE WHEN (h.shares * h.avg_cost) > 0 AND COALESCE(s.price, o.close) IS NOT NULL
                        THEN ROUND(
                            ((h.shares * COALESCE(s.price, o.close) - h.shares * h.avg_cost) / (h.shares * h.avg_cost)) * 100,
                            2
                        )
                        ELSE 0
                    END AS pnl_pct
                FROM psx_holdings h
                LEFT JOIN psx_market_snapshot s ON s.symbol = h.symbol
                LEFT JOIN LATERAL (
                    SELECT close FROM psx_ohlcv WHERE symbol = h.symbol ORDER BY date DESC LIMIT 1
                ) o ON TRUE
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


class NetworthHolding(BaseModel):
    symbol: str
    shares: int
    avg_cost: float
    current_price: float | None
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    pnl_pct: float
    previous_close: float | None
    today_pnl: float


class NetworthResponse(BaseModel):
    total_market_value: float
    total_cost_basis: float
    total_unrealized_pnl: float
    total_unrealized_pnl_pct: float
    today_pnl: float
    today_pnl_pct: float
    portfolio_count: int
    holding_count: int
    by_holding: list[NetworthHolding]


class PortfolioHistoryPoint(BaseModel):
    date: str
    label: str
    value: float
    benchmark: float


class PortfolioHistoryResponse(BaseModel):
    days: int
    points: list[PortfolioHistoryPoint]


@router.get("/portfolio/networth")
async def portfolio_networth(
    user: Annotated[dict, Depends(require_user)],
):
    """Sum totals across all user portfolios with buy-date-aware today P&L."""
    user_id = user["user_id"]
    data = await portfolio_service.networth(user_id)
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
    """Historical portfolio value based on current holdings and PSX closes.

    The app does not yet store full portfolio transaction lots, so this values
    the user's current holdings across historical daily closes. KSE-100 is
    normalized to the first portfolio value in the returned range so the chart
    compares relative movement on the same scale.
    """
    user_id = user["user_id"]
    bounded_days = max(7, min(days, 365))
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                WITH portfolio_values AS (
                    SELECT
                        o.date,
                        COALESCE(SUM(h.shares * o.close), 0)::numeric AS value
                    FROM psx_holdings h
                    JOIN psx_portfolios p
                      ON p.id = h.portfolio_id
                     AND p.user_id = :uid
                    JOIN psx_ohlcv o
                      ON o.symbol = h.symbol
                    -- Chart shows the value of the CURRENT portfolio across
                    -- historical closes (no purchased_at filter: a holding
                    -- bought today would otherwise have zero bars until the
                    -- nightly OHLCV backfill -> empty chart).
                    WHERE o.date >= CURRENT_DATE - (:days * INTERVAL '1 day')
                    GROUP BY o.date
                ),
                joined AS (
                    SELECT
                        pv.date,
                        pv.value,
                        idx.close AS index_close,
                        FIRST_VALUE(pv.value) OVER (ORDER BY pv.date ASC) AS first_value,
                        FIRST_VALUE(idx.close) OVER (ORDER BY pv.date ASC) AS first_index_close
                    FROM portfolio_values pv
                    LEFT JOIN psx_index_eod idx
                      ON idx.code = 'KSE100'
                     AND idx.date = pv.date
                    WHERE pv.value > 0
                )
                SELECT
                    date,
                    value,
                    CASE
                        WHEN first_value > 0
                         AND first_index_close IS NOT NULL
                         AND first_index_close <> 0
                         AND index_close IS NOT NULL
                        THEN (index_close / first_index_close) * first_value
                        ELSE value
                    END::numeric AS benchmark
                FROM joined
                ORDER BY date ASC
            """),
            {"uid": user_id, "days": bounded_days},
        )
        rows = result.mappings().all()

        # Append a live "today" point from the market snapshot when today's EOD
        # bar hasn't been ingested yet (nightly backfill), so a freshly bought
        # portfolio charts immediately instead of showing an empty state.
        last_date = rows[-1]["date"] if rows else None
        today_row = None
        if last_date is None or str(last_date) < str(datetime.now(timezone.utc).date()):
            live = await conn.execute(
                text("""
                    SELECT SUM(
                        h.shares * COALESCE(s.price, lc.eod_close, h.avg_cost)
                    )::numeric AS value
                    FROM psx_holdings h
                    JOIN psx_portfolios p ON p.id = h.portfolio_id AND p.user_id = :uid
                    LEFT JOIN psx_market_snapshot s ON s.symbol = h.symbol
                    LEFT JOIN LATERAL (
                        SELECT close AS eod_close FROM psx_ohlcv
                        WHERE symbol = h.symbol ORDER BY date DESC LIMIT 1
                    ) lc ON TRUE
                """),
                {"uid": user_id},
            )
            live_value = live.scalar()
            if live_value and float(live_value) > 0:
                today = datetime.now(timezone.utc).date()
                today_row = {
                    "date": today,
                    "value": float(live_value),
                    # carry the last benchmark forward so the overlay stays continuous
                    "benchmark": float(rows[-1]["benchmark"]) if rows else float(live_value),
                }

    points = [
        PortfolioHistoryPoint(
            date=str(r["date"]),
            label=r["date"].strftime("%b %d") if hasattr(r["date"], "strftime") else str(r["date"]),
            value=float(r["value"]),
            benchmark=float(r["benchmark"]),
        )
        for r in rows
    ]
    if today_row is not None:
        points.append(
            PortfolioHistoryPoint(
                date=str(today_row["date"]),
                label=today_row["date"].strftime("%b %d"),
                value=today_row["value"],
                benchmark=today_row["benchmark"],
            )
        )

    return PortfolioHistoryResponse(days=bounded_days, points=points)


@router.get("/watchlist")
async def get_watchlist(
    user: Annotated[dict, Depends(require_user)],
):
    """Return user's watchlist with real-time price and company name enrichment."""
    return await portfolio_service.enriched_watchlist(user["user_id"])
