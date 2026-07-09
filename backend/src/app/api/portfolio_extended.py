"""User-scoped portfolio extensions: allocation, performance, stock transactions."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import require_user
from app.db.sqlalchemy import get_session_factory
from app.services import portfolio as portfolio_service
from app.services.permissions import enforce_count_limit
from app.services.symbols import require_known_symbol

router = APIRouter(tags=["portfolio-extended"])


class AllocationResponse(BaseModel):
    by: str
    items: list[dict[str, Any]]


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

    factory = get_session_factory()
    async with factory() as session:
        if portfolio_id is None:
            row = await session.execute(
                text(
                    "SELECT id FROM psx_portfolios "
                    "WHERE user_id = :uid ORDER BY created_at ASC LIMIT 1"
                ),
                {"uid": user["user_id"]},
            )
            r = row.first()
            if not r:
                return AllocationResponse(by=by, items=[]).model_dump()
            portfolio_id = int(r[0])
        own = await session.execute(
            text(
                "SELECT 1 FROM psx_portfolios WHERE id = :pid AND user_id = :uid"
            ),
            {"pid": portfolio_id, "uid": user["user_id"]},
        )
        if not own.first():
            raise HTTPException(404, "Portfolio not found")
    items = await portfolio_service.allocation(portfolio_id, by=by)
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


class StockTransactionCreate(BaseModel):
    portfolio_id: int = Field(..., gt=0)
    symbol: str = Field(..., min_length=1, max_length=20)
    side: str = Field(..., pattern="^(buy|sell|adjust)$")
    quantity: int = Field(..., gt=0)
    price: float = Field(..., ge=0)
    fees: float = Field(0, ge=0)
    executed_at: Optional[datetime] = None
    notes: Optional[str] = None
    source: str = Field("manual", max_length=20)


class StockTransactionOut(BaseModel):
    id: int
    user_id: str
    portfolio_id: int
    symbol: str
    side: str
    quantity: int
    price: float
    fees: float
    executed_at: datetime
    notes: Optional[str]
    source: str
    created_at: datetime


@router.get("/portfolio/transactions")
async def list_stock_transactions(
    user: Annotated[dict, Depends(require_user)],
    limit: int = 100,
):
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(
            text(
                "SELECT id, user_id, portfolio_id, symbol, side, quantity, price, "
                "fees, executed_at, notes, source, created_at "
                "FROM stock_transactions WHERE user_id = :uid "
                "ORDER BY executed_at DESC LIMIT :lim"
            ),
            {"uid": user["user_id"], "lim": max(1, min(limit, 500))},
        )
        out = []
        for r in rows.mappings().all():
            out.append(
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "portfolio_id": r["portfolio_id"],
                    "symbol": r["symbol"],
                    "side": r["side"],
                    "quantity": int(r["quantity"]),
                    "price": float(r["price"]),
                    "fees": float(r["fees"]),
                    "executed_at": str(r["executed_at"]),
                    "notes": r["notes"],
                    "source": r["source"],
                    "created_at": str(r["created_at"]),
                }
            )
    return out


@router.post("/portfolio/transactions")
async def create_stock_transaction(
    body: StockTransactionCreate,
    user: Annotated[dict, Depends(require_user)],
):
    """Create a stock transaction.

    For 'buy' or 'sell', the corresponding psx_holdings row is upserted
    so the existing /api/portfolio/networth and /api/portfolio/{id}/value
    endpoints keep working without a code change.
    """
    factory = get_session_factory()
    async with factory() as session:
        # verify portfolio ownership
        own = await session.execute(
            text(
                "SELECT 1 FROM psx_portfolios WHERE id = :pid AND user_id = :uid"
            ),
            {"pid": body.portfolio_id, "uid": user["user_id"]},
        )
        if not own.first():
            raise HTTPException(404, "Portfolio not found")

        await require_known_symbol(session, body.symbol)

        if body.side == "buy":
            await enforce_count_limit(
                session,
                user,
                feature_key="max_holdings_per_portfolio",
                count_sql=(
                    "SELECT COUNT(*) FROM psx_holdings "
                    "WHERE portfolio_id = :pid AND symbol <> :sym"
                ),
                params={"pid": body.portfolio_id, "sym": body.symbol.upper()},
                label="Holdings",
            )

        executed = body.executed_at or datetime.now(timezone.utc)
        row = await session.execute(
            text(
                "INSERT INTO stock_transactions "
                "(user_id, portfolio_id, symbol, side, quantity, price, fees, "
                "executed_at, notes, source) "
                "VALUES (:uid, :pid, :sym, :side, :qty, :price, :fees, "
                "        :executed, :notes, :src) "
                "RETURNING id, user_id, portfolio_id, symbol, side, quantity, "
                "          price, fees, executed_at, notes, source, created_at"
            ),
            {
                "uid": user["user_id"],
                "pid": body.portfolio_id,
                "sym": body.symbol.upper(),
                "side": body.side,
                "qty": int(body.quantity),
                "price": float(body.price),
                "fees": float(body.fees),
                "executed": executed,
                "notes": body.notes,
                "src": body.source,
            },
        )
        r = row.mappings().first()
        # update psx_holdings: weighted average cost for buy, decrement for sell
        if body.side in ("buy", "sell"):
            existing = await session.execute(
                text(
                    "SELECT id, shares, avg_cost FROM psx_holdings "
                    "WHERE portfolio_id = :pid AND symbol = :sym"
                ),
                {"pid": body.portfolio_id, "sym": body.symbol.upper()},
            )
            er = existing.mappings().first()
            if er is None and body.side == "buy":
                await session.execute(
                    text(
                        "INSERT INTO psx_holdings "
                        "(portfolio_id, symbol, shares, avg_cost, purchased_at) "
                        "VALUES (:pid, :sym, :shares, :cost, :date)"
                    ),
                    {
                        "pid": body.portfolio_id,
                        "sym": body.symbol.upper(),
                        "shares": int(body.quantity),
                        "cost": float(body.price),
                        "date": executed.date(),
                    },
                )
            elif er is not None:
                if body.side == "buy":
                    new_shares = int(er["shares"]) + int(body.quantity)
                    new_cost = (
                        (float(er["avg_cost"]) * int(er["shares"]))
                        + (float(body.price) * int(body.quantity))
                    ) / new_shares if new_shares > 0 else 0
                    await session.execute(
                        text(
                            "UPDATE psx_holdings "
                            "SET shares = :shares, avg_cost = :cost, "
                            "    purchased_at = LEAST(purchased_at, :date) "
                            "WHERE id = :id"
                        ),
                        {
                            "shares": new_shares,
                            "cost": round(new_cost, 4),
                            "date": executed.date(),
                            "id": er["id"],
                        },
                    )
                else:  # sell
                    new_shares = max(0, int(er["shares"]) - int(body.quantity))
                    if new_shares == 0:
                        await session.execute(
                            text("DELETE FROM psx_holdings WHERE id = :id"),
                            {"id": er["id"]},
                        )
                    else:
                        await session.execute(
                            text(
                                "UPDATE psx_holdings SET shares = :s WHERE id = :id"
                            ),
                            {"s": new_shares, "id": er["id"]},
                        )

        # Reflect the trade in personal finance so a purchase (or sale) shows up
        # in the Finance transactions feed. A buy is cash out (expense), a sell is
        # cash in (income); both categorised 'Investment', source 'stock_trade'
        # so they are identifiable and can be filtered from spending later.
        if body.side in ("buy", "sell"):
            gross = float(body.price) * int(body.quantity)
            if body.side == "buy":
                fin_type = "expense"
                fin_amount = gross + float(body.fees)
                merchant = f"Buy {int(body.quantity)} {body.symbol.upper()}"
            else:
                fin_type = "income"
                fin_amount = max(0.01, gross - float(body.fees))
                merchant = f"Sell {int(body.quantity)} {body.symbol.upper()}"
            await session.execute(
                text(
                    "INSERT INTO user_transactions "
                    "(user_id, merchant, amount, currency, transaction_type, category, "
                    " transaction_date, source, note) "
                    "VALUES (:uid, :merchant, :amount, 'PKR', :ttype, 'Investment', "
                    "        :txdate, 'stock_trade', :note)"
                ),
                {
                    "uid": user["user_id"],
                    "merchant": merchant,
                    "amount": round(fin_amount, 2),
                    "ttype": fin_type,
                    "txdate": executed,
                    "note": f"{int(body.quantity)} @ {float(body.price)}",
                },
            )

        await session.commit()
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "portfolio_id": r["portfolio_id"],
        "symbol": r["symbol"],
        "side": r["side"],
        "quantity": int(r["quantity"]),
        "price": float(r["price"]),
        "fees": float(r["fees"]),
        "executed_at": str(r["executed_at"]),
        "notes": r["notes"],
        "source": r["source"],
        "created_at": str(r["created_at"]),
    }
