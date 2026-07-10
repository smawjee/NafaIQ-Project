from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import structlog

from app.scrapers.dps import DPSScraper
from app.scrapers.ahletrade import AhleTradePoller
from app.scrapers.tradingview import TradingViewScraper
from app.services.cache import CacheLayer
from app.api.health import set_market_refresh_time
from app.db.supabase import async_execute

log = structlog.get_logger()

scheduler = AsyncIOScheduler()
ahletrade = AhleTradePoller()
dps = DPSScraper()
tv = TradingViewScraper()
_cache: CacheLayer | None = None


def get_cache() -> CacheLayer:
    global _cache
    if _cache is None:
        _cache = CacheLayer(dps)
    return _cache

PTK_TZ = timezone(timedelta(hours=5))


async def _is_market_open() -> bool:
    now = datetime.now(PTK_TZ)
    return now.weekday() < 5 and 570 <= now.hour * 60 + now.minute <= 930


# ----- jobs -----

async def job_refresh_market():
    if not await _is_market_open():
        return
    try:
        log.info("job:refresh_market:start")
        items = await dps.fetch_market_watch()
        if not items:
            return
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            {
                "symbol": item.symbol,
                "price": item.price,
                "change": item.change,
                "change_pct": item.change_pct,
                "volume": item.volume,
                "day_high": item.day_high,
                "day_low": item.day_low,
                "refreshed_at": now,
            }
            for item in items
        ]
        await async_execute(lambda c: c.table("psx_market_snapshot").upsert(rows, on_conflict="symbol"))
        set_market_refresh_time()
        log.info("job:refresh_market:done", symbols=len(items))
    except Exception:
        log.exception("job:refresh_market:failed")


async def job_refresh_announcements():
    try:
        log.info("job:refresh_announcements:start")
        items = await dps.fetch_announcements(offset=0, count=50)
        if not items:
            return
        rows = [
            {
                "id": item.id,
                "symbol": item.symbol,
                "posted_at": item.posted_at.isoformat() if item.posted_at else None,
                "title": item.title,
                "category": item.category,
                "url": item.url,
                "refreshed_at": datetime.now(timezone.utc).isoformat(),
            }
            for item in items
        ]
        await async_execute(lambda c: c.table("psx_announcements").upsert(rows, on_conflict="id"))
        log.info("job:refresh_announcements:done", count=len(items))
    except Exception:
        log.exception("job:refresh_announcements:failed")


async def job_poll_ahletrade():
    """Polls AhleTrade for real-time trades and writes to psx_market_snapshot."""
    if not await _is_market_open():
        return
    try:
        symbols = await async_execute(lambda c: c.table("psx_profile").select("symbol"))
        sym_list = [r["symbol"] for r in (symbols.data or [])]

        # Poll top 20 by volume (avoid hammering AhleTrade with 500 symbols)
        snapshot = await async_execute(lambda c: c.table("psx_market_snapshot").select("symbol,volume").order("volume", desc=True).limit(20))
        top_symbols = [r["symbol"] for r in (snapshot.data or [])] or sym_list[:20]

        now = datetime.now(timezone.utc).isoformat()
        rows_to_write = []

        for sym in top_symbols:
            try:
                trades = await ahletrade.fetch_trades(sym)
                if trades:
                    last = trades[-1]
                    rows_to_write.append({
                        "symbol": sym,
                        "price": last["price"],
                        "volume": last.get("volume", 0),
                        "refreshed_at": now,
                    })
                    await asyncio.sleep(0.05)
            except Exception:
                log.debug("ahletrade_poll_symbol_failed", symbol=sym)

        if rows_to_write:
            await async_execute(lambda c: c.table("psx_market_snapshot").upsert(rows_to_write, on_conflict="symbol"))
            log.debug("job:poll_ahletrade:done", patched=len(rows_to_write))
    except Exception:
        log.exception("job:poll_ahletrade:failed")


async def _run_concurrently(
    symbols: list[str],
    worker: "Callable[[str], Awaitable[None]]",
    max_concurrent: int = 5,
) -> None:
    sem = asyncio.Semaphore(max_concurrent)

    async def wrapped(sym: str) -> None:
        async with sem:
            await worker(sym)

    await asyncio.gather(*[wrapped(sym) for sym in symbols], return_exceptions=True)


async def job_backfill_history():
    log.info("job:backfill_history:start")
    result = await async_execute(lambda c: c.table("psx_profile").select("symbol"))
    symbols = [r["symbol"] for r in (result.data or [])]
    if not symbols:
        return

    async def _backfill(sym: str) -> None:
        try:
            bars = await dps.fetch_historical(sym)
            if bars:
                rows = [b.to_dict() for b in bars]
                await async_execute(lambda c: c.table("psx_ohlcv").upsert(rows, on_conflict="symbol,date"))
            log.info("job:backfill_history:symbol_done", symbol=sym, bars=len(bars))
        except Exception:
            log.exception("job:backfill_history:failed", symbol=sym)

    await _run_concurrently(symbols, _backfill, max_concurrent=5)
    log.info("job:backfill_history:done")


