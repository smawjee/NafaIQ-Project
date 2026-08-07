from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import structlog

from app.config import settings
from app.scrapers.dps import DPSScraper
from app.scrapers.ahletrade import AhleTradePoller
# SECTOR OWNERSHIP (psx_profile.sector)
#   DPS is authoritative. job_refresh_fundamentals writes PSX's own
#   classification ("Commercial Banks", "Cement", "Oil & Gas Exploration
#   Companies") scraped from the official portal — ~35 real sectors.
#   TV_SECTOR_MAP is the FALLBACK only, for symbols DPS has no company page
#   for. It collapses PSX's taxonomy into TradingView's 18 global buckets, so
#   it is lossy: "Process Industries" merges Cement, Chemicals, Paper, Textile.
#   job_refresh_tv_data therefore preserves an existing sector and fills the
#   column only when it is empty. It previously overwrote it every 5 minutes,
#   which is why migration 20260716010000 (DPS-style back-fill) appeared to be
#   a no-op and was disabled.
#   Sector is static metadata; heatmap freshness comes from psx_market_snapshot
#   (refreshed every 5s), not from psx_profile.
#   Repairing drift: the pre-fix overwrites left 42 DPS-classified symbols on TV
#   buckets. `python -m scripts.repair_tv_sector_drift` (dry run by default)
#   re-resolves them from DPS and writes only the sector column. Drift is
#   detected by CASE — DPS is UPPERCASE, every TV value is title case — which
#   also catches sectors TV_SECTOR_MAP has no entry for and passes through raw.
from app.scrapers.tradingview import TV_SECTOR_MAP, TradingViewScraper
from app.scrapers.sbp import SBPScraper
from app.scrapers.mufap import BotChallengeError, MUFAPScraper
from app.scrapers.brecorder import BRecorderScraper
from app.scrapers.pdf_fetcher import PDFFetcher
from app.scrapers.financials_psx import FinancialsPSXScraper
from app.schemas.market import MarketSnapshotItem
from app.services.market.volume_spikes import VolumeSpikeDetector
import os
from app.services.market._base import get_cache, ALL_PSX_INDICES
from app.services.market import intraday as intraday_service
from app.api.health import set_market_refresh_time
from app.db.supabase import async_execute, select_all
from app.repositories import reports_repo
from app.repositories.base import begin
from app.services.ai import engine
from app.services.ai.engine import ReportUnavailable
from app.services.ai.providers import ProviderError
from app.services.ai.specs import REPORT_SPECS

log = structlog.get_logger()

# Fraction of per-symbol failures `job_refresh_dividends` tolerates before it
# reports the run as degraded. A 1077-symbol crawl always loses a few to
# delisted/suspended tickers with no DPS payout page; ~66 (6%) is the observed
# steady state, so 10% flags a real regression without crying wolf nightly.
DIVIDENDS_MAX_FAILURE_RATIO = 0.10

# APScheduler's built-in default is `misfire_grace_time=1` — a job whose trigger
# time is reached while the event loop is busy for even one second is dropped
# silently, not run late. Most daily jobs below pass an explicit grace, but any
# that forgot inherited the 1s default: that is how the 18:00 PKT
# `refresh_index_eod_postclose` run vanished on 2026-08-05 with no error and no
# health row, leaving 17 of 18 index cards showing the previous day's close.
# A floor of 300s here means a missed beat is served late instead of skipped;
# `coalesce` collapses a backlog into a single catch-up run so a stalled loop
# can't stampede on recovery, and `max_instances=1` keeps a slow job from
# overlapping itself. Jobs needing a wider window still override per-job.
scheduler = AsyncIOScheduler(
    job_defaults={
        "misfire_grace_time": 300,
        "coalesce": True,
        "max_instances": 1,
    }
)
ahletrade = AhleTradePoller()
dps = DPSScraper()
tv = TradingViewScraper()
sbp = SBPScraper()
mufap = MUFAPScraper()
brecorder = BRecorderScraper()
pdf_fetcher = PDFFetcher()
financials_psx = FinancialsPSXScraper()
volume_spike_detector = VolumeSpikeDetector()
PTK_TZ = timezone(timedelta(hours=5))

# `ALL_PSX_INDICES` is owned by `app.services.market._base` so it can be
# imported by both the scheduler and the services layer without a cycle
# (the scheduler imports `app.services.ai.*` which transitively reaches back
# into the market services). See _base.ALL_PSX_INDICES for the 18 codes.


async def _is_market_open() -> bool:
    now = datetime.now(PTK_TZ)
    return now.weekday() < 5 and 570 <= now.hour * 60 + now.minute <= 930


async def _record_health(
    source: str,
    success: bool,
    rows_updated: int = 0,
    error: str | None = None,
    *,
    allow_zero_rows: bool = False,
):
    """Upsert a row into psx_data_source_health.

    On success: clears any prior error state so the row reflects the latest
    successful run. On failure: sets last_error/last_error_message and leaves
    last_success untouched.

    A "successful" run that wrote ZERO rows is downgraded to a failure unless the
    caller passes ``allow_zero_rows=True``. Audit 2026-07-22 §7 found four
    sources reporting green while their tables sat empty — sbp_macro, mufap_nav,
    financials_5y and psx_fundamentals all had last_success set and
    rows_updated=0, so nothing surfaced that KIBOR/FX had been broken for weeks.
    Monitoring that cannot distinguish "wrote everything" from "wrote nothing" is
    not monitoring. Pass allow_zero_rows=True only where an empty result is a
    genuine no-op (e.g. a poller with nothing new to fetch).

    Never raises. An observability write must not be able to fail the job it is
    observing: most call sites sit inside an ``except`` block (with no enclosing
    try) or after the job's real work has already succeeded, so propagating here
    would either escape to APScheduler or turn a successful run into a spurious
    "job failed". Failures are logged at error level and swallowed.
    """
    if success and rows_updated == 0 and not allow_zero_rows:
        success = False
        error = error or (
            "run completed but wrote 0 rows — the upstream source returned "
            "nothing usable, or its page format changed"
        )
        log.warning("health:zero_rows_downgraded", source=source)
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "source": source,
        "refreshed_at": now,
        "rows_updated": rows_updated,
    }
    if success:
        payload["last_success"] = now
        payload["last_error"] = None
        payload["last_error_message"] = None
    else:
        payload["last_error"] = now
        payload["last_error_message"] = error
    try:
        await async_execute(lambda c: c.table("psx_data_source_health").upsert(payload, on_conflict="source"))
    except Exception as e:
        log.error("health_record_failed", source=source, error=str(e))


async def _get_all_symbols() -> list[str]:
    """Get all PSX symbols from psx_profile.

    Returns an empty list on failure rather than a hardcoded subset. A 19-symbol
    fallback silently reduced coverage to ~4% of the market while the calling
    job still reported success — callers must treat empty as "cannot run" and
    record an error, not quietly process a stub list.
    """
    try:
        rows = await select_all("psx_profile", "symbol", order_by="symbol")
        symbols = [r["symbol"] for r in rows if r.get("symbol")]
        if symbols:
            return symbols
        log.warning("get_all_symbols_empty")
    except Exception as e:
        log.warning("get_all_symbols_failed", error=str(e))
    return []


# ----- jobs -----

async def _market_watch_tv_fallback() -> list[MarketSnapshotItem]:
    """TradingView scanner as the market-watch source of last resort.

    DPS started dropping the /market-watch connection entirely from Railway's
    egress IP on 2026-08-06 (httpx.RemoteProtocolError — the server closed the
    connection without a single response header), while the DPS homepage and
    the TradingView scanner kept working from the same host. Rather than let
    the whole snapshot freeze on yesterday's close, the job serves the
    scanner's price/change/volume for every symbol.

    The scanner has no day_high/day_low — callers must OMIT those columns when
    writing, so the upsert preserves the last DPS-derived extremes instead of
    NULLing them.
    """
    items = await tv.fetch_market_data()
    out: list[MarketSnapshotItem] = []
    for r in items:
        price = r.get("close")
        if price is None or price <= 0:
            continue
        out.append(
            MarketSnapshotItem(
                symbol=r["symbol"].upper(),
                price=price,
                change=r.get("change_abs"),
                change_pct=r.get("change_pct"),
                volume=int(r.get("volume") or 0),
            )
        )
    return out


