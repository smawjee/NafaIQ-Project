"""TradingView sector heatmap + SQLAlchemy Core sector averages."""
from __future__ import annotations

from typing import Any

from app.repositories import market as repo
from app.repositories.base import connect
from app.services.market._base import TTL_SECTOR_AVG
from app.services.memcache import mem_cache


async def heatmap() -> dict[str, Any]:
    """TradingView-backed sector heatmap plus top movers.

    TradingView is the best live breadth source for sector rotation and
    relative performance; DPS stays the source for fundamentals/history.
    """
    from app.scrapers.tradingview import get_scanner

    rows = await get_scanner().scan(
        columns=["name", "close", "change", "change_abs", "volume", "sector", "market_cap_basic"],
        sort_by="volume",
        sort_dir="desc",
        limit=500,
    )
    sectors_agg: dict[str, dict[str, float]] = {}
    stocks: list[dict[str, Any]] = []
    for row in rows:
        d = row.get("d", []) if isinstance(row, dict) else []
        if not d or len(d) < 7:
            continue
        symbol = (row.get("s") or "").replace("PSX:", "").upper()
        if not symbol:
            continue
        sector = d[5] or "Other"
        try:
            change_pct = float(d[2] or 0)
            volume = float(d[4] or 0)
            close = float(d[1] or 0)
        except (TypeError, ValueError):
            continue
        stocks.append(
            {
                "symbol": symbol,
                "name": d[0] or symbol,
                "sector": sector,
                "close": close,
                "change_pct": change_pct,
                "volume": volume,
                "market_cap": d[6],
            }
        )
        bucket = sectors_agg.setdefault(sector, {"sum_pct": 0.0, "sum_vol": 0.0, "count": 0.0})
        bucket["sum_pct"] += change_pct
        bucket["sum_vol"] += volume
        bucket["count"] += 1

    sector_rows = [
        {
            "name": name,
            "pct": round(data["sum_pct"] / data["count"], 2) if data["count"] else 0.0,
            "volume": int(data["sum_vol"]),
        }
        for name, data in sorted(
            sectors_agg.items(),
            key=lambda item: item[1]["sum_pct"] / item[1]["count"] if item[1]["count"] else 0,
            reverse=True,
        )
    ]
    top_stocks = sorted(stocks, key=lambda s: abs(s["change_pct"]), reverse=True)[:24]
    return {
        "source": "tradingview",
        "sectors": sector_rows,
        "stocks": top_stocks,
        "count": len(stocks),
    }


async def sector_averages() -> list[dict[str, Any]]:
    """Per-sector average % change via SQLAlchemy Core (join+aggregation)."""

    async def load() -> list[dict[str, Any]]:
        async with connect() as conn:
            return await repo.sector_averages(conn)

    return await mem_cache.get_or_load("sector_averages", TTL_SECTOR_AVG, load)
