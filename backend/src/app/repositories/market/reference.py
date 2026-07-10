"""Symbol existence checks over the PSX reference tables."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

Executor = Any

_SYMBOL_EXISTS_SQL = text(
    """
    SELECT
        EXISTS(SELECT 1 FROM psx_profile          WHERE symbol = :s)
     OR EXISTS(SELECT 1 FROM psx_market_snapshot   WHERE symbol = :s)
     OR EXISTS(SELECT 1 FROM psx_ohlcv             WHERE symbol = :s)
    """
)


async def symbol_is_known(conn: Executor, symbol: str) -> bool:
    """True if the (upper-cased) symbol exists in any PSX reference source
    (company profile, live snapshot, or historical OHLCV)."""
    result = await conn.execute(_SYMBOL_EXISTS_SQL, {"s": symbol.upper()})
    return bool(result.scalar())
