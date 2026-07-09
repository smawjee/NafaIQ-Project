"""Market data service: cache access, screener/backtest orchestration, and
SQLAlchemy Core aggregations. Keeps app.api.market a thin controller."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import HTTPException

from app.repositories import market_repo as repo
from app.repositories.base import connect
from app.scrapers.dps import DPSScraper
from app.schemas.market import BacktestParams, ScreenerParams
from app.services.backtest import run_backtest
from app.services.cache import CacheLayer
from app.services.indicators import compute_indicators

DEFAULT_INDICATORS = ["rsi14", "sma20", "sma50", "sma200", "macd", "bollinger", "atr14"]


@lru_cache(maxsize=1)
def get_cache() -> CacheLayer:
    return CacheLayer(DPSScraper())


# ---------- passthrough reads (thin cache delegation) ----------


async def market_snapshot() -> list[dict[str, Any]]:
    items = await get_cache().get_market_snapshot()
    return [i.model_dump(mode="json") for i in items]


async def quote(symbol: str) -> dict[str, Any]:
    items = await get_cache().get_market_snapshot()
    for i in items:
        if i.symbol == symbol.upper():
            return i.model_dump(mode="json")
    raise HTTPException(404, f"Symbol {symbol} not found in market snapshot")


async def history(symbol: str, days: int = 250) -> list[dict[str, Any]]:
    bars = await get_cache().get_history(symbol, days)
    return [b.model_dump(mode="json") for b in bars]


async def symbols() -> list[dict[str, Any]]:
    items = await get_cache().get_symbols()
    return [i.model_dump(mode="json") for i in items]


async def fundamentals(symbol: str) -> dict[str, Any]:
    f = await get_cache().get_fundamentals(symbol)
    return f.model_dump(mode="json")


async def profile(symbol: str) -> dict[str, Any]:
    p = await get_cache().get_profile(symbol)
    if p is None:
        raise HTTPException(404, f"Profile for {symbol} not found")
    return p.model_dump(mode="json")


async def announcements(symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    items = await get_cache().get_announcements(symbol, limit)
    return [i.model_dump(mode="json") for i in items]


async def dividends(symbol: str) -> list[dict[str, Any]]:
    events = await get_cache().get_dividends(symbol)
    return [e.model_dump(mode="json") for e in events]


async def index_eod(code: str) -> list[dict[str, Any]]:
    bars = await get_cache().get_index_eod(code)
    return [b.model_dump(mode="json") for b in bars]


async def sectors() -> list[dict[str, Any]]:
    items = await get_cache().get_sectors()
    return [i.model_dump(mode="json") for i in items]


async def indicators(symbol: str, indicator_list: list[str] | None = None) -> dict[str, Any]:
    result = compute_indicators(
        await get_cache().get_history(symbol, 250),
        indicator_list or DEFAULT_INDICATORS,
    )
    return {"symbol": result.symbol, "indicators": result.indicators}


# ---------- screener / backtest orchestration ----------


async def run_screener(params: ScreenerParams) -> dict[str, Any]:
    from app.services.screener import screen_symbols

    cache = get_cache()
    snapshot = await cache.get_market_snapshot()
    symbols_list = await cache.get_symbols()

    # Compute indicators/fundamentals for top 50 symbols by volume (expensive).
    top_symbols = sorted(snapshot, key=lambda x: x.volume or 0, reverse=True)[:50]
    indicators_map: dict[str, Any] = {}
    fundamentals_map: dict[str, Any] = {}
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

    results = screen_symbols(
        snapshot, symbols_list, indicators_map, fundamentals_map, params
    )
    return {
        "results": [
            r.model_dump(mode="json") if hasattr(r, "model_dump") else r
            for r in results
        ],
        "count": len(results),
    }


async def run_backtest_top(params: BacktestParams) -> dict[str, Any]:
    cache = get_cache()
    snapshot = await cache.get_market_snapshot()
    top_symbols = sorted(snapshot, key=lambda x: x.volume or 0, reverse=True)[:50]
    history_map: dict[str, Any] = {}
    for item in top_symbols:
        try:
            history_map[item.symbol] = await cache.get_history(item.symbol, 250)
        except Exception:
            pass

    result = run_backtest(history_map, snapshot, params)
    return result.model_dump(mode="json") if hasattr(result, "model_dump") else vars(result)


# ---------- TradingView heatmap ----------


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


# ---------- SQLAlchemy Core aggregations ----------


async def sector_averages() -> list[dict[str, Any]]:
    """Per-sector average % change via SQLAlchemy Core (join+aggregation)."""
    async with connect() as conn:
        return await repo.sector_averages(conn)


async def history_coverage() -> list[dict[str, Any]]:
    """Days of historical OHLCV data per symbol. Verifies the 20-day guarantee."""
    async with connect() as conn:
        return await repo.history_coverage(conn)
