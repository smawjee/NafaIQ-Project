"""Public PSX market endpoints: latest price, sector map, KSE-100 benchmark."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import optional_user
from app.middleware.rate_limit import limiter
from app.services import market as market_service
from app.services.memcache import mem_cache
from app.services.psx.benchmark import get_kse100_latest, get_kse100_series
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
    """Return a TradingView-backed sector heatmap plus top movers."""
    return await market_service.heatmap()


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
    async def load():
        series = await get_kse100_series(days=days)
        latest = await get_kse100_latest()
        return {"latest": latest, "series": series}

    return await mem_cache.get_or_load(f"kse100:{days}", 60.0, load)
