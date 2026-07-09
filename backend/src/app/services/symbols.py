"""Symbol validation against the known PSX universe.

A symbol is considered valid if it appears in any of our reference sources:
the company profile table, the live market snapshot, or historical OHLCV.
Used to reject holdings/transactions for non-existent tickers (e.g. "DF").
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import text

_EXISTS_SQL = text(
    """
    SELECT
        EXISTS(SELECT 1 FROM psx_profile          WHERE symbol = :s)
     OR EXISTS(SELECT 1 FROM psx_market_snapshot   WHERE symbol = :s)
     OR EXISTS(SELECT 1 FROM psx_ohlcv             WHERE symbol = :s)
    """
)


async def symbol_is_known(conn: Any, symbol: str) -> bool:
    """Return True if the (upper-cased) symbol exists in any PSX reference source."""
    result = await conn.execute(_EXISTS_SQL, {"s": symbol.upper()})
    return bool(result.scalar())


async def require_known_symbol(conn: Any, symbol: str) -> None:
    """Raise 400 if the symbol is not a recognised PSX ticker."""
    if not await symbol_is_known(conn, symbol):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown PSX symbol '{symbol.upper()}'. Enter a valid listed ticker.",
        )
