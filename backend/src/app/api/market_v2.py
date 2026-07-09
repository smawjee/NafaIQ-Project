"""Public PSX market endpoints: latest price, sector map, KSE-100 benchmark."""
from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import optional_user
from app.middleware.rate_limit import limiter
from app.services.psx.benchmark import get_kse100_latest, get_kse100_series
from app.scrapers.tradingview import get_scanner
from app.services.psx.prices import get_latest_price
from app.services.psx.sector_map import get_sector, get_sector_map

router = APIRouter(tags=["market-v2"])


@router.get("/market/latest/{symbol}")
@limiter.limit("60/minute")
async def latest(
    request: Request,
    symbol: str,
    _user: Annotated[Optional[dict], Depends(optional_user)] = None,
):
    data = await get_latest_price(symbol, allow_external=True)
    if data is None:
        raise HTTPException(404, f"Symbol {symbol} not found")
    return data


@router.get("/market/sector-map")
@limiter.limit("30/minute")
async def sector_map(
    request: Request,
    force: bool = False,
    _user: Annotated[Optional[dict], Depends(optional_user)] = None,
):
    return await get_sector_map(force=force)


@router.get("/market/heatmap")
@limiter.limit("30/minute")
async def market_heatmap(
    request: Request,
    _user: Annotated[Optional[dict], Depends(optional_user)] = None,
):
    """Return a TradingView-backed sector heatmap plus top movers.

    TradingView is the best live breadth source we have for sector rotation
    and relative performance. We keep DPS for fundamentals/history and use
    this endpoint for the market heatmap UI.
    """
    rows = await get_scanner().scan(
        columns=["name", "close", "change", "change_pct", "volume", "sector", "market_cap_basic"],
        sort_by="volume",
        sort_dir="desc",
        limit=500,
    )
    sectors: dict[str, dict[str, float]] = {}
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
        bucket = sectors.setdefault(sector, {"sum_pct": 0.0, "sum_vol": 0.0, "count": 0.0})
        bucket["sum_pct"] += change_pct
        bucket["sum_vol"] += volume
        bucket["count"] += 1

    sector_rows = [
        {
            "name": name,
            "pct": round(data["sum_pct"] / data["count"], 2) if data["count"] else 0.0,
            "volume": int(data["sum_vol"]),
        }
        for name, data in sorted(sectors.items(), key=lambda item: item[1]["sum_pct"] / item[1]["count"] if item[1]["count"] else 0, reverse=True)
    ]
    top_stocks = sorted(stocks, key=lambda s: abs(s["change_pct"]), reverse=True)[:24]
    return {"source": "tradingview", "sectors": sector_rows, "stocks": top_stocks, "count": len(stocks)}


@router.get("/market/sector/{symbol}")
@limiter.limit("60/minute")
async def sector_for_symbol(
    request: Request,
    symbol: str,
    _user: Annotated[Optional[dict], Depends(optional_user)] = None,
):
    sec = await get_sector(symbol)
    return {"symbol": symbol.upper(), "sector": sec}


@router.get("/market/kse100")
@limiter.limit("30/minute")
async def kse100(
    request: Request,
    days: int = 365,
    _user: Annotated[Optional[dict], Depends(optional_user)] = None,
):
    series = await get_kse100_series(days=days)
    latest = await get_kse100_latest()
    return {"latest": latest, "series": series}
