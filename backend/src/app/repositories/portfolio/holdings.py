"""Holding-row data access (psx_holdings): CRUD + ownership/quota checks."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import text

Executor = Any


def _holding_dict(r: Any) -> dict[str, Any]:
    return {
        "id": r["id"],
        "portfolio_id": r["portfolio_id"],
        "symbol": r["symbol"],
        "shares": int(r["shares"]),
        "avg_cost": float(r["avg_cost"]),
        "purchased_at": str(r["purchased_at"]) if r["purchased_at"] is not None else None,
    }


async def count_holdings(conn: Executor, portfolio_id: int, exclude_symbol: str) -> int:
    """Holdings in a portfolio excluding one symbol (for add-holding quota:
    updating an existing symbol must not be blocked by the limit)."""
    result = await conn.execute(
        text(
            "SELECT COUNT(*) FROM psx_holdings "
            "WHERE portfolio_id = :pid AND symbol <> :sym"
        ),
        {"pid": portfolio_id, "sym": exclude_symbol.upper()},
    )
    return int(result.scalar() or 0)


async def list_holdings(conn: Executor, portfolio_id: int) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            """
            SELECT id, portfolio_id, symbol, shares, avg_cost, purchased_at
            FROM psx_holdings
            WHERE portfolio_id = :pid
            ORDER BY symbol ASC
            """
        ),
        {"pid": portfolio_id},
    )
    return [_holding_dict(r) for r in result.mappings().all()]


async def is_holding_owned(
    conn: Executor, user_id: str, portfolio_id: int, holding_id: int
) -> bool:
    result = await conn.execute(
        text(
            """
            SELECT h.id FROM psx_holdings h
            JOIN psx_portfolios p ON p.id = h.portfolio_id
            WHERE h.id = :hid AND p.id = :pid AND p.user_id = :uid
            """
        ),
        {"hid": holding_id, "pid": portfolio_id, "uid": user_id},
    )
    return result.first() is not None


async def upsert_holding_add(
    conn: Executor,
    portfolio_id: int,
    symbol: str,
    shares: int,
    avg_cost: float,
    purchased_at: Optional[str],
) -> dict[str, Any]:
    """Add shares to a holding (weighted-average cost) or create it."""
    result = await conn.execute(
        text(
            """
            INSERT INTO psx_holdings (portfolio_id, symbol, shares, avg_cost, purchased_at)
            VALUES (:pid, :sym, :shares, :cost, :pdate)
            ON CONFLICT (portfolio_id, symbol) DO UPDATE
            SET shares = psx_holdings.shares + EXCLUDED.shares,
                avg_cost = (psx_holdings.avg_cost * psx_holdings.shares + EXCLUDED.avg_cost * EXCLUDED.shares)
                           / NULLIF(psx_holdings.shares + EXCLUDED.shares, 0)
            RETURNING id, portfolio_id, symbol, shares, avg_cost, purchased_at
            """
        ),
        {
            "pid": portfolio_id,
            "sym": symbol.upper(),
            "shares": shares,
            "cost": avg_cost,
            "pdate": purchased_at,
        },
    )
    return _holding_dict(result.mappings().first())


async def update_holding_fields(
    conn: Executor, holding_id: int, fields: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """Patch shares/avg_cost/purchased_at. `fields` uses column names."""
    column_bind = {"shares": "shares", "avg_cost": "cost", "purchased_at": "pdate"}
    sets: list[str] = []
    params: dict[str, Any] = {"hid": holding_id}
    for col, bind in column_bind.items():
        if col in fields:
            sets.append(f"{col} = :{bind}")
            params[bind] = fields[col]
    if not sets:
        return None
    result = await conn.execute(
        text(
            f"""
            UPDATE psx_holdings SET {", ".join(sets)}
            WHERE id = :hid
            RETURNING id, portfolio_id, symbol, shares, avg_cost, purchased_at
            """
        ),
        params,
    )
    return _holding_dict(result.mappings().first())


async def delete_holding(
    conn: Executor, user_id: str, portfolio_id: int, holding_id: int
) -> Optional[int]:
    result = await conn.execute(
        text(
            """
            DELETE FROM psx_holdings h
            USING psx_portfolios p
            WHERE h.id = :hid
              AND h.portfolio_id = p.id
              AND p.id = :pid
              AND p.user_id = :uid
            RETURNING h.id
            """
        ),
        {"hid": holding_id, "pid": portfolio_id, "uid": user_id},
    )
    row = result.first()
    return int(row[0]) if row else None


async def get_holding_by_symbol(
    conn: Executor, portfolio_id: int, symbol: str
) -> Optional[dict[str, Any]]:
    result = await conn.execute(
        text(
            "SELECT id, shares, avg_cost FROM psx_holdings "
            "WHERE portfolio_id = :pid AND symbol = :sym"
        ),
        {"pid": portfolio_id, "sym": symbol.upper()},
    )
    r = result.mappings().first()
    if r is None:
        return None
    return {"id": r["id"], "shares": int(r["shares"]), "avg_cost": float(r["avg_cost"])}


async def insert_holding(
    conn: Executor,
    portfolio_id: int,
    symbol: str,
    shares: int,
    avg_cost: float,
    purchased_at: date,
) -> None:
    await conn.execute(
        text(
            "INSERT INTO psx_holdings "
            "(portfolio_id, symbol, shares, avg_cost, purchased_at) "
            "VALUES (:pid, :sym, :shares, :cost, :date)"
        ),
        {
            "pid": portfolio_id,
            "sym": symbol.upper(),
            "shares": shares,
            "cost": avg_cost,
            "date": purchased_at,
        },
    )


async def update_holding_position(
    conn: Executor, holding_id: int, shares: int, avg_cost: float, purchased_at: date
) -> None:
    await conn.execute(
        text(
            "UPDATE psx_holdings "
            "SET shares = :shares, avg_cost = :cost, "
            "    purchased_at = LEAST(purchased_at, :date) "
            "WHERE id = :id"
        ),
        {"shares": shares, "cost": avg_cost, "date": purchased_at, "id": holding_id},
    )


async def set_holding_shares(conn: Executor, holding_id: int, shares: int) -> None:
    await conn.execute(
        text("UPDATE psx_holdings SET shares = :s WHERE id = :id"),
        {"s": shares, "id": holding_id},
    )


async def delete_holding_by_id(conn: Executor, holding_id: int) -> None:
    await conn.execute(
        text("DELETE FROM psx_holdings WHERE id = :id"), {"id": holding_id}
    )
