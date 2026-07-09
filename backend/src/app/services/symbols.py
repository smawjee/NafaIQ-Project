"""Symbol validation against the known PSX universe.

A symbol is valid if it appears in any reference source (company profile, live
market snapshot, or historical OHLCV). Used to reject holdings/transactions for
non-existent tickers. The existence query lives in market_repo; this module is
the validation guard (raises the domain 400).
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.repositories import market_repo


async def symbol_is_known(conn: Any, symbol: str) -> bool:
    return await market_repo.symbol_is_known(conn, symbol)


async def require_known_symbol(conn: Any, symbol: str) -> None:
    """Raise 400 if the symbol is not a recognised PSX ticker."""
    if not await symbol_is_known(conn, symbol):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown PSX symbol '{symbol.upper()}'. Enter a valid listed ticker.",
        )