async def job_refresh_market():
    if not await _is_market_open():
        return
    try:
        log.info("job:refresh_market:start")
        source = "dps"
        try:
            # Bound the DPS attempt: ResilientHTTP retries 4x with backoff
            # (~22s+) while the worker overruns this 10s trigger and every run
            # logs a full traceback. If the connection is dropped (see
            # _market_watch_tv_fallback), the fallback takes over within the
            # budget instead of stalling the interval.
            items = await asyncio.wait_for(dps.fetch_market_watch(), timeout=12.0)
        except Exception:
            source = "tv"
            items = await _market_watch_tv_fallback()
            log.warning("job:refresh_market:dps_failed_using_tv", symbols=len(items))
        if not items:
            # Both sources came back empty. `tv.fetch_market_data` swallows its
            # own exceptions and returns [], so without this the job returned
            # silently and `psx_data_source_health` kept showing whatever it
            # last recorded. That is how the snapshot sat frozen from
            # 2026-08-06 10:30 UTC through the whole of the next session with
            # nothing in the health table pointing at the market-watch path.
            log.warning("job:refresh_market:no_items", source=source)
            await _record_health(
                "market_snapshot",
                success=False,
                error=f"both DPS and the {source} fallback returned no rows",
            )
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
        if source == "tv":
            # Keep the last DPS-derived session extremes (see helper docstring).
            for r in rows:
                r.pop("day_high", None)
                r.pop("day_low", None)
        await async_execute(lambda c: c.table("psx_market_snapshot").upsert(rows, on_conflict="symbol"))
        set_market_refresh_time()
        log.info("job:refresh_market:done", symbols=len(items), source=source)
        await _record_health("market_snapshot", success=True, rows_updated=len(items))
    except Exception as e:
        log.exception("job:refresh_market:failed")
        await _record_health("market_snapshot", success=False, error=str(e))


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
        await _record_health("psx_announcements", success=True, rows_updated=len(items))
    except Exception as e:
        log.exception("job:refresh_announcements:failed")
        await _record_health("psx_announcements", success=False, error=str(e))


async def job_precompute_cross_section():
    """Daily cross-sectional factor ranks for the liquid universe (cross-sectional analytics)."""
    from app.services.signals.cross_section_job import precompute_cross_section

    try:
        log.info("job:cross_section:start")
        result = await precompute_cross_section()
        log.info("job:cross_section:done", **result)
        await _record_health("psx_signal_cross_section", success=result.get("written", 0) > 0,
                             rows_updated=result.get("written", 0))
    except Exception as e:
        log.exception("job:cross_section:failed")
        await _record_health("psx_signal_cross_section", success=False, error=str(e))


async def job_record_signal_recommendations():
    """Snapshot today's calibrated call for every ranked symbol.

    Must run AFTER job_precompute_cross_section: the reversal percentile the
    recommendation conditions on is produced there, and without it the lookup
    falls back to a coarser cohort.
    """
    from app.services.signals.track_record_job import record_todays_recommendations

    try:
        log.info("job:record_recommendations:start")
        result = await record_todays_recommendations()
        log.info("job:record_recommendations:done", **result)
        await _record_health("psx_signal_recommendations",
                             success=result.get("recorded", 0) > 0,
                             rows_updated=result.get("recorded", 0))
    except Exception as e:
        log.exception("job:record_recommendations:failed")
        await _record_health("psx_signal_recommendations", success=False, error=str(e))


async def job_mature_signal_recommendations():
    """Measure predictions whose horizon has elapsed, then roll them up.

    Writes outcomes once and never revises them — a revisable track record is
    marketing, not measurement. Raw rows are pruned past the retention window;
    the per-bucket rollup is the permanent record.
    """
    from app.services.signals.track_record_job import mature_recommendations

    try:
        log.info("job:mature_recommendations:start")
        result = await mature_recommendations()
        log.info("job:mature_recommendations:done", **result)
        # Zero matured is normal (nothing reached its horizon today), so this
        # must not be judged on row count.
        await _record_health("psx_signal_calibration", success=True,
                             rows_updated=result.get("matured", 0),
                             allow_zero_rows=True)
    except Exception as e:
        log.exception("job:mature_recommendations:failed")
        await _record_health("psx_signal_calibration", success=False, error=str(e))


async def job_ingest_signal_events():
    """Fold psx_announcements + psx_dividends into canonical psx_signal_events.

    Reads the DB only (no external scraping) and upserts on a deterministic
    event id, so it is idempotent and never touches the technical/context
    serving path. Foundation for the (still dormant) event-forecast track.
    """
    from app.services.signals.ingest import ingest_events

    try:
        log.info("job:ingest_signal_events:start")
        result = await ingest_events()
        log.info("job:ingest_signal_events:done", **result)
        await _record_health("psx_signal_events", success=True, rows_updated=result.get("events_written", 0))
    except Exception as e:
        log.exception("job:ingest_signal_events:failed")
        await _record_health("psx_signal_events", success=False, error=str(e))


async def job_poll_ahletrade():
    """Polls AhleTrade for real-time trades and writes to psx_market_snapshot."""
    if not await _is_market_open():
        return
    try:
        # Poll top 20 by volume (avoid hammering AhleTrade with 500 symbols)
        snapshot = await async_execute(lambda c: c.table("psx_market_snapshot").select("symbol,volume").order("volume", desc=True).limit(20))
        top_symbols = [r["symbol"] for r in (snapshot.data or [])]
        if not top_symbols:
            # Cold start only — the snapshot is empty until job_refresh_market
            # has run once. Paging all ~1,076 psx_profile rows costs two
            # round-trips, so pay for it only when it is actually needed: this
            # ran on EVERY 5s tick for a fallback that never fired.
            rows = await select_all("psx_profile", "symbol", order_by="symbol")
            top_symbols = [r["symbol"] for r in rows][:20]

        now = datetime.now(timezone.utc).isoformat()
        rows_to_write = []

        async def _poll(sym: str) -> None:
            try:
                trades = await ahletrade.fetch_trades(sym)
                if not trades:
                    return
                last = trades[-1]
                price = last.get("price")
                # PriceVolume can emit 0.0 for a symbol with no trade yet; a
                # zero would read as a crash in the UI and poison the sector
                # aggregates. Never write it.
                if price is None or price <= 0:
                    return
                # append from concurrent workers is safe: asyncio does not
                # preempt between the await and this line.
                rows_to_write.append({
                    "symbol": sym,
                    "price": price,
                    "refreshed_at": now,
                })
            except Exception:
                log.debug("ahletrade_poll_symbol_failed", symbol=sym)

        # Concurrent, 5 in flight. Sequentially these 20 calls took ~6.6s and
        # could never fit the 5s trigger, so APScheduler skipped 11 of every 15
        # runs. The semaphore is the throttle the old per-call sleep provided.
        await _run_concurrently(top_symbols, _poll, max_concurrent=5)

        if rows_to_write:
            # AHL owns only the live `price` (last trade) plus refreshed_at.
            # `volume` is deliberately NOT written: the PriceVolume feed's
            # volume is per-trade, not day-cumulative, and overwriting the
            # cumulative figure with the last print (previously an ask quote
            # from the misparsed BuySell feed — CNERGY showed volume 11 vs a
            # real 42.2M) corrupts the volume column market-wide. The
            # partial-update RPC never clobbers the DPS-derived
            # change/change_pct/day_high/day_low either.
            await async_execute(
                lambda c: c.rpc("patch_market_snapshot", {"rows": rows_to_write})
            )
            log.debug("job:poll_ahletrade:done", patched=len(rows_to_write))
        await _record_health("ahletrade_live", success=True, rows_updated=len(rows_to_write))
    except Exception as e:
        log.exception("job:poll_ahletrade:failed")
        await _record_health("ahletrade_live", success=False, error=str(e))


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


async def _last_bar_dates() -> dict[str, "date"]:
    """Latest stored bar date per symbol, in one query.

    Drives the incremental upsert and the staleness ordering below.
    """
    from sqlalchemy import text as _sql_text

    from app.repositories.base import connect as _connect

    async with _connect() as conn:
        rows = await conn.execute(
            _sql_text("SELECT symbol, max(date) AS last_date FROM psx_ohlcv GROUP BY symbol")
        )
        return {r["symbol"]: r["last_date"] for r in rows.mappings().all()}