async def job_refresh_fundamentals():
    log.info("job:refresh_fundamentals:start")
    result = await async_execute(lambda c: c.table("psx_profile").select("symbol"))
    symbols = [r["symbol"] for r in (result.data or [])]
    if not symbols:
        return
    now = datetime.now(timezone.utc).isoformat()

    async def _refresh(sym: str) -> None:
        try:
            f = await dps.fetch_fundamentals(sym)
            profile = await dps.fetch_profile(sym)
            await async_execute(lambda c: c.table("psx_fundamentals").upsert({
                "symbol": sym,
                "eps": f.eps,
                "pe": f.pe,
                "pb": f.pb,
                "div_yield": f.div_yield,
                "payout": f.payout,
                "roe": f.roe,
                "refreshed_at": now,
            }, on_conflict="symbol"))
            await async_execute(lambda c: c.table("psx_profile").upsert({
                "symbol": sym,
                "name": profile.name,
                "sector": profile.sector,
                "listed_shares": profile.listed_shares,
                "free_float": profile.free_float,
                "refreshed_at": now,
            }, on_conflict="symbol"))
        except Exception:
            log.exception("job:refresh_fundamentals:failed", symbol=sym)

    await _run_concurrently(symbols, _refresh, max_concurrent=5)
    log.info("job:refresh_fundamentals:done")


async def job_refresh_index_eod():
    log.info("job:refresh_index_eod:start")
    for code in ("KSE100", "KSE30", "KMI30", "ALLSHR"):
        try:
            bars = await dps.fetch_index_eod(code)
            if bars:
                rows = [
                    {
                        "code": b.code,
                        "date": b.date.isoformat(),
                        "open": b.open or 0,
                        "high": b.high or 0,
                        "low": b.low or 0,
                        "close": b.close,
                        "volume": b.volume,
                    }
                    for b in bars
                ]
                await async_execute(lambda c: c.table("psx_index_eod").upsert(rows, on_conflict="code,date"))
        except Exception:
            log.exception("job:refresh_index_eod:failed", code=code)
    log.info("job:refresh_index_eod:done")


async def job_refresh_tv_data():
    """Fetch TradingView scanner data for sectors — primary source for all stocks."""
    log.info("job:refresh_tv_data:start")
    try:
        items = await tv.fetch_market_data()
        if not items:
            return
        now = datetime.now(timezone.utc).isoformat()

        profile_rows = []
        for item in items:
            profile_rows.append({
                "symbol": item["symbol"],
                "name": item.get("name", item["symbol"]),
                "sector": item.get("sector"),
                "logoid": item.get("logoid"),
                "refreshed_at": now,
            })

        if profile_rows:
            await async_execute(lambda c: c.table("psx_profile").upsert(profile_rows, on_conflict="symbol"))

        log.info("job:refresh_tv_data:done", symbols=len(items))
    except Exception:
        log.exception("job:refresh_tv_data:failed")


async def job_check_alerts():
    """Evaluate ALL user alerts (stock price, bill, budget, goal) on a schedule.

    Delegates to the full evaluator so a trigger records an alert_event and
    delivers a notification. The previous inline version only flipped the
    alert's `enabled` flag off and notified nobody.
    """
    try:
        from app.services.alerts import evaluate_all

        result = await evaluate_all()
        if any(result.values()):
            log.info("job:check_alerts:done", **result)
    except Exception:
        log.exception("job:check_alerts:failed")


# ----- init -----

def init_scheduler():
    scheduler.add_job(job_refresh_market, IntervalTrigger(seconds=5), id="refresh_market", replace_existing=True)
    scheduler.add_job(job_refresh_announcements, IntervalTrigger(minutes=15), id="refresh_announcements", replace_existing=True)
    scheduler.add_job(job_poll_ahletrade, IntervalTrigger(seconds=5), id="poll_ahletrade", replace_existing=True)
    scheduler.add_job(job_backfill_history, CronTrigger(hour=2, minute=0), id="backfill_history", replace_existing=True)
    scheduler.add_job(job_refresh_fundamentals, CronTrigger(day_of_week=6, hour=4, minute=0), id="refresh_fundamentals", replace_existing=True)
    scheduler.add_job(job_refresh_index_eod, CronTrigger(hour=1, minute=0), id="refresh_index_eod", replace_existing=True)
    scheduler.add_job(job_check_alerts, IntervalTrigger(seconds=60), id="check_alerts", replace_existing=True)
    scheduler.add_job(job_refresh_tv_data, IntervalTrigger(minutes=5), id="refresh_tv_data", replace_existing=True)
    scheduler.start()
    log.info("scheduler:started")


def shutdown_scheduler():
    scheduler.shutdown(wait=False)
    log.info("scheduler:shutdown")
