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
from app.services.indicators import compute_indicators, rsi_from_closes
from app.services.memcache import mem_cache

DEFAULT_INDICATORS = ["rsi14", "sma20", "sma50", "sma200", "macd", "bollinger", "atr14"]

# In-process TTLs for hot reads (seconds). Supabase stays the persistent
# store; these just stop every request from paying a cloud round-trip.
TTL_SNAPSHOT = 5.0
TTL_SYMBOLS = 900.0
TTL_INDEX = 60.0
TTL_SECTORS = 15.0
TTL_HISTORY = 3600.0  # EOD candles — refreshed by the nightly backfill job
TTL_PROFILE = 1800.0
TTL_FUNDAMENTALS = 1800.0
TTL_SECTOR_AVG = 30.0
TTL_SCREENER_METRICS = 120.0

INDEX_CARD_CODES = ["KSE100", "KSE30", "KMI30", "ALLSHR"]


@lru_cache(maxsize=1)
def get_cache() -> CacheLayer:
    return CacheLayer(DPSScraper())


# ---------- passthrough reads (memory TTL -> Supabase -> scrape) ----------


async def _snapshot_rows() -> list[dict[str, Any]]:
    async def load() -> list[dict[str, Any]]:
        items = await get_cache().get_market_snapshot()
        return [i.model_dump(mode="json") for i in items]

    return await mem_cache.get_or_load("market_snapshot", TTL_SNAPSHOT, load)


async def market_snapshot() -> list[dict[str, Any]]:
    return await _snapshot_rows()


async def quote(symbol: str) -> dict[str, Any]:
    sym = symbol.upper()
    # In-memory scan of the cached snapshot — no per-quote network fetch.
    for row in await _snapshot_rows():
        if row["symbol"] == sym:
            return row
    raise HTTPException(404, f"Symbol {symbol} not found in market snapshot")


async def history(symbol: str, days: int = 250) -> list[dict[str, Any]]:
    sym = symbol.upper()

    async def load() -> list[dict[str, Any]]:
        bars = await get_cache().get_history(sym, days)
        return [b.model_dump(mode="json") for b in bars]

    return await mem_cache.get_or_load(f"history:{sym}:{days}", TTL_HISTORY, load)


async def symbols() -> list[dict[str, Any]]:
    async def load() -> list[dict[str, Any]]:
        items = await get_cache().get_symbols()
        return [i.model_dump(mode="json") for i in items]

    return await mem_cache.get_or_load("symbols", TTL_SYMBOLS, load)


async def fundamentals(symbol: str) -> dict[str, Any]:
    sym = symbol.upper()

    async def load() -> dict[str, Any]:
        f = await get_cache().get_fundamentals(sym)
        return f.model_dump(mode="json")

    return await mem_cache.get_or_load(f"fundamentals:{sym}", TTL_FUNDAMENTALS, load)


async def profile(symbol: str) -> dict[str, Any]:
    sym = symbol.upper()

    async def load() -> dict[str, Any] | None:
        p = await get_cache().get_profile(sym)
        return p.model_dump(mode="json") if p is not None else None

    result = await mem_cache.get_or_load(f"profile:{sym}", TTL_PROFILE, load)
    if result is None:
        raise HTTPException(404, f"Profile for {symbol} not found")
    return result


async def announcements(symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    items = await get_cache().get_announcements(symbol, limit)
    return [i.model_dump(mode="json") for i in items]


async def dividends(symbol: str) -> list[dict[str, Any]]:
    events = await get_cache().get_dividends(symbol)
    return [e.model_dump(mode="json") for e in events]


async def index_eod(code: str) -> list[dict[str, Any]]:
    c = code.upper()

    async def load() -> list[dict[str, Any]]:
        bars = await get_cache().get_index_eod(c)
        return [b.model_dump(mode="json") for b in bars]

    return await mem_cache.get_or_load(f"index:{c}", TTL_INDEX, load)


async def index_cards() -> list[dict[str, Any]]:
    """Latest + previous close per benchmark index — one light payload for
    the dashboard cards instead of four full-history downloads."""

    async def load() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for code in INDEX_CARD_CODES:
            bars = await get_cache().get_index_latest(code, bars=2)
            if not bars:
                continue
            latest = bars[0]
            prev = bars[1] if len(bars) > 1 else None
            change = (latest.close - prev.close) if prev else 0.0
            change_pct = (change / prev.close * 100) if prev and prev.close else 0.0
            out.append(
                {
                    "code": code,
                    "date": latest.date.isoformat() if latest.date else None,
                    "close": latest.close,
                    "prev_close": prev.close if prev else None,
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                }
            )
        return out

    return await mem_cache.get_or_load("index_cards", TTL_INDEX, load)


async def sectors() -> list[dict[str, Any]]:
    async def load() -> list[dict[str, Any]]:
        items = await get_cache().get_sectors()
        return [i.model_dump(mode="json") for i in items]

    return await mem_cache.get_or_load("sectors", TTL_SECTORS, load)


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

    async def load() -> list[dict[str, Any]]:
        async with connect() as conn:
            return await repo.sector_averages(conn)

    return await mem_cache.get_or_load("sector_averages", TTL_SECTOR_AVG, load)


async def screener_metrics() -> list[dict[str, Any]]:
    """Per-symbol RSI (from OHLCV history) and market cap (listed shares *
    live price), for the screener/movers tables. Nulls where unavailable —
    callers must render a dash rather than a placeholder number.

    Computed from our own cached DB (one closes query + one market-cap query),
    so it never scrapes on the request path; memoized to keep it cheap.
    """

    async def load() -> list[dict[str, Any]]:
        async with connect() as conn:
            caps = await repo.market_caps(conn)
            closes = await repo.recent_closes(conn, days=60)
        symbols = set(caps) | set(closes)
        out: list[dict[str, Any]] = []
        for sym in symbols:
            out.append(
                {
                    "symbol": sym,
                    "rsi": rsi_from_closes(closes.get(sym, [])),
                    "market_cap": caps.get(sym),
                }
            )
        return out

    return await mem_cache.get_or_load("screener_metrics", TTL_SCREENER_METRICS, load)


async def history_coverage() -> list[dict[str, Any]]:
    """Days of historical OHLCV data per symbol. Verifies the 20-day guarantee."""
    async with connect() as conn:
        return await repo.history_coverage(conn)