async def job_backfill_history():
    """Refresh daily bars for every symbol.

    Fixed 2026-07-22 after the audit found the back half of the alphabet had no
    bars for over a week — PPL, PSO, POL, PTC, SEARL, SNGP, SSGC, TRG and UBL
    among them, all trading millions of shares a day. Three compounding faults:

    1. WRITE VOLUME. `fetch_historical` returns a symbol's ENTIRE history (~2,400
       bars) and every one was re-upserted nightly: 1,077 symbols x ~2,400 =
       ~2.6M row writes per run. The job could not finish in its window. Now only
       bars NEWER than what we already hold are written, which is a handful per
       symbol on a normal day.

    2. STARVATION. Symbols were always processed in the same alphabetical order,
       so a truncated run starved the exact same tail every single night —
       a permanent blind spot from "PIBTL" onward, not a transient gap. Now the
       STALEST symbols go first, so any backlog is self-healing: whatever was
       missed last night is at the front of the queue tonight.

    3. FALSE GREEN. Health reported success regardless of coverage. It now
       records how many symbols were actually covered and fails when a
       meaningful share were missed.
    """
    total_bars = 0
    covered = 0
    failed: list[str] = []
    try:
        log.info("job:backfill_history:start")
        rows = await select_all("psx_profile", "symbol", order_by="symbol")
        symbols = [r["symbol"] for r in rows]
        if not symbols:
            return

        last_dates = await _last_bar_dates()
        # Stalest first; a symbol we have never seen sorts to the very front.
        symbols.sort(key=lambda s: (last_dates.get(s) or date.min, s))

        async def _backfill(sym: str) -> None:
            nonlocal total_bars, covered
            try:
                bars = await dps.fetch_historical(sym)
                known = last_dates.get(sym)
                if known is not None:
                    # Incremental: only what we do not already store. Re-writing
                    # a decade of unchanged history every night is what starved
                    # the tail of the alphabet.
                    bars = [b for b in bars if b.date > known]
                if bars:
                    payload = [b.to_dict() for b in bars]
                    await async_execute(
                        lambda c, _p=payload: c.table("psx_ohlcv").upsert(
                            _p, on_conflict="symbol,date"
                        )
                    )
                    total_bars += len(bars)
                covered += 1
                log.debug("job:backfill_history:symbol_done", symbol=sym, bars=len(bars))
            except Exception as e:
                failed.append(sym)
                # One symbol failing is routine (upstream drops connections);
                # the traceback is httpx internals and identical every time.
                log.warning("job:backfill_history:failed", symbol=sym, error=str(e))

        await _run_concurrently(symbols, _backfill, max_concurrent=5)

        coverage_pct = round(100.0 * covered / len(symbols), 1) if symbols else 0.0
        log.info(
            "job:backfill_history:done",
            total_bars=total_bars, covered=covered, symbols=len(symbols),
            coverage_pct=coverage_pct, failed=len(failed),
        )
        # Bars written can legitimately be 0 (a holiday, or a re-run the same
        # day), so success is judged on COVERAGE, not row count.
        ok = coverage_pct >= 95.0
        if not ok:
            log.warning(
                "job:backfill_history:incomplete_coverage",
                coverage_pct=coverage_pct, missed=len(failed),
                first_missed=failed[:10],
            )
        await _record_health(
            "backfill_history",
            success=ok,
            rows_updated=total_bars,
            allow_zero_rows=True,
            error=None if ok
            else f"only {covered}/{len(symbols)} symbols covered ({coverage_pct}%); "
                 f"first missed: {', '.join(failed[:5])}",
        )
    except Exception as e:
        log.exception("job:backfill_history:failed")
        await _record_health("backfill_history", success=False, error=str(e))


async def job_refresh_fundamentals():
    total = 0
    try:
        log.info("job:refresh_fundamentals:start")
        rows = await select_all("psx_profile", "symbol", order_by="symbol")
        symbols = [r["symbol"] for r in rows]
        if not symbols:
            return
        now = datetime.now(timezone.utc).isoformat()
        errors: list[str] = []

        async def _refresh(sym: str) -> None:
            nonlocal total
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
                # This job OWNS psx_profile.sector.
                #
                # DPS is the official PSX portal, so quote__sector is the
                # authoritative PSX classification for the symbol ("Commercial
                # Banks", "Oil & Gas Exploration Companies", "Cement", ...).
                # TV_SECTOR_MAP can only approximate it — TradingView has 18
                # global buckets against PSX's ~35, so it is lossy by
                # construction (its "Process Industries" flattens Cement,
                # Chemicals, Paper and Textile into one tile group).
                #
                # Sector is static metadata — a company is reclassified maybe
                # once a year — so this job's weekly cadence is ample. Heatmap
                # freshness comes from psx_market_snapshot (5s), not from here.
                # job_refresh_tv_data now preserves this value instead of
                # overwriting it every 5 minutes.
                profile_row = {
                    "symbol": sym,
                    "name": profile.name,
                    "listed_shares": profile.listed_shares,
                    "free_float": profile.free_float,
                    "refreshed_at": now,
                }
                # Only claim the column when DPS actually returned one — a
                # failed scrape must not blank a good sector.
                if profile.sector:
                    profile_row["sector"] = profile.sector
                await async_execute(
                    lambda c, r=profile_row: c.table("psx_profile").upsert(r, on_conflict="symbol")
                )
                total += 1
            except Exception as e:
                errors.append(f"{sym}: {e}")
                log.warning("job:refresh_fundamentals:failed", symbol=sym, error=str(e))

        await _run_concurrently(symbols, _refresh, max_concurrent=5)
        log.info(
            "job:refresh_fundamentals:done", total=total, errors=len(errors),
            symbols=len(symbols),
        )
        # This used to report success=True even when every symbol failed, so a
        # total DPS outage looked identical to a clean run. listed_shares is the
        # market-cap input, and it silently went stale for weeks.
        await _record_health(
            "psx_fundamentals",
            success=total > 0 and len(errors) < len(symbols),
            rows_updated=total,
            error=None if not errors
            else f"{len(errors)}/{len(symbols)} symbols failed; first: {errors[0][:180]}",
        )
    except Exception as e:
        log.exception("job:refresh_fundamentals:failed")
        await _record_health("psx_fundamentals", success=False, error=str(e))


