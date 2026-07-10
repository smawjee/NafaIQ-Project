"""Stock transactions (trades): record a buy/sell, upsert the holding with
weighted-average cost, and reflect the cash movement into personal finance."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.repositories import portfolio as repo
from app.repositories.base import connect, session
from app.schemas.portfolio import StockTransactionCreate
from app.services.permissions import check_count_limit
from app.services.symbols import require_known_symbol


async def list_stock_transactions(user_id: str, limit: int = 100) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_stock_transactions(conn, user_id, limit)


async def _apply_holding_change(conn, body: StockTransactionCreate, executed) -> None:
    """Weighted-average-cost buy / decrement-or-remove sell on the holding."""
    existing = await repo.get_holding_by_symbol(conn, body.portfolio_id, body.symbol)
    if existing is None and body.side == "buy":
        await repo.insert_holding(
            conn, body.portfolio_id, body.symbol, int(body.quantity),
            float(body.price), executed.date(),
        )
    elif existing is not None:
        if body.side == "buy":
            new_shares = existing["shares"] + int(body.quantity)
            new_cost = (
                (existing["avg_cost"] * existing["shares"])
                + (float(body.price) * int(body.quantity))
            ) / new_shares if new_shares > 0 else 0
            await repo.update_holding_position(
                conn, existing["id"], new_shares, round(new_cost, 4), executed.date()
            )
        else:  # sell
            new_shares = max(0, existing["shares"] - int(body.quantity))
            if new_shares == 0:
                await repo.delete_holding_by_id(conn, existing["id"])
            else:
                await repo.set_holding_shares(conn, existing["id"], new_shares)


async def create_stock_transaction(user: dict, body: StockTransactionCreate) -> dict[str, Any]:
    """Record a trade; for buy/sell also upsert the holding (weighted average
    cost) and reflect the cash movement into personal finance."""
    async with session() as sess:
        if not await repo.is_portfolio_owned(sess, user["user_id"], body.portfolio_id):
            raise HTTPException(404, "Portfolio not found")

        await require_known_symbol(sess, body.symbol)

        if body.side == "buy":
            current = await repo.count_holdings(sess, body.portfolio_id, body.symbol)
            check_count_limit(
                user, feature_key="max_holdings_per_portfolio", current=current, label="Holdings"
            )
        elif body.side == "sell":
            # Reject selling more shares than are held — otherwise the trade would
            # book phantom income and silently delete the position.
            holding = await repo.get_holding_by_symbol(sess, body.portfolio_id, body.symbol)
            held = holding["shares"] if holding else 0
            if held < int(body.quantity):
                raise HTTPException(
                    400,
                    f"Insufficient shares to sell: you hold {held} {body.symbol.upper()}, "
                    f"tried to sell {int(body.quantity)}.",
                )

        executed = body.executed_at or datetime.now(timezone.utc)
        r = await repo.insert_stock_transaction(
            sess,
            user_id=user["user_id"],
            portfolio_id=body.portfolio_id,
            symbol=body.symbol,
            side=body.side,
            quantity=int(body.quantity),
            price=float(body.price),
            fees=float(body.fees),
            executed_at=executed,
            notes=body.notes,
            source=body.source,
        )

        if body.side in ("buy", "sell"):
            await _apply_holding_change(sess, body, executed)

            # Reflect the trade in personal finance: a buy is cash out
            # (expense), a sell is cash in (income); categorised 'Investment',
            # source 'stock_trade' so they're identifiable/filterable later.
            gross = float(body.price) * int(body.quantity)
            if body.side == "buy":
                fin_type = "expense"
                fin_amount = gross + float(body.fees)
                merchant = f"Buy {int(body.quantity)} {body.symbol.upper()}"
            else:
                fin_type = "income"
                fin_amount = max(0.01, gross - float(body.fees))
                merchant = f"Sell {int(body.quantity)} {body.symbol.upper()}"
            await repo.insert_finance_reflection(
                sess,
                user_id=user["user_id"],
                merchant=merchant,
                amount=round(fin_amount, 2),
                transaction_type=fin_type,
                transaction_date=executed,
                note=f"{int(body.quantity)} @ {float(body.price)}",
                stock_transaction_id=r["id"],
            )

        await sess.commit()
    return r
