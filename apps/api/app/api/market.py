from fastapi import APIRouter, HTTPException, Request
from functools import lru_cache
from sqlalchemy import func, select
from app.scrapers.dps import DPSScraper
from app.services.cache import CacheLayer
from app.services.indicators import compute_indicators, bars_to_df
from app.services.screener import screen_symbols
from app.services.backtest import run_backtest
from app.models import ScreenerParams, BacktestParams
from app.db.sqlalchemy import ensure_reflected, get_session_factory
from app.db.orm import get_table
from app.middleware.rate_limit import limiter

router = APIRouter(tags=["market"])


@lru_cache(maxsize=1)
def _get_cache() -> CacheLayer:
    return CacheLayer(DPSScraper())


DEFAULT_INDICATORS = ["rsi14", "sma20", "sma50", "sma200", "macd", "bollinger", "atr14"]


# ---------- snapshot ----------

@router.get("/market/snapshot")
@limiter.limit("60/minute")
async def market_snapshot(request: Request):
    items = await _get_cache().get_market_snapshot()
    return [i.model_dump(mode="json") for i in items]


@router.get("/quote/{symbol}")
@limiter.limit("60/minute")
async def quote(request: Request, symbol: str):
    items = await _get_cache().get_market_snapshot()
    for i in items:
        if i.symbol == symbol.upper():
            return i.model_dump(mode="json")
    raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found in market snapshot")


@router.get("/quote/{symbol}/history")
@limiter.limit("30/minute")
async def history(request: Request, symbol: str, days: int = 250):
    bars = await _get_cache().get_history(symbol, days)
    return [b.model_dump(mode="json") for b in bars]


# ---------- symbols ----------

@router.get("/symbols")
@limiter.limit("30/minute")
async def get_symbols(request: Request):
    items = await _get_cache().get_symbols()
    return [i.model_dump(mode="json") for i in items]


# ---------- fundamentals & profile ----------

@router.get("/fundamentals/{symbol}")
async def fundamentals(symbol: str):
    f = await _get_cache().get_fundamentals(symbol)
    return f.model_dump(mode="json")


@router.get("/profile/{symbol}")
async def profile(symbol: str):
    p = await _get_cache().get_profile(symbol)
    if p is None:
        raise HTTPException(status_code=404, detail=f"Profile for {symbol} not found")
    return p.model_dump(mode="json")


# ---------- announcements ----------

@router.get("/announcements")
async def announcements(symbol: str | None = None, limit: int = 50):
    items = await _get_cache().get_announcements(symbol, limit)
    return [i.model_dump(mode="json") for i in items]


# ---------- dividends ----------

@router.get("/dividends/{symbol}")
async def dividends(symbol: str):
    events = await _get_cache().get_dividends(symbol)
    return [e.model_dump(mode="json") for e in events]


# ---------- index ----------

@router.get("/index/{code}")
async def index_data(code: str):
    bars = await _get_cache().get_index_eod(code)
    return [b.model_dump(mode="json") for b in bars]


# ---------- indicators ----------

@router.post("/indicators/{symbol}")
async def indicators(symbol: str, body: dict | None = None):
    indicator_list = (body or {}).get("indicators", DEFAULT_INDICATORS)
    bars = await _get_cache().get_history(symbol, 250)
    result = compute_indicators(bars, indicator_list)
    return {"symbol": result.symbol, "indicators": result.indicators}


# ---------- screener ----------

@router.post("/screener")
async def screener(params: ScreenerParams):
    cache = _get_cache()
    snapshot = await cache.get_market_snapshot()
    symbols = await cache.get_symbols()

    # Compute indicators for top 50 symbols by volume (expensive, so limit)
    top_symbols = sorted(snapshot, key=lambda x: x.volume or 0, reverse=True)[:50]
    indicators_map = {}
    fundamentals_map = {}
    for item in top_symbols:
        try:
            bars = await cache.get_history(item.symbol, 200)
            indicators_map[item.symbol] = compute_indicators(bars, DEFAULT_INDICATORS)
        except Exception:
            pass
        try:
            f = await cache.get_fundamentals(item.symbol)
            fundamentals_map[item.symbol] = vars(f)
        except Exception:
            pass

    results = screen_symbols(snapshot, symbols, indicators_map, fundamentals_map, params)
    return {"results": [r.model_dump(mode="json") if hasattr(r, 'model_dump') else r for r in results], "count": len(results)}


# ---------- backtest ----------

@router.post("/backtest")
async def backtest(params: BacktestParams):
    cache = _get_cache()
    snapshot = await cache.get_market_snapshot()
    top_symbols = sorted(snapshot, key=lambda x: x.volume or 0, reverse=True)[:50]
    history_map = {}
    for item in top_symbols:
        try:
            history_map[item.symbol] = await cache.get_history(item.symbol, 250)
        except Exception:
            pass

    result = run_backtest(history_map, snapshot, params)
    return result.model_dump(mode="json") if hasattr(result, 'model_dump') else vars(result)


# ---------- sectors ----------

@router.get("/sectors")
@limiter.limit("30/minute")
async def sectors(request: Request):
    items = await _get_cache().get_sectors()
    return [i.model_dump(mode="json") for i in items]


# ---------- sector averages (SQLAlchemy Core example endpoint) ----------
# This endpoint uses SQLAlchemy Core for a typed join+aggregation that would
# be awkward to write in Supabase REST. The data is computed server-side from
# psx_market_snapshot (price/change) joined with psx_profile (sector).

@router.get("/market/sectors/avg")
async def sector_averages():
    """Return per-sector average % change computed via SQLAlchemy Core.

    Demonstrates the hybrid data-access pattern: complex joins done with
    SQLAlchemy Core (typed, composable) while bulk writes stay on Supabase REST.
    """
    await ensure_reflected()
    snapshot = get_table("psx_market_snapshot")
    profile = get_table("psx_profile")

    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(
                profile.c.sector.label("sector"),
                func.avg(snapshot.c.change_pct).label("avg_change_pct"),
                func.count().label("stock_count"),
                func.sum(snapshot.c.volume).label("total_volume"),
            )
            .select_from(
                snapshot.join(profile, snapshot.c.symbol == profile.c.symbol)
            )
            .where(profile.c.sector.isnot(None))
            .group_by(profile.c.sector)
            .order_by(func.avg(snapshot.c.change_pct).desc())
        )
        result = await session.execute(stmt)
        rows = result.all()
        return [
            {
                "sector": row.sector,
                "avg_change_pct": float(row.avg_change_pct) if row.avg_change_pct is not None else 0.0,
                "stock_count": row.stock_count,
                "total_volume": int(row.total_volume) if row.total_volume is not None else 0,
            }
            for row in rows
        ]
