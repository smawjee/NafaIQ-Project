from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Optional

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
from app.scrapers.tradingview import TV_SECTOR_MAP, TradingViewScraper
from app.scrapers.sbp import SBPScraper
from app.scrapers.mufap import MUFAPScraper
from app.scrapers.brecorder import BRecorderScraper
from app.scrapers.pdf_fetcher import PDFFetcher
from app.scrapers.financials_psx import FinancialsPSXScraper
from app.services.signals.volume_spikes import VolumeSpikeDetector
import os
from app.services.market._base import get_cache, ALL_PSX_INDICES
from app.api.health import set_market_refresh_time
from app.db.supabase import async_execute, select_all
from app.repositories import reports_repo
from app.repositories.base import begin
from app.services.ai import engine
from app.services.ai.engine import ReportUnavailable
from app.services.ai.providers import ProviderError
from app.services.ai.specs import REPORT_SPECS

log = structlog.get_logger()

scheduler = AsyncIOScheduler()
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


async def _record_health(source: str, success: bool, rows_updated: int = 0, error: str | None = None):
    """Upsert a row into psx_data_source_health.

    On success: clears any prior error state so the row reflects the latest
    successful run. On failure: sets last_error/last_error_message and leaves
    last_success untouched.

    Never raises. An observability write must not be able to fail the job it is
    observing: most call sites sit inside an ``except`` block (with no enclosing
    try) or after the job's real work has already succeeded, so propagating here
    would either escape to APScheduler or turn a successful run into a spurious
    "job failed". Failures are logged at error level and swallowed.
    """
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


async def job_poll_ahletrade():
    """Polls AhleTrade for real-time trades and writes to psx_market_snapshot."""
    if not await _is_market_open():
        return
    try:
        rows = await select_all("psx_profile", "symbol", order_by="symbol")
        sym_list = [r["symbol"] for r in rows]

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
            # Phase 0 / B1: AHL writes only {price, volume, refreshed_at}.
            # Use the partial-update RPC so we never clobber the DPS-derived
            # change/change_pct/day_high/day_low that job_refresh_market owns.
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


async def job_backfill_history():
    total_bars = 0
    try:
        log.info("job:backfill_history:start")
        rows = await select_all("psx_profile", "symbol", order_by="symbol")
        symbols = [r["symbol"] for r in rows]
        if not symbols:
            return

        async def _backfill(sym: str) -> None:
            nonlocal total_bars
            try:
                bars = await dps.fetch_historical(sym)
                if bars:
                    rows = [b.to_dict() for b in bars]
                    await async_execute(lambda c: c.table("psx_ohlcv").upsert(rows, on_conflict="symbol,date"))
                    total_bars += len(bars)
                log.info("job:backfill_history:symbol_done", symbol=sym, bars=len(bars))
            except Exception as e:
                # One symbol failing is routine (upstream drops connections);
                # the traceback is httpx internals and identical every time.
                log.warning("job:backfill_history:failed", symbol=sym, error=str(e))

        await _run_concurrently(symbols, _backfill, max_concurrent=5)
        log.info("job:backfill_history:done", total_bars=total_bars)
        await _record_health("backfill_history", success=True, rows_updated=total_bars)
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
                log.warning("job:refresh_fundamentals:failed", symbol=sym, error=str(e))

        await _run_concurrently(symbols, _refresh, max_concurrent=5)
        log.info("job:refresh_fundamentals:done", total=total)
        await _record_health("psx_fundamentals", success=True, rows_updated=total)
    except Exception as e:
        log.exception("job:refresh_fundamentals:failed")
        await _record_health("psx_fundamentals", success=False, error=str(e))


async def job_refresh_index_eod():
    total_bars = 0
    try:
        log.info("job:refresh_index_eod:start")
        for code in ALL_PSX_INDICES:
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
                    total_bars += len(bars)
            except Exception as e:
                log.warning("job:refresh_index_eod:failed", code=code, error=str(e))
        log.info("job:refresh_index_eod:done", total_bars=total_bars)
        await _record_health("index_eod", success=True, rows_updated=total_bars)
    except Exception as e:
        log.exception("job:refresh_index_eod:failed")
        await _record_health("index_eod", success=False, error=str(e))


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
    except Exception:
        log.exception("job:poll_inboxes:failed")


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


