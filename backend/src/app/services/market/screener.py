"""Screener & backtest orchestration + per-symbol screener metrics."""
from __future__ import annotations

from typing import Any

from app.repositories import market as repo
from app.repositories.base import connect
from app.schemas.market import BacktestParams, ScreenerParams
from app.services.backtest import run_backtest
from app.services.indicators import compute_indicators, rsi_from_closes
from app.services.market._base import DEFAULT_INDICATORS, TTL_SCREENER_METRICS, get_cache
from app.services.memcache import mem_cache


async def run_screener(params: ScreenerParams) -> dict[str, Any]:
    from app.services.screener import screen_symbols

    cache = get_cache()
    snapshot = await cache.get_market_snapshot()
    symbols_list = await cache.get_symbols()

    # Compute indicators/fundamentals for top 50 symbols by volume (expensive).
    top_symbols = sorted(snapshot, key=lambda x: x.volume or 0, reverse=True)[:50]
    syms = [item.symbol for item in top_symbols]
    indicators_map: dict[str, Any] = {}
    fundamentals_map: dict[str, Any] = {}

    histories = await cache.get_histories_batch(syms, 200)
    fundamentals = await cache.get_fundamentals_batch(syms)

    for sym in syms:
        bars = histories.get(sym)
        if bars:
            indicators_map[sym] = compute_indicators(bars, DEFAULT_INDICATORS)
        f = fundamentals.get(sym)
        if f:
            fundamentals_map[sym] = vars(f)

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

        # Market cap source of truth: live listed_shares * price from our DB
        # when we have it; otherwise TradingView's market_cap_basic (the only
        # bulk source, since psx_profile.listed_shares is rarely populated).
        tv_caps = await _tradingview_market_caps()

        symbols = set(caps) | set(closes) | set(tv_caps)
        out: list[dict[str, Any]] = []
        for sym in symbols:
            out.append(
                {
                    "symbol": sym,
                    "rsi": rsi_from_closes(closes.get(sym, [])),
                    "market_cap": caps.get(sym) or tv_caps.get(sym),
                }
            )
        return out

    return await mem_cache.get_or_load("screener_metrics", TTL_SCREENER_METRICS, load)


async def _tradingview_market_caps() -> dict[str, float]:
    """Bulk market caps keyed by symbol from the TradingView scanner. Empty on
    any failure so screener_metrics still returns RSI + DB caps."""
    from app.scrapers.tradingview import get_scanner

    try:
        rows = await get_scanner().fetch_market_data()
    except Exception:
        return {}
    out: dict[str, float] = {}
    for row in rows:
        sym = row.get("symbol")
        cap = row.get("market_cap")
        if sym and cap:
            try:
                out[sym.upper()] = float(cap)
            except (TypeError, ValueError):
                continue
    return out
