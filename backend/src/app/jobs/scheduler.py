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

from app.scrapers.dps import DPSScraper
from app.scrapers.ahletrade import AhleTradePoller
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
from app.db.supabase import async_execute
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
            # Phase 0 / B1: AHL writes only {price, volume, refreshed_at}.
            # Use the partial-update RPC so we never clobber the DPS-derived
            # change/change_pct/day_high/day_low that job_refresh_market owns.
            await async_execute(
                lambda c: c.rpc("patch_market_snapshot", {"rows": rows_to_write})
            )
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

        # Hardcoded Shariah-compliant stock list (sourced from PSX Shariah Index constituents).
        # This is more reliable than trying to derive from DPSScraper data.
        SHARIAH_STOCKS: set[str] = {
            # KMI30 and KMIALLSHR constituents — the definitive PSX Shariah universe.
            # (These will be moved to config.py in a future cleanup.)
            "MARI", "OGDC", "PPL", "POL", "LUCK", "SEARL", "HBL", "MEBL",
            "UBL", "FABL", "EFERT", "FFC", "ENGRO", "NESTLE", "COLG", "LINDE",
            "NCL", "SCBPL", "BAHL", "BAFL", "TGL", "HUMNL", "GHGL", "MLCF",
            "PIOC", "ASTL", "AMBL", "KTML", "CHCC", "FLYNG", "PSX", "FCCL",
            "DCR", "EPCL", "LOTCHEM", "RPL", "TREET", "UNITY", "WAHUN", "GATI",
            "AGL", "BIFO", "BIPL", "BML", "BRR", "CASH", "CNERGY", "DOL",
            "DWAE", "DYNO", "ELCM", "FFL", "FRSM", "GAL", "GLAXO", "HAEL",
            "HASCOL", "HSPI", "HZAN", "ICL", "IDYM", "ILP", "IMCO", "INDU",
            "ISL", "JKL", "JSCL", "KAPCO", "KOHE", "KOHC", "LEUL", "LPGL",
            "MACFL", "MERIT", "MFTM", "MLOD", "MUREB", "NATF", "NBP", "NCPL",
            "NML", "NRL", "NTCL", "OBOY", "PAEL", "PAKRI", "PGIL", "PICT",
            "PKGS", "PMI", "PNER", "PRFG", "PRWM", "PSMC", "PTC", "QUICE",
            "RMFL", "SANL", "SAPT", "SGF", "SHEL", "SHJD", "SIMG", "SITC",
            "SMCPL", "SPWL", "SRVI", "SSGC", "STJT", "STPL", "SYM", "SYS",
            "TATM", "TAUS", "TCORP", "TGL", "THALL", "TPLP", "TRG", "TRIPF",
            "UPFL", "WAVES", "WTL", "YOUSP", "ZIL",
        }

        # Pre-load existing listed_shares values so the TV job doesn't
        # nullify them (the TV scanner has no shares-outstanding column).
        existing_rows: list[dict] = []
        try:
            res = await async_execute(
                lambda c: c.table("psx_profile").select("symbol,listed_shares,free_float")
            )
            existing_rows = res.data or []
        except Exception:
            log.debug("job:refresh_tv_data:existing_profile_load_failed", exc_info=True)
        existing_by_sym: dict[str, dict] = {
            r["symbol"].upper(): r for r in existing_rows if r.get("symbol")
        }

        profile_rows = []
        for item in items:
            tv_sector = item.get("sector") or ""
            sector = TV_SECTOR_MAP.get(tv_sector, tv_sector or None)
            sym = item["symbol"].upper()

            existing = existing_by_sym.get(sym, {})
            listed_shares = existing.get("listed_shares")
            free_float = existing.get("free_float")

            row = {
                "symbol": sym,
                "name": item.get("name", item["symbol"]),
                "sector": sector,
                "logoid": item.get("logoid"),
                "is_shariah": sym in SHARIAH_STOCKS,
                "refreshed_at": now,
            }
            if listed_shares is not None:
                row["listed_shares"] = listed_shares
            if free_float is not None:
                row["free_float"] = free_float
            profile_rows.append(row)

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
    except Exception:
        log.exception("job:refresh_sbp:failed")


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
            # Pull each fund's history. Bounded at 50 funds per pass — the
            # full history for every fund is impractical (thousands of rows
            # each); we only fetch funds that the dashboard exposes.
            for f in funds[:50]:
                try:
                    history = await mufap.fetch_nav_history(f["fund_code"])
                    if history:
                        await async_execute(
                            lambda c, _h=history: c.table("psx_fund_nav_history").upsert(
                                _h, on_conflict="fund_code,date"
                            )
                        )
                except Exception:
                    log.debug("mufap_history_failed", fund=f.get("fund_code"), exc_info=True)
                await asyncio.sleep(0.05)
        log.info("job:refresh_mufap:done", funds=len(funds))
    except Exception:
        log.exception("job:refresh_mufap:failed")


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
            result = await async_execute(
                lambda c: c.table("psx_profile").select("symbol").limit(1000)
            )
            known = {r["symbol"] for r in (result.data or []) if r.get("symbol")}
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
    except Exception:
        log.exception("job:refresh_brecorder_news:failed")


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
    except Exception:
        log.exception("job:fetch_announcement_pdfs:failed")


async def job_detect_unusual_volume():
    """Run the volume-spike detector and persist results."""
    try:
        log.info("job:detect_unusual_volume:start")
        rows = await volume_spike_detector.detect()
        log.info("job:detect_unusual_volume:done", count=len(rows))
    except Exception:
        log.exception("job:detect_unusual_volume:failed")


async def job_refresh_financials_5y():
    """Weekly refresh of 5y annual + quarterly financials for every symbol."""
    try:
        log.info("job:refresh_financials_5y:start")
        result = await async_execute(lambda c: c.table("psx_profile").select("symbol"))
        symbols = [r["symbol"] for r in (result.data or [])]
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
    except Exception:
        log.exception("job:refresh_financials_5y:failed")


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
    scheduler.start()
    log.info("scheduler:started")


def shutdown_scheduler():
    scheduler.shutdown(wait=False)
    log.info("scheduler:shutdown")
