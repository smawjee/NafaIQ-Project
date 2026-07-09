"""Market data access: SQLAlchemy Core aggregations over the reflected PSX
tables. Only the market queries that hit our own DB live here; live external
sources (DPS cache, TradingView scanner) are orchestrated in the service.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text

from app.db.orm import get_table
from app.db.sqlalchemy import ensure_reflected

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


async def sector_averages(conn: Executor) -> list[dict[str, Any]]:
    """Per-sector average % change: psx_market_snapshot joined with psx_profile."""
    await ensure_reflected()
    snapshot = get_table("psx_market_snapshot")
    profile_t = get_table("psx_profile")
    stmt = (
        select(
            profile_t.c.sector.label("sector"),
            func.avg(snapshot.c.change_pct).label("avg_change_pct"),
            func.count().label("stock_count"),
            func.sum(snapshot.c.volume).label("total_volume"),
        )
        .select_from(snapshot.join(profile_t, snapshot.c.symbol == profile_t.c.symbol))
        .where(profile_t.c.sector.isnot(None))
        .group_by(profile_t.c.sector)
        .order_by(func.avg(snapshot.c.change_pct).desc())
    )
    rows = (await conn.execute(stmt)).all()
    return [
        {
            "sector": row.sector,
            "avg_change_pct": float(row.avg_change_pct) if row.avg_change_pct is not None else 0.0,
            "stock_count": row.stock_count,
            "total_volume": int(row.total_volume) if row.total_volume is not None else 0,
        }
        for row in rows
    ]


async def market_caps(conn: Executor) -> dict[str, float]:
    """Market cap per symbol = listed_shares * live price, from psx_profile
    joined to psx_market_snapshot. Only symbols with both values present."""
    await ensure_reflected()
    snapshot = get_table("psx_market_snapshot")
    profile_t = get_table("psx_profile")
    stmt = (
        select(
            snapshot.c.symbol,
            snapshot.c.price,
            profile_t.c.listed_shares,
        )
        .select_from(snapshot.join(profile_t, snapshot.c.symbol == profile_t.c.symbol))
        .where(profile_t.c.listed_shares.isnot(None))
        .where(profile_t.c.listed_shares > 0)
        .where(snapshot.c.price.isnot(None))
        .where(snapshot.c.price > 0)
    )
    rows = (await conn.execute(stmt)).all()
    return {r.symbol: float(r.price) * float(r.listed_shares) for r in rows}


async def recent_closes(conn: Executor, days: int = 60) -> dict[str, list[float]]:
    """Recent daily closes per symbol (oldest -> newest) for indicator math."""
    await ensure_reflected()
    stmt = text(
        """
        SELECT symbol, close
        FROM psx_ohlcv
        WHERE date >= CURRENT_DATE - (:days * INTERVAL '1 day')
        ORDER BY symbol, date
        """
    )
    rows = (await conn.execute(stmt, {"days": days})).all()
    out: dict[str, list[float]] = {}
    for r in rows:
        if r.close is None:
            continue
        out.setdefault(r.symbol, []).append(float(r.close))
    return out


async def history_coverage(conn: Executor) -> list[dict[str, Any]]:
    """Days of historical OHLCV data per symbol (verifies the 20-day guarantee)."""
    await ensure_reflected()
    ohlcv = get_table("psx_ohlcv")
    stmt = (
        select(
            ohlcv.c.symbol,
            func.count().label("days_available"),
            func.min(ohlcv.c.date).label("oldest_date"),
            func.max(ohlcv.c.date).label("newest_date"),
        )
        .group_by(ohlcv.c.symbol)
        .order_by(ohlcv.c.symbol)
    )
    rows = (await conn.execute(stmt)).all()
    return [
        {
            "symbol": r.symbol,
            "days_available": r.days_available,
            "oldest_date": str(r.oldest_date) if r.oldest_date else None,
            "newest_date": str(r.newest_date) if r.newest_date else None,
        }
        for r in rows
    ]
