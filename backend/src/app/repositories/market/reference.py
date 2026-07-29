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


# Ranked so an exact ticker always wins: a user saying "MEBL" means the ticker,
# not every company whose name happens to contain those letters. Then
# ticker-prefix, then name-prefix, then name-contains — which is what separates
# "Meezan" -> MEBL/MEHT (two real candidates worth asking about) from a long
# tail of incidental substring hits.
_SYMBOL_SEARCH_SQL = text(
    """
    SELECT symbol, name, sector
    FROM psx_profile
    WHERE upper(symbol) = upper(:q)
       OR upper(symbol) LIKE upper(:prefix)
       OR upper(name)   LIKE upper(:prefix)
       OR upper(name)   LIKE upper(:contains)
    ORDER BY
        CASE
            WHEN upper(symbol) = upper(:q)             THEN 0
            WHEN upper(symbol) LIKE upper(:prefix)     THEN 1
            WHEN upper(name)   LIKE upper(:prefix)     THEN 2
            ELSE 3
        END,
        symbol
    LIMIT :limit
    """
)


async def search_symbols(
    conn: Executor, query: str, limit: int = 5
) -> list[dict[str, Any]]:
    """PSX ticker candidates for a company name or partial ticker.

    Exists for the assistant's resolve_symbol tool: a spoken "add Meezan to my
    watchlist" must not be guessed into a ticker, because MEBL (Meezan Bank) and
    MEHT (Meezan Hotels) are both real and only the user knows which they meant.
    Returning ranked candidates lets the agent ask instead.
    """
    term = (query or "").strip()
    if not term:
        return []
    result = await conn.execute(
        _SYMBOL_SEARCH_SQL,
        {"q": term, "prefix": f"{term}%", "contains": f"%{term}%", "limit": limit},
    )
    return [
        {"symbol": r["symbol"], "name": r["name"], "sector": r["sector"]}
        for r in result.mappings().all()
    ]