def _context_hash(bundle: dict) -> str:
    """sha256 of the assembled bundle — the report's cache/provenance key."""
    return hashlib.sha256(
        json.dumps(bundle, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


async def job_generate_market_brief():
    """Generate the once-per-trading-day SHARED Market Brief and persist it (§11).

    Runs after the daily market data is refreshed. The Market Brief is shared
    (no user, `confidential=False` -> free/shared provider) and cache-keyed by
    trading_date via `get_or_create_shared`, so the read endpoint only fetches
    the latest. A failed brief must NEVER crash the scheduler, so every failure
    mode (fail-closed `ReportUnavailable`, `ProviderError`, or anything else) is
    logged and swallowed — mirroring `job_check_alerts`.
    """
    try:
        log.info("job:generate_market_brief:start")
        gen = await engine.generate_report(REPORT_SPECS["market_brief"], lang="en")
        trading_date = datetime.now(PTK_TZ).date().isoformat()
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
            )
        log.info(
            "job:generate_market_brief:done",
            trading_date=trading_date,
            verified=gen.verification.verified,
        )
    except (ReportUnavailable, ProviderError):
        log.warning("job:generate_market_brief:unavailable")
    except Exception:
        log.exception("job:generate_market_brief:failed")


# ----- Workstream D: SBP / MUFAP / News / Filings / Volume spikes / Financials -----


async def job_refresh_sbp():
    """Refresh SBP rates (KIBOR, PKRV, FX, policy rate) into ``macro_rates``."""
    try:
        log.info("job:refresh_sbp:start")
        now_iso = datetime.now(timezone.utc).isoformat()
        total = 0
        for series, rows in (
            ("kibor", await sbp.fetch_kibor()),
            ("pkrv", await sbp.fetch_pkrv()),
            ("fx", await sbp.fetch_fx_rates()),
        ):
            if rows:
                payload = [
                    {**r, "refreshed_at": now_iso}
                    for r in rows
                ]
                await async_execute(
                    lambda c, _p=payload: c.table("macro_rates").upsert(
                        _p, on_conflict="series,date"
                    )
                )
                total += len(rows)
        pr = await sbp.fetch_policy_rate()
        if pr and pr.get("value") is not None:
            await async_execute(
                lambda c: c.table("macro_rates").upsert(
                    [{**pr, "refreshed_at": now_iso}],
                    on_conflict="series,date",
                )
            )
            total += 1
        log.info("job:refresh_sbp:done", rows=total)
        await _record_health("sbp_macro", success=True, rows_updated=total)
    except Exception as e:
        log.exception("job:refresh_sbp:failed")
        await _record_health("sbp_macro", success=False, error=str(e))


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
        rows: list[dict] = []
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
                        rows.append({
                            "announcement_id": item["id"],
                            "symbol": item.get("symbol"),
                            "type": item.get("category"),
                            "filed_at": (item.get("posted_at") or "")[:10] or None,
                            "pdf_url": url,
                            "text_content": text,
                            "page_count": pg_count,
                            "refreshed_at": datetime.now(timezone.utc).isoformat(),
                        })
                finally:
                    if os.path.exists(dest):
                        os.unlink(dest)
            except Exception:
                log.debug("pdf_processing_failed", url=url, exc_info=True)
        if rows:
            await async_execute(
                lambda c: c.table("filings").upsert(rows, on_conflict="announcement_id")
            )
        log.info("job:fetch_announcement_pdfs:done", count=len(rows))
        await _record_health("announcement_pdfs", success=True, rows_updated=len(rows))
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
        async def _per_symbol(sym: str) -> None:
            try:
                annual = await financials_psx.fetch_annual(sym)
                if annual:
                    payload = [{**r, "refreshed_at": now_iso} for r in annual]
                    await async_execute(
                        lambda c, _p=payload: c.table("psx_financials_annual").upsert(
                            _p, on_conflict="symbol,year"
                        )
                    )
                quarterly = await financials_psx.fetch_quarterly(sym)
                if quarterly:
                    payload = [{**r, "refreshed_at": now_iso} for r in quarterly]
                    await async_execute(
                        lambda c, _p=payload: c.table("psx_financials_quarterly").upsert(
                            _p, on_conflict="symbol,period"
                        )
                    )
            except Exception:
                log.debug("financials_5y_failed", symbol=sym, exc_info=True)

        await _run_concurrently(symbols, _per_symbol, max_concurrent=3)
        log.info("job:refresh_financials_5y:done")
        await _record_health("financials_5y", success=True, rows_updated=0)
    except Exception as e:
        log.exception("job:refresh_financials_5y:failed")
        await _record_health("financials_5y", success=False, error=str(e))


async def job_refresh_dividends():
    """Fetch dividend payouts for all known symbols from DPS."""
    log.info("job:refresh_dividends:start")
    try:
        # Reuse the module-level scraper: constructing one per run leaked an
        # httpx.AsyncClient (and its pool) on every invocation.
        symbols = await _get_all_symbols()
        if not symbols:
            log.warning("job:refresh_dividends:no_symbols")
            await _record_health(
                "refresh_dividends", success=False, error="no symbols available"
            )
            return

        total = 0
        errors = 0
        for sym in symbols:
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
                    await async_execute(lambda c, r=rows: c.table("psx_dividends").upsert(r, on_conflict="announcement_id"))
                    total += len(rows)
            except asyncio.CancelledError:
                # Expected on graceful shutdown — do not count as a symbol error.
                log.info("job:refresh_dividends:cancelled", processed=total)
                raise
            except Exception as e:
                errors += 1
                log.warning("job:refresh_dividends:symbol_failed", symbol=sym, error=str(e))
            await asyncio.sleep(0.5)

        log.info("job:refresh_dividends:done", total=total, errors=errors)
        # Only green when every symbol succeeded — otherwise the health row
        # claims the source is fine while most of the market failed.
        await _record_health(
            "refresh_dividends",
            success=errors == 0,
            rows_updated=total,
            error=None if errors == 0 else f"{errors}/{len(symbols)} symbols failed",
        )
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.exception("job:refresh_dividends:failed")
        await _record_health("refresh_dividends", success=False, error=str(e))


# ----- init -----

def init_scheduler():
    scheduler.add_job(job_refresh_market, IntervalTrigger(seconds=5), id="refresh_market", replace_existing=True)
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
    scheduler.add_job(job_refresh_index_eod, CronTrigger(hour=1, minute=0, timezone="Asia/Karachi"), id="refresh_index_eod", replace_existing=True)
    scheduler.add_job(job_check_alerts, IntervalTrigger(seconds=60), id="check_alerts", replace_existing=True)
    scheduler.add_job(job_refresh_tv_data, IntervalTrigger(minutes=5), id="refresh_tv_data", replace_existing=True)
    # Shariah universe from the live KMIALLSHR index. Daily 03:30 PKT — index
    # membership is reviewed periodically, and this is the only writer of
    # psx_profile.is_shariah.
    scheduler.add_job(job_refresh_shariah, CronTrigger(hour=3, minute=30, timezone="Asia/Karachi"), id="refresh_shariah", replace_existing=True)
    # Shared, once-per-trading-day Market Brief — weekdays ~09:45 PKT, after the
    # morning market data refresh (§11). Runs in Asia/Karachi (PSX) time.
    scheduler.add_job(
        job_generate_market_brief,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=45, timezone="Asia/Karachi"),
        id="generate_market_brief",
        replace_existing=True,
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
    # Dividends refresh: daily, with an immediate first run on startup so the
    # frontend dividend page shows real data on first request.
    # Cadence rationale: a sweep is ~500 symbols with a 0.5s delay each (~4 min
    # and ~500 requests to dps.psx.com.pk). Dividends change a few times per
    # quarter per symbol, so the old 30-min interval meant ~24k requests/day for
    # data that barely moves — daily is ample and matches the other
    # fundamentals-style jobs (refresh_fundamentals, financials_5y are weekly).
    scheduler.add_job(
        job_refresh_dividends,
        CronTrigger(hour=5, minute=30, timezone="Asia/Karachi"),
        id="refresh_dividends",
        replace_existing=True,
        misfire_grace_time=3600,
        next_run_time=datetime.now(PTK_TZ),
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