async def _ingest_index_eod(code: str) -> int:
    """Fetch + upsert one index's EOD history. Returns rows written."""
    bars = await dps.fetch_index_eod(code)
    if not bars:
        return 0
    # Keyed by (code, date), not a list comprehension: DPS returns an exact
    # duplicate bar for 2024-01-22 in 15 of the 18 indices (and 2021-10-29 for
    # BKTI/OGTI), and Postgres rejects the whole batch with 21000 "ON CONFLICT
    # DO UPDATE command cannot affect row a second time" when two proposed rows
    # share the conflict target. One duplicated day cost the index its ENTIRE
    # history: only the three duplicate-free codes ingested, while ALLSHR sat
    # three weeks stale. Last one wins — the duplicates observed are identical
    # bars, so which survives does not matter; failing the code does. Same bug
    # class as job_refresh_dividends (fixed 2026-07-16).
    rows_by_key = {
        (b.code, b.date.isoformat()): {
            "code": b.code,
            "date": b.date.isoformat(),
            "open": b.open or 0,
            "high": b.high or 0,
            "low": b.low or 0,
            "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    }
    rows = list(rows_by_key.values())
    await async_execute(
        lambda c, r=rows: c.table("psx_index_eod").upsert(r, on_conflict="code,date")
    )
    return len(rows)


async def job_refresh_index_eod(attempts: int = 3, backoff_seconds: float = 30.0):
    """Ingest EOD bars for all 18 indices, retrying the ones that fail.

    This job used to run exactly once a day at 01:00 PKT with no retry, so any
    code that failed stayed stale for a FULL 24 hours — and if it failed again
    the next night, indefinitely. That is how ALLSHR drifted three weeks behind
    without anything downstream noticing.

    Retrying failed codes in-run turns a transient DPS hiccup into a delay of
    seconds instead of a day. Codes that already succeeded are never re-fetched.
    """
    total_bars = 0
    pending = list(ALL_PSX_INDICES)
    try:
        log.info("job:refresh_index_eod:start", indices=len(pending))
        for attempt in range(1, attempts + 1):
            failed: list[str] = []
            for code in pending:
                try:
                    total_bars += await _ingest_index_eod(code)
                except Exception as e:
                    failed.append(code)
                    log.warning(
                        "job:refresh_index_eod:code_failed",
                        code=code, attempt=attempt, error=str(e),
                    )
            pending = failed
            if not pending or attempt == attempts:
                break
            log.info("job:refresh_index_eod:retrying", codes=pending, attempt=attempt)
            await asyncio.sleep(backoff_seconds)

        log.info("job:refresh_index_eod:done", total_bars=total_bars, errors=len(pending))
        # A partial run is NOT a success. Counting only the codes that landed and
        # always reporting green is how 15 broken indices looked identical to a
        # clean night for weeks.
        await _record_health(
            "index_eod",
            success=not pending,
            rows_updated=total_bars,
            error=None if not pending else
            f"{len(pending)}/{len(ALL_PSX_INDICES)} indices failed after {attempts} attempts: {', '.join(pending)}",
        )
    except Exception as e:
        log.exception("job:refresh_index_eod:failed")
        await _record_health("index_eod", success=False, error=str(e))


async def job_refresh_index_snapshot():
    """Scrape DPS homepage for live index values every 5 min during market hours.

    Writes to ``psx_index_live_snapshot`` so the web API can serve live
    intraday index data for all 18 benchmark indices without scraping DPS on
    the request path (which silently failed on Railway, causing stale
    yesterday-EOD fallback).

    The old live-scrape path on the web request had two problems:
      1. The DPS homepage (~95KB) often timed out from Railway infrastructure.
      2. The exception was caught silently by ``_live_index_by_code()``, which
         returned ``{}``, causing ``index_cards()`` to fall back to the
         ``psx_index_eod`` table — last written at 01:00 AM PKT.

    With this job, the scheduler writes fresh intraday data to the DB, and the
    web API reads it without ever touching DPS directly.
    """
    log.info("job:refresh_index_snapshot:start")
    try:
        rows = await dps.fetch_index_snapshot()
        if rows:
            now = datetime.now(timezone.utc).isoformat()
            for r in rows:
                r["updated_at"] = now
            await async_execute(
                lambda c: c.table("psx_index_live_snapshot").upsert(rows, on_conflict="code")
            )
            await _record_health("index_snapshot", success=True, rows_updated=len(rows))
        else:
            await _record_health("index_snapshot", success=False, error="DPS homepage returned no index rows")
        log.info("job:refresh_index_snapshot:done", count=len(rows) if rows else 0)
    except Exception as e:
        log.exception("job:refresh_index_snapshot:failed")
        await _record_health("index_snapshot", success=False, error=str(e))


async def job_capture_intraday():
    """Write 5-minute bars into ``psx_intraday``.

    ``psx_market_snapshot`` is upsert-on-symbol — every refresh overwrites the
    previous tick — so before this job existed no intraday series was retained
    anywhere and the chart's "1D" timeframe had nothing but daily bars to draw.

    The AhleTrade tape is the primary source. It carries every print, so a bar's
    O/H/L/C are exact and its volume is a sum; the snapshot sampler could only
    see ~5 prices per bucket and had to reverse out volume from a day-cumulative
    counter it could not verify. The tape also stays correct while DPS is
    unreachable, which on 2026-08-07 left the snapshot frozen from the previous
    session's close and every candle drawing as a flat full-range hairline.

    Snapshot sampling remains the fallback: it needs no per-symbol requests, so
    it still produces something if the tape is down. Both paths write the same
    bucket key, so a re-run of the same minute is idempotent either way.
    """
    if not await _is_market_open():
        return
    try:
        symbols = await _intraday_symbols()
        written = 0
        source = "tape"
        if symbols:
            written = await intraday_service.capture_from_trades(
                ahletrade.fetch_trades, symbols
            )
        if written == 0:
            # Nothing from the tape: either every fetch failed or the market is
            # genuinely quiet. The sampler cannot tell those apart either, but
            # it costs one already-cached read, so prefer a bar to no bar.
            source = "snapshot"
            written = await intraday_service.capture_snapshot()
        log.info("job:capture_intraday:done", rows=written, source=source)
        await _record_health("psx_intraday", success=True, rows_updated=written)
    except Exception as e:
        log.exception("job:capture_intraday:failed")
        await _record_health("psx_intraday", success=False, error=str(e))


async def _intraday_symbols() -> list[str]:
    """Symbols to pull tapes for. Empty list falls the caller back to sampling."""
    try:
        res = await async_execute(
            lambda c: c.table("psx_market_snapshot").select("symbol").order("symbol")
        )
        return [r["symbol"] for r in (res.data or []) if r.get("symbol")]
    except Exception:
        log.warning("job:capture_intraday:symbol_list_failed", exc_info=True)
        return []


async def job_prune_intraday():
    """Drop intraday bars past the retention window.

    ~500 symbols x 78 buckets is ~39k rows per session, and the table backs a
    chart window rather than an archive (``psx_ohlcv`` is the historical
    record), so without this it only ever grows.
    """
    try:
        await intraday_service.prune()
        log.info("job:prune_intraday:done")
        # A prune that deleted nothing is the healthy steady state once the
        # window is shorter than the retention period.
        await _record_health("psx_intraday_prune", success=True, allow_zero_rows=True)
    except Exception as e:
        log.exception("job:prune_intraday:failed")
        await _record_health("psx_intraday_prune", success=False, error=str(e))


async def job_refresh_tv_data():
    """Fetch TradingView scanner data for sectors — primary source for all stocks."""
    log.info("job:refresh_tv_data:start")
    try:
        items = await tv.fetch_market_data()
        if not items:
            return
        now = datetime.now(timezone.utc).isoformat()

        # psx_profile.is_shariah is NOT written here — job_refresh_shariah owns
        # it, sourced from the live KMIALLSHR constituents. This job used to
        # derive it from a hardcoded config set on every 5-min refresh.
        # Pre-load existing listed_shares/free_float so the TV job doesn't
        # nullify them (the TV scanner has no shares-outstanding column), and
        # existing sector so it doesn't overwrite DPS's authoritative value.
        # This read MUST page and MUST NOT be swallowed. psx_profile is past
        # PostgREST's ~1000-row cap, and every symbol missing from this map
        # resolves to the TV bucket below and is upserted over DPS's value —
        # so a truncated or empty map silently clobbers the sector column
        # market-wide. Let a failure propagate to the handler, which records
        # the job unhealthy instead of reporting a green clobber.
        existing_rows = await select_all(
            "psx_profile", "symbol,listed_shares,free_float,sector", order_by="symbol"
        )
        existing_by_sym: dict[str, dict] = {
            r["symbol"].upper(): r for r in existing_rows if r.get("symbol")
        }

        profile_rows = []
        for item in items:
            sym = item["symbol"].upper()

            existing = existing_by_sym.get(sym, {})
            listed_shares = existing.get("listed_shares")
            free_float = existing.get("free_float")

            # Sector: DPS (job_refresh_fundamentals) is authoritative — it is
            # PSX's own classification. TV is only the FALLBACK, used when no
            # sector exists yet (a symbol DPS has no company page for). This
            # job used to overwrite the column every 5 minutes, which silently
            # replaced ~35 real PSX sectors with 18 generic TradingView buckets
            # and made the apply_sector_map back-fill look like a no-op.
            tv_sector = item.get("sector") or ""
            sector = existing.get("sector") or TV_SECTOR_MAP.get(tv_sector, tv_sector or None)

            row = {
                "symbol": sym,
                "name": item.get("name", item["symbol"]),
                "logoid": item.get("logoid"),
                "refreshed_at": now,
            }
            if sector:
                row["sector"] = sector
            if listed_shares is not None:
                row["listed_shares"] = listed_shares
            if free_float is not None:
                row["free_float"] = free_float
            profile_rows.append(row)

        if profile_rows:
            await async_execute(lambda c: c.table("psx_profile").upsert(profile_rows, on_conflict="symbol"))

        log.info("job:refresh_tv_data:done", symbols=len(items))
        await _record_health("tradingview", success=True, rows_updated=len(items))
    except Exception as e:
        log.exception("job:refresh_tv_data:failed")
        await _record_health("tradingview", success=False, error=str(e))


async def job_purge_error_events():
    """Age out captured error events past the retention window.

    Only the individual occurrences are deleted; app_error_groups keeps its
    counters and triage state, so a long-running bug's history isn't lost when
    its oldest samples expire.
    """
    from app.services import telemetry

    try:
        deleted = await telemetry.purge_expired()
        log.info("job:purge_error_events:done", deleted=deleted)
        await _record_health("error_retention", success=True, rows_updated=deleted,
                             allow_zero_rows=True)
    except Exception as e:
        log.exception("job:purge_error_events:failed")
        await _record_health("error_retention", success=False, error=str(e))


async def job_refresh_fipi():
    """Daily FIPI/LIPI investor-flow ingestion (NCCPL data via finhisaab mirror)."""
    from datetime import date, timedelta

    from app.repositories.market import fipi_repo
    from app.scrapers.fipi import fetch_day

    try:
        total = 0
        today = date.today()
        for d in (today - timedelta(days=1), today):
            if d.weekday() >= 5:
                continue
            rows = await fetch_day(d.isoformat())
            if rows:
                total += await fipi_repo.upsert_fipi_rows(rows)
        await _record_health("fipi_daily", success=True, rows_updated=total)
    except Exception as e:
        log.warning("job_refresh_fipi_failed", exc_info=True)
        await _record_health("fipi_daily", success=False, error=str(e))


async def job_refresh_shariah():
    """Refresh psx_profile.is_shariah from the live KMI All-Share constituents.

    KMIALLSHR is PSX's own Shariah-screened index, so it is authoritative. The
    flag was previously derived from a hardcoded 124-symbol set in config that
    marked conventional interest-based banks (HBL, UBL, NBP, ...) compliant.

    Cadence is daily because index membership is reviewed periodically, not
    intraday — it does not belong in the 5-minute TV job that used to own it.
    """
    try:
        log.info("job:refresh_shariah:start")
        members = await dps.fetch_index_constituents("KMIALLSHR")
        # is_shariah is NOT NULL DEFAULT false and this job writes `false` for
        # every non-member, so a failed or partial scrape would silently mark
        # the ENTIRE market non-Shariah — worse than stale data in a
        # Muslim-audience app. A per-field `if value:` guard cannot catch this.
        # The real index is ~310 members; anything near-empty is a broken
        # scrape, so leave the last-known-good flags untouched.
        if len(members) < 200:
            await _record_health(
                "shariah_universe",
                success=False,
                error=f"suspiciously small constituent set: {len(members)}",
            )
            return

        symbols = await _get_all_symbols()
        if not symbols:
            await _record_health(
                "shariah_universe", success=False, error="no symbols available"
            )
            return

        member_set = set(members)
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            {"symbol": sym, "is_shariah": sym in member_set, "refreshed_at": now}
            for sym in symbols
        ]
        await async_execute(
            lambda c: c.table("psx_profile").upsert(rows, on_conflict="symbol")
        )
        log.info("job:refresh_shariah:done", members=len(members), symbols=len(symbols))
        await _record_health("shariah_universe", success=True, rows_updated=len(rows))
    except Exception as e:
        log.exception("job:refresh_shariah:failed")
        await _record_health("shariah_universe", success=False, error=str(e))


async def job_poll_inboxes():
    """Poll every connected mailbox for new bank transaction alerts.

    Deliberately NOT market-gated — bank alerts arrive 24/7. Per-user failures
    are recorded on the integration row inside the pipeline, so one bad mailbox
    never stops the rest.
    """
    if not settings.email_import_configured:
        return
    try:
        from app.services.email_import import sync_all

        result = await sync_all()
        if result.get("imported") or result.get("scanned"):
            log.info("job:poll_inboxes:done", **result)
        # allow_zero_rows: a poll that finds no new bank mail is the NORMAL
        # outcome, not a failure.
        await _record_health(
            "email_import",
            success=True,
            rows_updated=int(result.get("imported") or 0),
            allow_zero_rows=True,
        )
    except Exception as e:
        log.exception("job:poll_inboxes:failed")
        await _record_health("email_import", success=False, error=str(e))


async def job_keepalive():
    """Ping the public API's health endpoint to keep the web service warm.

    Railway cold-starts an idle service, and this app's boot cost (numpy/pandas
    import + DB schema reflection) makes that first request slow. This runs on
    the always-on worker, so a brief user gap never leaves the API cold. No-op
    unless API_KEEPALIVE_URL is set.
    """
    url = settings.api_keepalive_url.strip()
    if not url:
        return
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.get(f"{url.rstrip('/')}/api/health")
        # Doubles as the WORKER'S OWN heartbeat. Every other source in
        # psx_data_source_health reports on an upstream; this one reports that
        # the process running all of them is still alive. Without it, a worker
        # that dies outside market hours looks identical to a quiet market —
        # every market-gated source simply stops updating, which is also what
        # a healthy weekend looks like.
        await _record_health("worker_heartbeat", success=True, allow_zero_rows=True)
    except Exception as e:
        # A missed ping is harmless — the next tick tries again — but it is still
        # recorded, because a SUSTAINED gap is the signal worth having.
        log.debug("keepalive_ping_failed", exc_info=True)
        await _record_health("worker_heartbeat", success=False, error=str(e))


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
        # Alerts are a whole product pillar and were, until now, the ONLY
        # unobserved thing in this file: every failure went to a log line that
        # nothing reads, so a permanently-throwing evaluator would have looked
        # exactly like a quiet market. allow_zero_rows because a tick where
        # nothing crossed a threshold is the normal case, not a failure.
        await _record_health(
            "alerts_evaluator",
            success=True,
            rows_updated=sum(v for v in result.values() if isinstance(v, int)),
            allow_zero_rows=True,
        )
    except Exception as e:
        log.exception("job:check_alerts:failed")
        await _record_health("alerts_evaluator", success=False, error=str(e))


def _context_hash(bundle: dict) -> str:
    """sha256 of the assembled bundle — the report's cache/provenance key."""
    return hashlib.sha256(
        json.dumps(bundle, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


async def job_generate_market_brief(replace: bool = False):
    """Generate the once-per-trading-day SHARED Market Brief and persist it (§11).

    Runs twice a day. The morning run gives users a brief to read during the
    session; the post-close run passes ``replace=True`` so the day ends with a
    brief that describes the COMPLETED session rather than a partial-day move.
    Without the second run the brief is frozen at whatever the tape looked like
    mid-morning — on 2026-08-06 the stored brief said the index "climbed 725.79
    points ... to close at 180740.72" when it actually closed at 181776.59,
    +1761.66.

    A failed brief must NEVER crash the scheduler, so every failure mode
    (fail-closed `ReportUnavailable`, `ProviderError`, or anything else) is
    logged and swallowed — mirroring `job_check_alerts`.
    """
    try:
        log.info("job:generate_market_brief:start", replace=replace)
        gen = await engine.generate_report(REPORT_SPECS["market_brief"], lang="en")
        # A `date`, NOT `.isoformat()`. asyncpg binds this straight to the
        # trading_date DATE column and raises "'str' object has no attribute
        # 'toordinal'" on a string — which is why this job threw on every run
        # since it was written and psx_data_source_health.market_brief carried
        # last_success = NULL while the LLM cost was paid each time.
        trading_date = datetime.now(PTK_TZ).date()
        async with begin() as conn:
            await reports_repo.get_or_create_shared(
                conn,
                report_type="market_brief",
                subject=None,
                trading_date=trading_date,
                content=gen.report.model_dump(),
                context_hash=_context_hash(gen.bundle),
                verified=gen.verification.verified,
                provider=gen.provider,
                model=gen.model,
                replace=replace,
            )
        log.info(
            "job:generate_market_brief:done",
            trading_date=trading_date.isoformat(),
            verified=gen.verification.verified,
            replace=replace,
        )
        await _record_health("market_brief", success=True, rows_updated=1)
    except (ReportUnavailable, ProviderError) as e:
        # Fail-closed by design (an unverifiable brief must not ship), but it is
        # still a day with no brief for users — record it rather than letting it
        # vanish into a warning log.
        log.warning("job:generate_market_brief:unavailable")
        await _record_health("market_brief", success=False, error=f"{type(e).__name__}: {e}")
    except Exception as e:
        log.exception("job:generate_market_brief:failed")
        await _record_health("market_brief", success=False, error=str(e))


# ----- Workstream D: SBP / MUFAP / News / Filings / Volume spikes / Financials -----


FX_CURRENCIES = ("USD", "EUR", "GBP")


async def _fetch_fx_rows() -> list[dict]:
    """FX rows for ``macro_rates``, with a fallback when SBP has none.

    SBP retired the machine-readable FX page: both URLs in ``sbp.FX_URLS`` now
    answer 200 with the ~202KB site shell (7 tables, no currency rows), so
    ``_parse_fx_html`` has matched nothing since 2026-07-21 and `macro_rates`
    contains no FX series AT ALL — /api/macro/fx has been returning `[]` to web
    and mobile ever since. Their EasyData portal does expose an API but it is
    credentialed (401), so it cannot be wired up unopposed here.

    So: still try SBP first — if they restore the page this silently goes back
    to the authoritative source — and otherwise derive from the SAME provider
    chain that already backs /api/macro/monetary (ExchangeRate.fun → Fawaz →
    MoneyConvert, refreshed every 10 minutes and green throughout). That data
    is already fetched, already fallback-protected, and already trusted enough
    to render on the monetary page.

    Caveat, deliberately not papered over: these are MID-MARKET reference rates.
    They carry no bid/ask, so BUY and SELL are written as the same number rather
    than inventing a spread. A caller that needs a genuine interbank spread
    needs SBP EasyData credentials.
    """
    rows = await sbp.fetch_fx_rates()
    if rows:
        return rows

    from app.services.macro.monetary import get_monetary_snapshot

    snapshot = await get_monetary_snapshot()
    as_of = datetime.now(PTK_TZ).date().isoformat()
    out: list[dict] = []
    for entry in snapshot.get("currencies") or []:
        code = entry.get("code")
        if code not in FX_CURRENCIES:
            continue
        pkr = entry.get("one_unit_in_pkr")
        if not pkr:
            continue
        value = round(float(pkr), 4)
        out.append({"series": f"FX_{code}_BUY", "date": as_of, "value": value})
        out.append({"series": f"FX_{code}_SELL", "date": as_of, "value": value})
    if out:
        log.info("job:refresh_sbp:fx_from_fallback", currencies=len(out) // 2)
    return out


async def job_refresh_sbp():
    """Refresh SBP rates (KIBOR, PKRV, FX, policy rate) into ``macro_rates``."""
    try:
        log.info("job:refresh_sbp:start")
        now_iso = datetime.now(timezone.utc).isoformat()
        total = 0
        # Per-feed counts, so one dead feed cannot hide behind healthy ones. FX
        # was returning nothing for weeks while the job reported success.
        counts: dict[str, int] = {}
        for name, rows in (
            ("kibor", await sbp.fetch_kibor()),
            ("pkrv", await sbp.fetch_pkrv()),
            ("fx", await _fetch_fx_rows()),
        ):
            counts[name] = len(rows)
            if rows:
                payload = [{**r, "refreshed_at": now_iso} for r in rows]
                await async_execute(
                    lambda c, _p=payload: c.table("macro_rates").upsert(
                        _p, on_conflict="series,date"
                    )
                )
                total += len(rows)
        pr = await sbp.fetch_policy_rate()
        counts["policy_rate"] = 1 if (pr and pr.get("value") is not None) else 0
        if counts["policy_rate"]:
            await async_execute(
                lambda c: c.table("macro_rates").upsert(
                    [{**pr, "refreshed_at": now_iso}],
                    on_conflict="series,date",
                )
            )
            total += 1

        empty = sorted(k for k, v in counts.items() if v == 0)
        log.info("job:refresh_sbp:done", rows=total, **counts)
        if empty:
            log.warning("job:refresh_sbp:empty_feeds", feeds=empty)
        # One health row PER FEED, not one for the job.
        #
        # These four feeds fail independently — they are different SBP pages with
        # different parsers. Collapsing them into a single `sbp_macro` boolean
        # meant the dead `fx` feed (SBP moved FX rates behind client-side
        # rendering, so the parser has matched nothing since 2026-07-21) marked
        # the whole source red, hiding that KIBOR, PKRV and the policy rate were
        # landing correctly the entire time. Red-for-everything is the same
        # amount of information as green-for-everything: none.
        for feed, rows_written in counts.items():
            await _record_health(
                f"sbp_{feed}",
                success=rows_written > 0,
                rows_updated=rows_written,
                error=None if rows_written else "no rows parsed — upstream page format likely changed",
            )
    except Exception as e:
        log.exception("job:refresh_sbp:failed")
        for feed in ("kibor", "pkrv", "fx", "policy_rate"):
            await _record_health(f"sbp_{feed}", success=False, error=str(e))


async def job_refresh_monetary_rates():
    """Refresh keyless FX + gold/silver reference data into the local cache."""
    try:
        log.info("job:refresh_monetary_rates:start")
        from app.services.macro.monetary import refresh_monetary_snapshot

        snapshot = await refresh_monetary_snapshot()
        rows = len(snapshot.get("currencies") or []) + len(snapshot.get("metals") or [])
        log.info("job:refresh_monetary_rates:done", rows=rows)
        await _record_health("monetary_rates", success=True, rows_updated=rows)
    except Exception as e:
        log.exception("job:refresh_monetary_rates:failed")
        await _record_health("monetary_rates", success=False, error=str(e))


async def job_refresh_mufap():
    """Refresh the MUFAP mutual-fund catalog + per-fund NAV history."""
    try:
        log.info("job:refresh_mufap:start")
        funds = await mufap.fetch_funds()
        now_iso = datetime.now(timezone.utc).isoformat()
        if funds:
            payload = [{**f, "refreshed_at": now_iso} for f in funds]
            await async_execute(
                lambda c: c.table("psx_mutual_funds").upsert(
                    payload, on_conflict="fund_code"
                )
            )
            # NOTE: per-fund NAV history is NOT fetched here. MUFAP exposes no
            # per-fund history URL, so MUFAPScraper.fetch_nav_history is a stub
            # that always returns []. The previous loop called it for 50 funds
            # every run — 50 warning lines and 2.5s of sleeps to do nothing.
            # psx_fund_nav_history is populated by the CSV import path instead
            # (scripts/import_mufap_csv.py -> POST /api/funds/import).
        log.info("job:refresh_mufap:done", funds=len(funds))
        await _record_health("mufap_nav", success=True, rows_updated=len(funds))
    except BotChallengeError as e:
        # A known, understood blocker — not a crash. MUFAP put Cloudflare bot
        # protection in front of every page, so there is nothing to retry and a
        # stack trace every evening is noise. The health row carries the
        # remediation (CSV import) instead of "page format changed", which is
        # what it said for the eight days nobody noticed.
        log.warning("job:refresh_mufap:blocked", error=str(e))
        await _record_health("mufap_nav", success=False, error=str(e))
    except Exception as e:
        log.exception("job:refresh_mufap:failed")
        await _record_health("mufap_nav", success=False, error=str(e))


async def job_refresh_brecorder_news():
    """Pull Business Recorder news, tag tickers, upsert into ``psx_news``."""
    try:
        log.info("job:refresh_brecorder_news:start")
        items = await brecorder.fetch_news(limit=30)
        if not items:
            return
        # Build the known-symbols set from the live PSX profile table.
        known: set[str] = set()
        try:
            rows = await select_all("psx_profile", "symbol", order_by="symbol")
            known = {r["symbol"] for r in rows if r.get("symbol")}
        except Exception:
            pass

        rows = []
        for it in items:
            tags = brecorder._tag_tickers(it.get("headline", ""), it.get("body", ""), known)
            rows.append({
                "headline": it.get("headline"),
                "url": it.get("url"),
                "source": it.get("source") or "brecorder",
                "published_at": it.get("published_at"),
                "tickers": tags,
                "body": it.get("body"),
                "summary": it.get("summary"),
                "refreshed_at": datetime.now(timezone.utc).isoformat(),
            })
        if rows:
            await async_execute(
                lambda c: c.table("psx_news").upsert(rows, on_conflict="url")
            )
        log.info("job:refresh_brecorder_news:done", count=len(rows))
        await _record_health("brecorder_news", success=True, rows_updated=len(rows))
    except Exception as e:
        log.exception("job:refresh_brecorder_news:failed")
        await _record_health("brecorder_news", success=False, error=str(e))


async def job_fetch_announcement_pdfs():
    """For recent PSX announcements, download the PDF and extract text.

    Bounded to the 20 most recent PDFs per pass — fetching the full archive
    would saturate the disk. The extracted text lands in the ``filings``
    table.
    """
    try:
        log.info("job:fetch_announcement_pdfs:start")
        ann = await async_execute(
            lambda c: c.table("psx_announcements")
            .select("id,symbol,category,posted_at,url")
            .order("posted_at", desc=True)
            .limit(20)
        )
        items = ann.data or []
        if not items:
            return
        # Stream: upsert each filing's text as it's extracted, rather than
        # accumulating up to 20 full multi-page texts in one list before a batch
        # write. On the single-process box that batch was a real memory spike;
        # one text resident at a time is the same result for a fraction of peak.
        written = 0
        import tempfile
        for item in items:
            url = item.get("url")
            if not url or not url.lower().endswith(".pdf"):
                continue
            try:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    dest = tmp.name
                try:
                    ok, text, pg_count = await pdf_fetcher.process_url(url, dest)
                    if ok and text:
                        row = {
                            "announcement_id": item["id"],
                            "symbol": item.get("symbol"),
                            "type": item.get("category"),
                            "filed_at": (item.get("posted_at") or "")[:10] or None,
                            "pdf_url": url,
                            "text_content": text,
                            "page_count": pg_count,
                            "refreshed_at": datetime.now(timezone.utc).isoformat(),
                        }
                        await async_execute(
                            lambda c, r=row: c.table("filings").upsert(
                                r, on_conflict="announcement_id"
                            )
                        )
                        written += 1
                finally:
                    if os.path.exists(dest):
                        os.unlink(dest)
            except Exception:
                log.debug("pdf_processing_failed", url=url, exc_info=True)
        log.info("job:fetch_announcement_pdfs:done", count=written)
        await _record_health("announcement_pdfs", success=True, rows_updated=written)
    except Exception as e:
        log.exception("job:fetch_announcement_pdfs:failed")
        await _record_health("announcement_pdfs", success=False, error=str(e))


async def job_detect_unusual_volume():
    """Run the volume-spike detector and persist results."""
    try:
        log.info("job:detect_unusual_volume:start")
        rows = await volume_spike_detector.detect()
        log.info("job:detect_unusual_volume:done", count=len(rows))
        await _record_health("unusual_volume", success=True, rows_updated=len(rows))
    except Exception as e:
        log.exception("job:detect_unusual_volume:failed")
        await _record_health("unusual_volume", success=False, error=str(e))


async def job_refresh_financials_5y():
    """Weekly refresh of 5y annual + quarterly financials for every symbol."""
    try:
        log.info("job:refresh_financials_5y:start")
        rows = await select_all("psx_profile", "symbol", order_by="symbol")
        symbols = [r["symbol"] for r in rows]
        if not symbols:
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        written: dict[str, Any] = {"rows": 0, "errors": 0, "first_error": ""}

        async def _per_symbol(sym: str) -> None:
            try:
                # One page fetch yields both statements (halves the request load).
                annual, quarterly = await financials_psx.fetch_financials(sym)
                if annual:
                    payload = [{**r, "refreshed_at": now_iso} for r in annual]
                    await async_execute(
                        lambda c, _p=payload: c.table("psx_financials_annual").upsert(
                            _p, on_conflict="symbol,year"
                        )
                    )
                    written["rows"] += len(annual)
                if quarterly:
                    payload = [{**r, "refreshed_at": now_iso} for r in quarterly]
                    await async_execute(
                        lambda c, _p=payload: c.table("psx_financials_quarterly").upsert(
                            _p, on_conflict="symbol,period"
                        )
                    )
                    written["rows"] += len(quarterly)
            except Exception as e:
                written["errors"] += 1
                if not written["first_error"]:
                    written["first_error"] = f"{sym}: {e}"
                log.debug("financials_5y_failed", symbol=sym, exc_info=True)

        await _run_concurrently(symbols, _per_symbol, max_concurrent=3)
        log.info(
            "job:refresh_financials_5y:done",
            rows=written["rows"], errors=written["errors"], symbols=len(symbols),
        )
        # rows_updated was hardcoded to 0 here, so this job's health row could
        # never distinguish a full scrape from a total failure — and both
        # financials tables have been empty since the feature shipped.
        await _record_health(
            "financials_5y",
            success=written["rows"] > 0,
            rows_updated=written["rows"],
            error=None if written["rows"] > 0
            else f"wrote 0 rows; {written['errors']}/{len(symbols)} symbols failed; "
                 f"first: {(written['first_error'] or 'n/a')[:180]}",
        )
    except Exception as e:
        log.exception("job:refresh_financials_5y:failed")
        await _record_health("financials_5y", success=False, error=str(e))


async def job_refresh_dividends():
    """Fetch dividend payouts for all known symbols from DPS concurrently.

    Sequential processing took ~9 min for ~1000 symbols (0.5s sleep + network
    round-trip per call). Concurrency with max_concurrent=3 cuts it to ~3 min,
    which is fast enough for a daily 05:30 PKT cron run on Railway. The old
    ``next_run_time=datetime.now(PTK_TZ)`` startup trigger was removed because
    an immediate 9-min crawl at boot prevents the server from becoming ready
    while holding the lifespan host, and DPS is unreachable from some developer
    network environments.
    """
    log.info("job:refresh_dividends:start")
    try:
        symbols = await _get_all_symbols()
        if not symbols:
            log.warning("job:refresh_dividends:no_symbols")
            await _record_health(
                "refresh_dividends", success=False, error="no symbols available"
            )
            return

        counters = {"total": 0, "errors": 0}
        failed: list[str] = []

        async def _per_symbol(sym: str) -> None:
            try:
                events = await dps.fetch_payouts(sym)
                if events:
                    # Keyed by announcement_id, not a list comprehension: DPS
                    # returns the same announcement twice for some symbols, and
                    # Postgres rejects the whole batch with 21000 "ON CONFLICT
                    # DO UPDATE command cannot affect row a second time" when
                    # two proposed rows share the conflict target. Last one wins
                    # — the duplicates observed are identical payouts, so which
                    # survives does not matter; failing the symbol does.
                    rows_by_id = {
                        e.announcement_id: {
                            "announcement_id": e.announcement_id,
                            "symbol": e.symbol,
                            "ex_date": e.ex_date.isoformat() if e.ex_date else None,
                            "announcement_date": e.announcement_date.isoformat() if e.announcement_date else None,
                            "payout_type": e.payout_type,
                            "per_share": e.per_share,
                            "bonus_pct": e.bonus_pct,
                            "refreshed_at": datetime.now(timezone.utc).isoformat(),
                        }
                        for e in events
                    }
                    rows = list(rows_by_id.values())
                    await async_execute(
                        lambda c, r=rows: c.table("psx_dividends").upsert(r, on_conflict="announcement_id")
                    )
                    counters["total"] += len(rows)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                failed.append(sym)
                log.warning("job:refresh_dividends:symbol_failed", symbol=sym, error=str(e))

        await _run_concurrently(symbols, _per_symbol, max_concurrent=3)

        # Retry the stragglers. A calm re-probe of failing symbols returns clean
        # data, so the ~66/1077 failures seen nightly are transient timeouts from
        # the concurrent crawl, not broken symbols — and without a retry they
        # silently skipped a day's payouts and turned the whole run red.
        for attempt in range(1, 3):
            if not failed:
                break
            retry_syms, failed = failed, []
            log.info("job:refresh_dividends:retrying", count=len(retry_syms), attempt=attempt)
            await asyncio.sleep(5)
            await _run_concurrently(retry_syms, _per_symbol, max_concurrent=2)

        counters["errors"] = len(failed)
        log.info(
            "job:refresh_dividends:done",
            total=counters["total"],
            errors=counters["errors"],
            # The failing symbols themselves, not just a count. The nightly
            # failure count sat at exactly 66/1077 both before AND after the
            # retry loop was added — identical, which is not what transient
            # timeouts look like. These are almost certainly symbols with no DPS
            # payout page (delisted / suspended / never paid a dividend), and
            # without the names nobody could ever confirm that.
            failed_symbols=sorted(failed)[:40],
        )
        # Ratio, not zero-tolerance. Demanding 0/1077 failures over a 1077-symbol
        # crawl meant one dead symbol turned a fully successful run red — and
        # because a red run never advances last_success, `refresh_dividends`
        # showed "8 days stale" on the health dashboard while it was in fact
        # writing 421 rows every single night. A monitor that cries wolf nightly
        # is a monitor nobody reads.
        failure_ratio = counters["errors"] / len(symbols) if symbols else 1.0
        degraded = failure_ratio > DIVIDENDS_MAX_FAILURE_RATIO
        await _record_health(
            "refresh_dividends",
            success=not degraded,
            rows_updated=counters["total"],
            error=(
                None
                if not degraded
                else f"{counters['errors']}/{len(symbols)} symbols failed "
                     f"({failure_ratio:.1%} > {DIVIDENDS_MAX_FAILURE_RATIO:.0%} tolerance)"
            ),
            # NOT allow_zero_rows: fetch_payouts returns each symbol's whole
            # payout history, not a delta, so a healthy run always re-upserts
            # hundreds of rows. Zero rows here means total upstream breakage,
            # which is exactly what the zero-rows guard exists to catch.
        )
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.exception("job:refresh_dividends:failed")
        await _record_health("refresh_dividends", success=False, error=str(e))


# ----- init -----

def init_scheduler():
    # 10s, not 5s: the job is ONE DPS call covering ~496 symbols and measures
    # 6.9s end to end, so a 5s trigger could never be met — APScheduler skipped
    # the overlapping run every time and logged a warning for each, while the
    # job self-paced at ~7s anyway. 10s is honest, gives headroom over a slow
    # upstream, and costs ~3s of freshness the 5s setting never actually
    # delivered. job_poll_ahletrade still patches live prices every 5s.
    scheduler.add_job(job_refresh_market, IntervalTrigger(seconds=10), id="refresh_market", replace_existing=True)
    scheduler.add_job(job_refresh_announcements, IntervalTrigger(minutes=15), id="refresh_announcements", replace_existing=True)
    scheduler.add_job(job_poll_ahletrade, IntervalTrigger(seconds=5), id="poll_ahletrade", replace_existing=True)
    # All cron jobs pin Asia/Karachi — an unpinned trigger fires on host local
    # time, which differs between a dev box and a UTC container.
    scheduler.add_job(job_backfill_history, CronTrigger(hour=2, minute=0, timezone="Asia/Karachi"), id="backfill_history", replace_existing=True)
    # `day_of_week="sat"` — APScheduler counts Monday as 0, so the previous
    # `day_of_week=6` was Sunday despite being documented as Saturday. This job
    # is the only writer of psx_profile.listed_shares (the treemap's real
    # market-cap source), so its schedule is load-bearing.
    scheduler.add_job(job_refresh_fundamentals, CronTrigger(day_of_week="sat", hour=4, minute=0, timezone="Asia/Karachi"), id="refresh_fundamentals", replace_existing=True)
    # EOD bars twice a day, not once. DPS publishes the day's close shortly after
    # the 15:30 PKT session ends, so the 18:00 run puts it in the table the same
    # evening instead of ~7 hours later. The 01:00 run stays as the safety net
    # that also catches a late DPS publish. Both are idempotent upserts.
    # Both runs carry an hour of grace, matching every other daily job. Without
    # it they inherited APScheduler's 1s default and a momentarily busy loop
    # dropped the run outright — the table then sat a full day stale, which is
    # exactly the failure the twice-daily schedule exists to prevent.
    scheduler.add_job(
        job_refresh_index_eod,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=0, timezone="Asia/Karachi"),
        id="refresh_index_eod_postclose",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        job_refresh_index_eod,
        CronTrigger(hour=1, minute=0, timezone="Asia/Karachi"),
        id="refresh_index_eod",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Live index snapshot: every 5 min during market hours (Mon-Fri 09:00-17:00 PKT).
    # Runs during market hours + buffer so the last snapshot before EOD is captured.
    scheduler.add_job(
        job_refresh_index_snapshot,
        CronTrigger(day_of_week="mon-fri", hour="9-16", minute="*/5", timezone="Asia/Karachi"),
        id="refresh_index_snapshot",
        replace_existing=True,
        # 120s covered a single missed beat but nothing worse: on 2026-08-05 the
        # last eight slots of the day (16:20–16:55 PKT) were all dropped, so the
        # final snapshot of the session — the one the cards fall back on after
        # close — was never taken. 600s survives a longer stall, and coalesce
        # keeps the catch-up to one run.
        misfire_grace_time=600,
    )
    # Intraday bar capture: every minute during market hours. One minute is the
    # sampling rate, not the bar size — samples fold into 5-minute buckets, so
    # each bar is built from ~5 observations and a missed beat only costs
    # resolution within a bucket, never the bucket itself.
    scheduler.add_job(
        job_capture_intraday,
        CronTrigger(day_of_week="mon-fri", hour="9-16", minute="*", timezone="Asia/Karachi"),
        id="capture_intraday",
        replace_existing=True,
        # Deliberately short: a late sample would be filed under the bucket it
        # runs in, not the one it was scheduled for, so a stale catch-up run is
        # worse than a skipped one.
        misfire_grace_time=30,
    )
    scheduler.add_job(
        job_prune_intraday,
        CronTrigger(hour=1, minute=30, timezone="Asia/Karachi"),
        id="prune_intraday",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(job_check_alerts, IntervalTrigger(seconds=60), id="check_alerts", replace_existing=True)
    # Keep-alive: the always-on worker pings the API so Railway can't cold-start
    # it after an idle gap (a cold boot pays the numpy/pandas + reflection cost).
    # Only scheduled when API_KEEPALIVE_URL is configured.
    if settings.api_keepalive_url.strip():
        scheduler.add_job(
            job_keepalive,
            IntervalTrigger(minutes=max(1, settings.keepalive_interval_minutes)),
            id="keepalive",
            replace_existing=True,
            next_run_time=datetime.now(PTK_TZ),  # warm it immediately on boot
        )
    scheduler.add_job(job_refresh_tv_data, IntervalTrigger(minutes=5), id="refresh_tv_data", replace_existing=True)
    # Shariah universe from the live KMIALLSHR index. Daily 03:30 PKT — index
    # membership is reviewed periodically, and this is the only writer of
    # psx_profile.is_shariah.
    scheduler.add_job(job_refresh_shariah, CronTrigger(hour=3, minute=30, timezone="Asia/Karachi"), id="refresh_shariah", replace_existing=True)
    # FIPI/LIPI flows publish after settlement — 18:30 PKT weekdays covers it,
    # and the job re-fetches yesterday too so late corrections are captured.
    scheduler.add_job(
        job_refresh_fipi,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=30, timezone="Asia/Karachi"),
        id="refresh_fipi",
        replace_existing=True,
    )
    # Shared Market Brief — weekdays, in Asia/Karachi (PSX) time (§11).
    #
    # Two runs, not one. The 09:45 run (after the morning market data refresh)
    # gives users something to read during the session. The 16:05 run lands
    # after the 15:30 close and passes replace=True so the stored brief ends the
    # day describing the COMPLETED session — otherwise it stays frozen on a
    # partial-day move and reads as a closing summary that never happened.
    #
    # misfire_grace_time is generous on both: a brief served late is fine, a day
    # with no brief is not.
    scheduler.add_job(
        job_generate_market_brief,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=45, timezone="Asia/Karachi"),
        id="generate_market_brief",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        job_generate_market_brief,
        CronTrigger(day_of_week="mon-fri", hour=16, minute=5, timezone="Asia/Karachi"),
        id="generate_market_brief_postclose",
        replace_existing=True,
        kwargs={"replace": True},
        misfire_grace_time=3600,
    )
    # ---- Workstream D ----
    # SBP rates: KIBOR/PKRV/FX/policy rate into ``macro_rates``. Daily 09:30 PKT,
    # right after the market open so a fresh policy-rate column appears on the
    # dashboard for the trading day.
    scheduler.add_job(
        job_refresh_sbp,
        CronTrigger(hour=9, minute=30, timezone="Asia/Karachi"),
        id="refresh_sbp",
        replace_existing=True,
    )
    # Currency + metals reference data. This is keyless external data, so keep a
    # short local cache warm without turning page views into provider traffic.
    scheduler.add_job(
        job_refresh_monetary_rates,
        IntervalTrigger(minutes=10),
        id="refresh_monetary_rates",
        replace_existing=True,
    )
    # MUFAP mutual funds. Weekday evenings 19:00 PKT — the public NAV report
    # is published after the market close (15:30) so 19:00 captures the day's
    # refresh.
    scheduler.add_job(
        job_refresh_mufap,
        CronTrigger(day_of_week="mon-fri", hour=19, minute=0, timezone="Asia/Karachi"),
        id="refresh_mufap",
        replace_existing=True,
    )
    # BRecorder news. Every 5 minutes during the day — used by the dashboard
    # ticker feed; cheap to scrape.
    scheduler.add_job(
        job_refresh_brecorder_news,
        IntervalTrigger(minutes=5),
        id="refresh_brecorder_news",
        replace_existing=True,
    )
    # PDF fetcher for announcement PDFs. 15-minute cadence — picks up the
    # newest PSX filings and extracts their text into ``filings``.
    scheduler.add_job(
        job_fetch_announcement_pdfs,
        IntervalTrigger(minutes=15),
        id="fetch_announcement_pdfs",
        replace_existing=True,
    )
    # Volume-spike detector. 5-minute cadence; cheap SQL.
    scheduler.add_job(
        job_detect_unusual_volume,
        IntervalTrigger(minutes=5),
        id="detect_unusual_volume",
        replace_existing=True,
    )
    # 5y financials refresh. Weekly on Sunday 03:00 PKT — financials.psx.com.pk
    # updates a quarter/year at a time, so a weekly cadence is sufficient.
    scheduler.add_job(
        job_refresh_financials_5y,
        CronTrigger(day_of_week="sun", hour=3, minute=0, timezone="Asia/Karachi"),
        id="refresh_financials_5y",
        replace_existing=True,
    )
    # Dividends refresh: daily at 5:30 AM PKT. Removed from the startup path
    # (~1076 sequential HTTP calls with 0.5s delay = ~9 min) because DPS is
    # unreachable from some network environments, which hung the whole backend.
    # The deployed Railway instance has reliable DPS connectivity and the
    # 5:30 AM run populates data before market hours.
    scheduler.add_job(
        job_refresh_dividends,
        CronTrigger(hour=5, minute=30, timezone="Asia/Karachi"),
        id="refresh_dividends",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Canonical corporate-event ingestion from the DB (announcements + dividends).
    # Runs after the 5:30 dividends refresh and hourly through the trading day so
    # new disclosures become point-in-time events promptly. DB-only, idempotent.
    scheduler.add_job(
        job_ingest_signal_events,
        CronTrigger(minute=20, timezone="Asia/Karachi"),
        id="ingest_signal_events",
        replace_existing=True,
        misfire_grace_time=1800,
    )
    # Cross-sectional factor ranks: after EOD prices settle (evening PKT).
    scheduler.add_job(
        job_precompute_cross_section,
        CronTrigger(hour=20, minute=0, timezone="Asia/Karachi"),
        id="precompute_cross_section",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Live track record. Recording runs 30 min after the cross-section job so
    # the reversal percentile it conditions on is fresh; maturation runs later
    # still and is independent of both.
    scheduler.add_job(
        job_record_signal_recommendations,
        CronTrigger(hour=20, minute=30, timezone="Asia/Karachi"),
        id="record_signal_recommendations",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        job_mature_signal_recommendations,
        CronTrigger(hour=21, minute=15, timezone="Asia/Karachi"),
        id="mature_signal_recommendations",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Error-event retention sweep. Daily and off-peak: the table is append-only
    # on the failure path, so it only ever grows without this.
    scheduler.add_job(
        job_purge_error_events,
        CronTrigger(hour=4, minute=15, timezone="Asia/Karachi"),
        id="purge_error_events",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Bank-email transaction import poller (from dev). Gated on config so it
    # never runs unless Gmail OAuth + the encryption key are set.
    if settings.email_import_configured:
        scheduler.add_job(
            job_poll_inboxes,
            IntervalTrigger(minutes=settings.email_poll_interval_minutes),
            id="poll_inboxes",
            replace_existing=True,
        )
    scheduler.start()
    log.info("scheduler:started")


def shutdown_scheduler():
    # No-op when this process never started the scheduler (process_role="web",
    # or it lost the advisory lock) — shutting down a non-running scheduler
    # raises SchedulerNotRunningError.
    if not scheduler.running:
        return
    scheduler.shutdown(wait=False)
    log.info("scheduler:shutdown")


async def close_scrapers():
    """Close every scraper's httpx.AsyncClient.

    Each module-level scraper lazily creates an AsyncClient and defines close(),
    but nothing called it — so every shutdown leaked a client and its
    connection pool. Failures are swallowed: shutdown must not raise.
    """
    for name, scraper in (
        ("ahletrade", ahletrade),
        ("dps", dps),
        ("tv", tv),
        ("sbp", sbp),
        ("mufap", mufap),
        ("brecorder", brecorder),
        ("pdf_fetcher", pdf_fetcher),
        ("financials_psx", financials_psx),
    ):
        try:
            await scraper.close()
        except Exception:
            log.warning("scraper_close_failed", scraper=name, exc_info=True)
    log.info("scrapers:closed")
