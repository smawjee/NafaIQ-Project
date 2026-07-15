"""Stock transactions (trades): record a buy/sell, upsert the holding with
weighted-average cost, and reflect the cash movement into personal finance.

`stock_transactions` is the SINGLE SOURCE OF TRUTH for a portfolio's positions.
`psx_holdings` is a stored aggregate with no DB trigger and no FK back to the
lots, so every write path that mutates `psx_holdings` MUST also record a
`stock_transactions` row through `record_trade_atomic` — otherwise the aggregate
drifts and cannot be reconciled. `rebuild_holdings_from_transactions` and
`detect_holding_drift` are the reconciliation safety net over that invariant.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException

from app.repositories import portfolio as repo
from app.repositories.base import begin, connect, session
from app.schemas.portfolio import StockTransactionCreate
from app.services.notifier import fire_and_forget, notify_activity
from app.services.permissions import check_count_limit
from app.services.symbols import require_known_symbol

# Floats never compare exactly; avg_cost is NUMERIC(_,4) and shares is integer.
_AVG_COST_TOL = 0.01


async def list_stock_transactions(user_id: str, limit: int = 100) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_stock_transactions(conn, user_id, limit)


async def _apply_holding_change(conn, body: StockTransactionCreate, executed) -> None:
    """Mutate psx_holdings for one lot.

    - buy:    weighted-average-cost add (create if missing)
    - sell:   decrement shares; delete the row if it reaches zero
    - adjust: authoritative ABSOLUTE snapshot — set shares/avg_cost to the row's
              quantity/price (this is how corrections and the rebuild reset a
              position to a known state).
    """
    existing = await repo.get_holding_by_symbol(conn, body.portfolio_id, body.symbol)
    if body.side == "adjust":
        if existing is None:
            await repo.insert_holding(
                conn, body.portfolio_id, body.symbol, int(body.quantity),
                float(body.price), executed.date(),
            )
        else:
            await repo.update_holding_position(
                conn, existing["id"], int(body.quantity), float(body.price), executed.date()
            )
        return
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


async def _reflect_finance(
    conn, *, user_id: str, body: StockTransactionCreate, executed, stock_transaction_id: int
) -> None:
    """Mirror a real cash movement into the personal-finance feed: a buy is cash
    out (expense), a sell is cash in (income); categorised 'Investment', source
    'stock_trade' so they stay identifiable and are excluded from expense
    aggregations. Only real trades / opening positions reflect — never
    PATCH/DELETE corrections (which would book phantom cash)."""
    gross = float(body.price) * int(body.quantity)
    if body.side == "buy":
        fin_type = "expense"
        fin_amount = gross + float(body.fees)
        merchant = f"Buy {int(body.quantity)} {body.symbol.upper()}"
    else:  # sell
        fin_type = "income"
        fin_amount = max(0.01, gross - float(body.fees))
        merchant = f"Sell {int(body.quantity)} {body.symbol.upper()}"
    await repo.insert_finance_reflection(
        conn,
        user_id=user_id,
        merchant=merchant,
        amount=round(fin_amount, 2),
        transaction_type=fin_type,
        transaction_date=executed,
        note=f"{int(body.quantity)} @ {float(body.price)}",
        stock_transaction_id=stock_transaction_id,
    )


async def record_trade_atomic(
    conn,
    *,
    user_id: str,
    body: StockTransactionCreate,
    executed: datetime,
    apply_holding: bool = True,
    reflect_finance: bool = True,
) -> dict[str, Any]:
    """Reusable, atomic core shared by every write path that touches a position.

    Within the caller's open transaction it (a) records a `stock_transactions`
    row, (b) optionally applies the holding change, (c) optionally inserts the
    `user_transactions` finance reflection. The caller owns the transaction
    boundary and ALL guards (ownership, quota, symbol validation,
    insufficient-shares). This is the single place a lot is written, so the
    aggregate can always be rebuilt from history.
    """
    r = await repo.insert_stock_transaction(
        conn,
        user_id=user_id,
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
    if apply_holding:
        await _apply_holding_change(conn, body, executed)
    if reflect_finance:
        await _reflect_finance(
            conn, user_id=user_id, body=body, executed=executed, stock_transaction_id=r["id"]
        )
    return r


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
        # Preserve existing behaviour: only buy/sell apply a holding change +
        # finance reflection; a bare `adjust` posted here records history only.
        do_side = body.side in ("buy", "sell")
        r = await record_trade_atomic(
            sess,
            user_id=user["user_id"],
            body=body,
            executed=executed,
            apply_holding=do_side,
            reflect_finance=do_side,
        )
        await sess.commit()
    verb = {"buy": "Bought", "sell": "Sold", "adjust": "Adjusted"}.get(body.side, body.side)
    fire_and_forget(
        notify_activity(
            user["user_id"],
            "trade",
            f"Trade executed: {verb} {body.symbol.upper()}",
            f"{verb} {int(body.quantity)} {body.symbol.upper()} @ PKR {float(body.price):,.2f}.",
        )
    )
    return r


# ---------------------------------------------------------------------------
# Reconciliation safety net: rebuild holdings from lots, and detect drift.
# ---------------------------------------------------------------------------


def _fold_lots(rows: list[dict[str, Any]]) -> tuple[int, float, Optional[date]]:
    """Reduce one symbol's ordered lots to (shares, avg_cost, first_lot_date).

    Fold semantics — the single definition every write path is consistent with:
      - buy:    weighted-average-cost add
      - sell:   subtract shares (avg_cost unchanged; reset to 0 when flat)
      - adjust: authoritative absolute snapshot (shares = quantity,
                avg_cost = price)

    `avg_cost` is the guaranteed reconstruction; `first_lot_date` is best-effort
    (earliest buy/adjust date) for the display-only purchased_at column.
    """
    shares = 0
    avg = 0.0
    first_date: Optional[date] = None
    for r in rows:
        side = r["side"]
        qty = int(r["quantity"])
        price = float(r["price"])
        ex = r.get("executed_at")
        ex_date = ex.date() if isinstance(ex, datetime) else ex
        if side == "buy":
            new_shares = shares + qty
            avg = ((avg * shares) + (price * qty)) / new_shares if new_shares > 0 else 0.0
            shares = new_shares
            if ex_date is not None:
                first_date = ex_date if first_date is None else min(first_date, ex_date)
        elif side == "sell":
            shares = max(0, shares - qty)
            if shares == 0:
                avg = 0.0
        elif side == "adjust":
            shares = qty
            avg = price
            if ex_date is not None:
                first_date = ex_date if first_date is None else min(first_date, ex_date)
    return shares, round(avg, 4), first_date


def _group_by_symbol(lots: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for lot in lots:
        grouped.setdefault(lot["symbol"], []).append(lot)
    return grouped


async def rebuild_holdings_from_transactions(portfolio_id: int) -> dict[str, Any]:
    """Recompute each holding's shares/avg_cost purely from that portfolio's
    `stock_transactions` (the source of truth) and overwrite psx_holdings.

    Symbols whose lots fold to zero shares have their holding deleted. Symbols
    that exist in psx_holdings but have NO backing lots are left untouched (they
    need the backfill script first) and are surfaced by `detect_holding_drift`.
    """
    async with begin() as conn:
        lots = await repo.fetch_portfolio_lots(conn, portfolio_id)
        results: list[dict[str, Any]] = []
        for symbol, rows in _group_by_symbol(lots).items():
            shares, avg, first_date = _fold_lots(rows)
            if shares > 0:
                await repo.set_holding_position_by_symbol(
                    conn, portfolio_id, symbol, shares, avg, first_date
                )
            else:
                await repo.delete_holding_by_symbol(conn, portfolio_id, symbol)
            results.append({"symbol": symbol, "shares": shares, "avg_cost": avg})
    return {"portfolio_id": portfolio_id, "holdings": results}


async def detect_holding_drift(
    portfolio_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Compare each psx_holdings row to the aggregate of its `stock_transactions`
    lots. Returns one entry per mismatch — including holdings that have no
    backing lots at all (`has_lots=False`), which are the un-reconciled rows the
    backfill script must repair.
    """
    mismatches: list[dict[str, Any]] = []
    async with connect() as conn:
        holdings = await repo.fetch_holdings_for_drift(conn, portfolio_id)
        for h in holdings:
            lots = await repo.fetch_symbol_lots(conn, h["portfolio_id"], h["symbol"])
            exp_shares, exp_avg, _ = _fold_lots(lots)
            shares_off = int(h["shares"]) != exp_shares
            avg_off = abs(float(h["avg_cost"]) - exp_avg) > _AVG_COST_TOL
            if shares_off or avg_off:
                mismatches.append(
                    {
                        "portfolio_id": h["portfolio_id"],
                        "symbol": h["symbol"],
                        "holding_shares": int(h["shares"]),
                        "expected_shares": exp_shares,
                        "holding_avg_cost": float(h["avg_cost"]),
                        "expected_avg_cost": exp_avg,
                        "has_lots": len(lots) > 0,
                    }
                )
    return mismatches
