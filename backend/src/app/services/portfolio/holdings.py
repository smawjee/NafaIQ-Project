"""Portfolio & holding CRUD. Business logic over portfolio.

Every holding mutation here routes a `stock_transactions` lot through the trade
core (`trades.record_trade_atomic`) so `psx_holdings` can always be reconciled
from history:

- add_holding    -> `buy`   lot + finance reflection (an opening position is a
                            real cash movement, consistent with the trade path).
- update_holding -> `adjust` lot (absolute snapshot of the corrected shares/
                            avg_cost), NO finance reflection — a correction is
                            not a trade and must not book phantom cash.
- delete_holding -> deletes the symbol's lots and their finance reflections
                            (a holding exists because a transaction happened, so
                            removing the holding removes the transaction).
- sell_holding   -> `sell`  lot at the user's stated sale price + finance
                            reflection. The real-exit counterpart to delete: the
                            UI offers both, because "I sold it" and "this
                            shouldn't be here" are different economic events.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException

from app.repositories import portfolio as repo
from app.repositories.base import begin, connect, session
from app.schemas.portfolio import (
    HoldingCreate,
    HoldingSell,
    HoldingUpdate,
    StockTransactionCreate,
)
from app.services.notifier import fire_and_forget, notify_activity
from app.services.permissions import check_count_limit
from app.services.portfolio.trades import record_trade_atomic
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


def _parse_purchased_at(purchased_at: Optional[str]) -> datetime:
    """Parse a holding's purchased_at (date string) for the display-only
    purchased_at column. Falls back to now() when absent or unparseable."""
    if purchased_at:
        try:
            return datetime.fromisoformat(purchased_at)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


async def add_holding(user: dict, portfolio_id: int, body: HoldingCreate) -> dict[str, Any]:
    """Manual add: record a `buy` lot + finance reflection through the trade
    core, then return the resulting holding. Preserves the ownership check,
    known-symbol validation, and the max-holdings quota."""
    user_id = user["user_id"]
    async with session() as sess:
        if not await repo.is_portfolio_owned(sess, user_id, portfolio_id):
            raise HTTPException(404, "Portfolio not found")
        await require_known_symbol(sess, body.symbol)
        current = await repo.count_holdings(sess, portfolio_id, body.symbol)
        check_count_limit(
            user, feature_key="max_holdings_per_portfolio", current=current, label="Holdings"
        )

        # Lot time = now, never body.purchased_at. `_fold_lots` reads an `adjust`
        # lot as an absolute snapshot, so a back-dated buy would sort ahead of a
        # prior correction and be folded away — the buy would vanish from the
        # reconstruction. A back-dated buy is therefore no longer economically
        # meaningful; purchased_at survives as display metadata only (below).
        executed = datetime.now(timezone.utc)
        trade = StockTransactionCreate(
            portfolio_id=portfolio_id,
            symbol=body.symbol,
            side="buy",
            quantity=int(body.shares),
            price=float(body.avg_cost),
            fees=0.0,
            executed_at=executed,
            notes="Manual holding add",
            source="manual",
        )
        await record_trade_atomic(
            sess, user_id=user_id, body=trade, executed=executed,
            apply_holding=True, reflect_finance=True,
        )
        holding = await repo.get_holding_by_symbol_full(sess, portfolio_id, body.symbol)
        # `_apply_holding_change` stamped purchased_at from the lot time; restore
        # the user's date, which is what this column is for.
        purchased = _parse_purchased_at(body.purchased_at).date()
        if holding is not None and purchased != executed.date():
            holding = await repo.update_holding_fields(
                sess, holding["id"], {"purchased_at": purchased}
            )
        await sess.commit()

    # Activity notification (from dev). Fired only after the transaction has
    # committed, so a rolled-back add cannot notify the user about a holding
    # that does not exist. dev raised it on the older repo.upsert_holding_add
    # path; that path is not restored here — this module's contract is that
    # every holding mutation goes through record_trade_atomic, so psx_holdings
    # stays reconcilable from stock_transactions history.
    fire_and_forget(
        notify_activity(
            user_id,
            "trade",
            f"Holding added: {body.symbol.upper()}",
            f"Added {body.shares} {body.symbol.upper()} at PKR {float(body.avg_cost):,.2f} average cost.",
        )
    )
    return holding


async def update_holding(
    user_id: str, portfolio_id: int, holding_id: int, body: HoldingUpdate
) -> dict[str, Any]:
    """PATCH a holding as a CORRECTION: record an `adjust` lot capturing the
    corrected absolute shares/avg_cost so the change is in history and the
    holding stays reconstructable, then apply the field update. No finance
    reflection — a correction is not a cash movement."""
    fields: dict[str, Any] = {}
    if body.shares is not None:
        fields["shares"] = body.shares
    if body.avg_cost is not None:
        fields["avg_cost"] = body.avg_cost
    if body.purchased_at is not None:
        fields["purchased_at"] = body.purchased_at
    if not fields:
        raise HTTPException(400, "No fields to update")

    async with session() as sess:
        holding = await repo.get_owned_holding(sess, user_id, portfolio_id, holding_id)
        if holding is None:
            raise HTTPException(404, "Holding not found")

        # Record an adjust lot only when a drift-relevant field (shares/avg_cost)
        # changes; a purchased_at-only edit does not affect reconstruction.
        if body.shares is not None or body.avg_cost is not None:
            new_shares = int(body.shares) if body.shares is not None else int(holding["shares"])
            new_avg = float(body.avg_cost) if body.avg_cost is not None else float(holding["avg_cost"])
            # Correction time = now, so the adjust snapshot orders AFTER any prior
            # lots and acts as the authoritative reset in the fold.
            executed = datetime.now(timezone.utc)
            note = (
                "Holding correction (avg_cost only)"
                if body.shares is None
                else "Holding correction (shares/avg_cost)"
            )
            trade = StockTransactionCreate(
                portfolio_id=portfolio_id,
                symbol=holding["symbol"],
                side="adjust",
                quantity=new_shares,
                price=new_avg,
                fees=0.0,
                executed_at=executed,
                notes=note,
                source="manual",
            )
            await record_trade_atomic(
                sess, user_id=user_id, body=trade, executed=executed,
                apply_holding=False, reflect_finance=False,
            )

        updated = await repo.update_holding_fields(sess, holding_id, fields)
        await sess.commit()
    return updated


async def delete_holding(user_id: str, portfolio_id: int, holding_id: int) -> dict[str, Any]:
    """DELETE a holding: remove the position AND the transactions that created it.

    Product rule: a holding exists because a transaction happened, so deleting
    the holding deletes its `stock_transactions` lots and the buy `expense`
    reflections mirroring them. This replaces the previous behaviour of appending
    a closing `sell` lot, which left the transaction feed showing trades for a
    position the user had explicitly removed.

    Realised income from any real prior sales of the same symbol is PRESERVED —
    that cash was actually received (see delete_symbol_lots). Scoped to this
    (portfolio, symbol); other holdings are untouched.
    """
    async with session() as sess:
        holding = await repo.get_owned_holding(sess, user_id, portfolio_id, holding_id)
        if holding is None:
            raise HTTPException(404, "Holding not found")

        removed = await repo.delete_symbol_lots(sess, portfolio_id, holding["symbol"])
        await repo.delete_holding_by_id(sess, holding_id)
        await sess.commit()
    return {
        "deleted": holding_id,
        "lots_deleted": removed["lots_deleted"],
        "reflections_deleted": removed["reflections_deleted"],
        # Realised income from any real prior sales of this symbol is kept, not
        # erased — surfaced so the UI/caller can say so rather than implying a
        # clean wipe.
        "income_preserved": removed["income_preserved"],
    }


async def sell_holding(
    user_id: str, portfolio_id: int, holding_id: int, body: HoldingSell
) -> dict[str, Any]:
    """Sell the ENTIRE position at a user-supplied price — a real exit.

    The counterpart to `delete_holding`. The UI offers both when a user removes a
    holding, because they are different economic events:

      sell   -> cash came in. Records a `sell` lot at the stated price and
                reflects the proceeds into personal finance as income, so the
                exit shows up in the transaction feed like any other trade.
      delete -> no cash ever moved. Removes the lots entirely (see delete_holding).

    The sell takes shares to zero, so `_apply_holding_change` drops the holding
    row and the surviving buy/sell lots fold to a flat position — no drift.

    Realised P&L is returned for display. It is deliberately not stored: there is
    no column for it, and the buy expense plus this sell income already net to the
    same figure in the finance feed.

    Partial sales are not handled here — this is the "remove this holding" flow.
    Use POST /trades with side='sell' to sell part of a position.
    """
    async with session() as sess:
        holding = await repo.get_owned_holding(sess, user_id, portfolio_id, holding_id)
        if holding is None:
            raise HTTPException(404, "Holding not found")

        shares = int(holding["shares"])
        if shares <= 0:
            raise HTTPException(400, "Holding has no shares to sell")

        executed = body.executed_at or datetime.now(timezone.utc)
        # A trade cannot have happened in the future; without this guard a
        # mistyped year lands a phantom future cash movement in the finance feed.
        if executed > datetime.now(timezone.utc):
            raise HTTPException(400, "executed_at cannot be in the future")

        symbol = holding["symbol"]
        avg_cost = float(holding["avg_cost"])
        price = float(body.price)
        fees = float(body.fees)

        trade = StockTransactionCreate(
            portfolio_id=portfolio_id,
            symbol=symbol,
            side="sell",
            quantity=shares,
            price=price,
            fees=fees,
            executed_at=executed,
            notes=body.notes or "Holding sold (full exit)",
            source="manual",
        )
        await record_trade_atomic(
            sess, user_id=user_id, body=trade, executed=executed,
            apply_holding=True, reflect_finance=True,
        )
        await sess.commit()

    cost_basis = avg_cost * shares
    proceeds = round((price * shares) - fees, 2)
    realized_pnl = round(proceeds - cost_basis, 2)
    realized_pnl_pct = round((realized_pnl / cost_basis) * 100, 2) if cost_basis > 0 else 0.0

    fire_and_forget(
        notify_activity(
            user_id,
            "trade",
            f"Holding sold: {symbol.upper()}",
            f"Sold {shares} {symbol.upper()} at PKR {price:,.2f} "
            f"for PKR {proceeds:,.2f} ({realized_pnl:+,.2f} realised).",
        )
    )
    return {
        "sold": holding_id,
        "symbol": symbol,
        "shares": shares,
        "price": price,
        "fees": fees,
        "proceeds": proceeds,
        "cost_basis": round(cost_basis, 2),
        "realized_pnl": realized_pnl,
        "realized_pnl_pct": realized_pnl_pct,
    }


async def resolve_owned_portfolio(user_id: str, portfolio_id: Optional[int]) -> Optional[int]:
    """None -> user's first portfolio (or None); an explicit id must be owned."""
    async with connect() as conn:
        if portfolio_id is None:
            return await repo.first_portfolio_id(conn, user_id)
        if not await repo.is_portfolio_owned(conn, user_id, portfolio_id):
            raise HTTPException(404, "Portfolio not found")
        return portfolio_id
