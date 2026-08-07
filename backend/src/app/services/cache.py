from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timedelta, timezone
from typing import Awaitable, Callable, Optional

import structlog

from app.config import settings
from app.db.supabase import async_execute, get_supabase, select_all
from app.scrapers.dps import DPSScraper
from app.scrapers.tradingview import get_scanner
from app.models import (
    MarketSnapshotItem,
    OHLCVBar,
    FundamentalsData,
    CompanyProfile,
    AnnouncementItem,
    DividendEvent,
    IndexBar,
    SymbolInfo,
    SectorDataItem,
)

log = structlog.get_logger()


# Minimum seconds between background scrapes of the same resource. The
# scheduler already refreshes these while the market is open; this throttle
# keeps stale-data fallbacks from hammering DPS when it is not.
BACKGROUND_REFRESH_THROTTLE = 60.0

# PostgREST returns at most ~1000 rows per response (Supabase's default
# max-rows), whatever .limit() asks for. get_history pages at this size so deep
# requests ("All" = 10 years ≈ 2500 bars) return the full series instead of
# being silently clipped at the first page.
_HISTORY_PAGE_SIZE = 1000
_PSX_TZ = timezone(timedelta(hours=5))
_INDEX_EOD_CUTOFF_MINUTES = 16 * 60 + 45


class CacheLayer:
    """Read-through cache: serve from Supabase if fresh, else scrape + write.

    Stale DB data is served immediately with the scrape moved to a background
    task — user requests only wait on a live PSX scrape when the table is
    completely empty.
    """

    def __init__(self, dps: DPSScraper):
        self.dps = dps
        self.db = get_supabase()
        self._refreshing: set[str] = set()
        self._last_refresh_attempt: dict[str, float] = {}
        # Live DPS scraping is the WORKER's job. On the web/API process
        # (PROCESS_ROLE=web -> runs_scheduler False), never scrape in the request
        # path: serve whatever the worker has written to the DB and return fast.
        # A blocking DPS scrape here made market endpoints take 8-13s whenever
        # DPS was unreachable (4 retries x backoff) — the "slow loading". On a
        # single-process deploy (all/worker) this stays True, unchanged.
        self.live_scrape = settings.runs_scheduler

    def _refresh_in_background(self, key: str, refresh: Callable[[], Awaitable[object]]) -> None:
        if not self.live_scrape:
            return  # web process: never scrape DPS off the request path either
        now = time.monotonic()
        if key in self._refreshing:
            return
        if now - self._last_refresh_attempt.get(key, 0.0) < BACKGROUND_REFRESH_THROTTLE:
            return
        self._last_refresh_attempt[key] = now
        self._refreshing.add(key)

        async def _run() -> None:
            try:
                await refresh()
            except Exception:
                log.warning("cache_background_refresh_failed", key=key, exc_info=True)
            finally:
                self._refreshing.discard(key)

        try:
            asyncio.get_running_loop().create_task(_run())
        except RuntimeError:
            self._refreshing.discard(key)

    @staticmethod
    def _is_stale(refreshed_at: object, max_age_seconds: int) -> bool:
        """True when a row is older than the window, or carries no usable stamp.

        An unparseable/absent `refreshed_at` counts as stale so it schedules a
        refresh — but callers must still SERVE the row. Staleness selects when to
        re-fetch, never whether the caller gets data.
        """
        if not isinstance(refreshed_at, str) or not refreshed_at:
            return True
        try:
            last_refresh = datetime.fromisoformat(refreshed_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        return (datetime.now(timezone.utc) - last_refresh).total_seconds() >= max_age_seconds

    # ---------- market snapshot ----------

    async def get_market_snapshot(self, max_age_seconds: int = 5) -> list[MarketSnapshotItem]:
        try:
            rows = await select_all("psx_market_snapshot", "*", order_by="symbol")
            if rows:
                newest = max((r.get("refreshed_at") or "" for r in rows), default="")
                stale = True
                if newest:
                    last_refresh = datetime.fromisoformat(newest.replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - last_refresh).total_seconds()
                    stale = age >= max_age_seconds
                if stale:
                    # Serve what we have; refresh off the request path.
                    self._refresh_in_background("market_snapshot", self._scrape_market_snapshot)
                return [_row_to_market_snapshot(r) for r in rows]
        except Exception:
            log.warning("cache_market_read_failed", exc_info=True)

        # Nothing cached: only the worker scrapes DPS. The web process returns
        # empty instead of blocking the request on a (possibly failing) scrape.
        if not self.live_scrape:
            return []
        return await self._scrape_market_snapshot()

    async def _scrape_market_snapshot(self) -> list[MarketSnapshotItem]:
        """Scrape the market watch, falling back to the TradingView scanner.

        DPS has dropped the /market-watch connection entirely from datacenter
        egress IPs since 2026-08-06 (RemoteProtocolError, no response headers)
        while the scanner keeps working. When DPS fails, TV rows are served
        with day_high/day_low absent so the writer below does not NULL them —
        PostgREST upsert only touches the columns present in the payload.
        """
        try:
            items = await self.dps.fetch_market_watch()
        except Exception:
            log.warning("cache_market_dps_failed_tv_fallback", exc_info=True)
            items = []
            for r in await get_scanner().fetch_market_data():
                price = r.get("close")
                if price is None or price <= 0:
                    continue
                items.append(
                    MarketSnapshotItem(
                        symbol=r["symbol"].upper(),
                        price=price,
                        change=r.get("change_abs"),
                        change_pct=r.get("change_pct"),
                        volume=int(r.get("volume") or 0),
                    )
                )
        if items:
            rows = [
                {
                    "symbol": i.symbol,
                    "price": i.price,
                    "change": i.change,
                    "change_pct": i.change_pct,
                    "volume": i.volume,
                    "refreshed_at": datetime.now(timezone.utc).isoformat(),
                }
                for i in items
            ]
            if items[0].day_high is not None:
                for r, i in zip(rows, items):
                    r["day_high"] = i.day_high
                    r["day_low"] = i.day_low
            try:
                await async_execute(lambda c: c.table("psx_market_snapshot").upsert(rows, on_conflict="symbol"))
            except Exception:
                log.warning("cache_market_write_failed", exc_info=True)
        return items

    # ---------- OHLCV history ----------

    async def get_history(self, symbol: str, days: int = 250, max_age_seconds: int = 21600) -> list[OHLCVBar]:
        sym = symbol.upper()
        try:
            # Page explicitly. PostgREST caps ANY single response at ~1000 rows
            # regardless of .limit(), so a bare .limit(days) silently truncated
            # every request deeper than ~4 years — psx_ohlcv holds ~10 years
            # (back to 2016), so the tail was unreachable and nothing errored.
            rows: list[dict] = []
            offset = 0
            while offset < days:
                take = min(_HISTORY_PAGE_SIZE, days - offset)
                page_res = await async_execute(
                    lambda c, o=offset, t=take: (
                        c.table("psx_ohlcv")
                        .select("*")
                        .eq("symbol", sym)
                        .order("date", desc=True)
                        .range(o, o + t - 1)
                    )
                )
                batch = page_res.data or []
                rows.extend(batch)
                if len(batch) < take:
                    break  # exhausted this symbol's history
                offset += take

            if rows:
                return [_row_to_bar(r) for r in rows]
        except Exception:
            log.warning("cache_history_read_failed", symbol=sym, exc_info=True)

        # Cache miss: only the worker scrapes. Web returns empty (fast).
        if not self.live_scrape:
            return []
        bars = await self.dps.fetch_historical(sym)
        if bars:
            rows = [b.to_dict() for b in bars]
            try:
                await async_execute(lambda c: c.table("psx_ohlcv").upsert(rows, on_conflict="symbol,date"))
            except Exception:
                log.warning("cache_history_write_failed", symbol=sym, exc_info=True)
        return bars[-days:] if len(bars) > days else bars

    # ---------- symbols ----------

    async def get_symbols(self, max_age_seconds: int = 86400) -> list[SymbolInfo]:
        try:
            rows = await select_all(
                "psx_profile", "symbol,name,sector,logoid,refreshed_at", order_by="symbol"
            )
            if rows:
                newest = max((r.get("refreshed_at") or "" for r in rows), default="")
                stale = True
                if newest:
                    last_refresh = datetime.fromisoformat(newest.replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - last_refresh).total_seconds()
                    stale = age >= max_age_seconds
                if stale:
                    self._refresh_in_background("symbols", self._scrape_symbols)
                return [
                    SymbolInfo(
                        symbol=r["symbol"],
                        name=r.get("name", ""),
                        sector=r.get("sector"),
                        logoid=r.get("logoid"),
                    )
                    for r in rows
                ]
        except Exception:
            log.warning("cache_symbols_read_failed", exc_info=True)

        # Nothing cached: web process returns empty rather than blocking on DPS.
        if not self.live_scrape:
            return []
        return await self._scrape_symbols()

    async def _scrape_symbols(self) -> list[SymbolInfo]:
        symbols = await self.dps.fetch_symbols()
        if symbols:
            rows = [
                {
                    "symbol": s.symbol,
                    "name": s.name,
                    "sector": s.sector,
                    "refreshed_at": datetime.now(timezone.utc).isoformat(),
                }
                for s in symbols
            ]
            try:
                await async_execute(lambda c: c.table("psx_profile").upsert(rows, on_conflict="symbol"))
            except Exception:
                log.warning("cache_symbols_write_failed", exc_info=True)
        return symbols

    # ---------- profile ----------

    async def get_profile(self, symbol: str, max_age_seconds: int = 604800) -> Optional[CompanyProfile]:
        """Company profile. Same rule as `get_fundamentals`: stale is still served.

        The 7-day window used to sit against a weekly writer, so a run that
        slipped by even an hour turned every profile into a 404 on the web
        process. Only a genuinely absent row is a miss now.
        """
        sym = symbol.upper()
        try:
            result = await async_execute(lambda c: c.table("psx_profile").select("*").eq("symbol", sym))
            rows = result.data or []
            if rows:
                r = rows[0]
                if self._is_stale(r.get("refreshed_at"), max_age_seconds):
                    self._refresh_in_background(
                        f"profile:{sym}", lambda: self._scrape_profile(sym)
                    )
                return CompanyProfile(
                    symbol=r["symbol"],
                    name=r.get("name", ""),
                    sector=r.get("sector"),
                    listed_shares=r.get("listed_shares"),
                    free_float=r.get("free_float"),
                )
        except Exception:
            log.warning("cache_profile_read_failed", symbol=sym, exc_info=True)

        if not self.live_scrape:
            return None
        return await self._scrape_profile(sym)

    async def _scrape_profile(self, sym: str) -> CompanyProfile:
        profile = await self.dps.fetch_profile(sym)
        try:
            await async_execute(lambda c: c.table("psx_profile").upsert({
                "symbol": profile.symbol,
                "name": profile.name,
                "sector": profile.sector,
                "listed_shares": profile.listed_shares,
                "free_float": profile.free_float,
                "refreshed_at": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="symbol"))
        except Exception:
            log.warning("cache_profile_write_failed", symbol=sym, exc_info=True)
        return profile

    # ---------- fundamentals ----------

    async def get_fundamentals(self, symbol: str, max_age_seconds: int = 86400) -> FundamentalsData:
        """Fundamentals for one symbol. A stale row is served, never discarded.

        `max_age_seconds` schedules a background refresh; it does NOT decide
        whether the caller gets data. Treating "stale" as "missing" is what broke
        this endpoint: the only writer (`job_refresh_fundamentals`) runs WEEKLY,
        the window here is one day, and on the web process `live_scrape` is False
        — so for six days out of seven every symbol fell through to the empty
        `FundamentalsData(symbol=sym)` below and the whole site rendered blank
        P/E, EPS and dividend yield while the real values sat in the table.
        `get_symbols`/`get_market_snapshot` already had it right; this now
        matches them. A day-old P/E is useful; a null one is not.
        """
        sym = symbol.upper()
        try:
            result = await async_execute(lambda c: c.table("psx_fundamentals").select("*").eq("symbol", sym))
            rows = result.data or []
            if rows:
                r = rows[0]
                if self._is_stale(r.get("refreshed_at"), max_age_seconds):
                    self._refresh_in_background(
                        f"fundamentals:{sym}", lambda: self._scrape_fundamentals(sym)
                    )
                return FundamentalsData(
                    symbol=sym,
                    eps=r.get("eps"),
                    pe=r.get("pe"),
                    pb=r.get("pb"),
                    div_yield=r.get("div_yield"),
                    payout=r.get("payout"),
                    roe=r.get("roe"),
                )
        except Exception:
            log.warning("cache_fundamentals_read_failed", symbol=sym, exc_info=True)

        # Genuinely nothing cached for this symbol: only the worker scrapes.
        if not self.live_scrape:
            return FundamentalsData(symbol=sym)
        return await self._scrape_fundamentals(sym)

    async def _scrape_fundamentals(self, sym: str) -> FundamentalsData:
        fundamentals = await self.dps.fetch_fundamentals(sym)
        try:
            await async_execute(lambda c: c.table("psx_fundamentals").upsert({
                "symbol": sym,
                "eps": fundamentals.eps,
                "pe": fundamentals.pe,
                "pb": fundamentals.pb,
                "div_yield": fundamentals.div_yield,
                "payout": fundamentals.payout,
                "roe": fundamentals.roe,
                "refreshed_at": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="symbol"))
        except Exception:
            log.warning("cache_fundamentals_write_failed", symbol=sym, exc_info=True)
        return fundamentals

    # ---------- batch helpers (screener) ----------

    async def get_histories_batch(self, symbols: list[str], days: int = 200) -> dict[str, list[OHLCVBar]]:
        syms = [s.upper() for s in symbols]
        try:
            bars_result = await async_execute(
                lambda c: (
                    c.table("psx_ohlcv")
                    .select("*")
                    .in_("symbol", syms)
                    .order("date", desc=True)
                )
            )
            rows = bars_result.data or []
            grouped: dict[str, list[OHLCVBar]] = {}
            for r in rows:
                sym = r["symbol"]
                if sym not in grouped:
                    grouped[sym] = []
                grouped[sym].append(_row_to_bar(r))
            return grouped
        except Exception:
            log.warning("cache_histories_batch_read_failed", exc_info=True)

        result: dict[str, list[OHLCVBar]] = {}
        for sym in symbols:
            result[sym] = await self.get_history(sym, days)
        return result

    async def get_fundamentals_batch(self, symbols: list[str]) -> dict[str, Optional[FundamentalsData]]:
        syms = [s.upper() for s in symbols]
        try:
            result = await async_execute(
                lambda c: c.table("psx_fundamentals").select("*").in_("symbol", syms)
            )
            rows = result.data or []
            grouped: dict[str, FundamentalsData] = {}
            for r in rows:
                sym = r["symbol"]
                grouped[sym] = FundamentalsData(
                    symbol=sym,
                    eps=r.get("eps"),
                    pe=r.get("pe"),
                    pb=r.get("pb"),
                    div_yield=r.get("div_yield"),
                    payout=r.get("payout"),
                    roe=r.get("roe"),
                )
            return grouped
        except Exception:
            log.warning("cache_fundamentals_batch_read_failed", exc_info=True)

        result: dict[str, Optional[FundamentalsData]] = {}
        for sym in symbols:
            result[sym] = await self.get_fundamentals(sym)
        return result

    # ---------- announcements ----------

    async def get_announcements(self, symbol: str | None = None, limit: int = 50, max_age_seconds: int = 900) -> list[AnnouncementItem]:
        """Latest announcements. Stale rows are served, not dropped.

        Two fixes over the previous shape:

        1. The 15-minute window was checked against a writer on a 15-minute
           interval, so any run that slipped by a second made this return `[]`
           on the web process — an empty feed rather than slightly old news.
        2. It issued a separate "newest refreshed_at" probe query before the
           real one, paying two DB round trips per request. The rows already
           carry `refreshed_at`, so one query answers both questions.
        """
        try:
            def _q(c):
                q = c.table("psx_announcements").select("*").order("posted_at", desc=True).limit(limit)
                if symbol:
                    q = q.eq("symbol", symbol.upper())
                return q

            result = await async_execute(_q)
            rows = result.data or []
            if rows:
                newest = max((r.get("refreshed_at") or "" for r in rows), default="")
                if self._is_stale(newest, max_age_seconds):
                    self._refresh_in_background(
                        "announcements", lambda: self._scrape_announcements(limit)
                    )
                return [
                    AnnouncementItem(
                        id=r["id"],
                        symbol=r.get("symbol"),
                        posted_at=datetime.fromisoformat(r["posted_at"].replace("Z", "+00:00")),
                        title=r.get("title", ""),
                        category=r.get("category"),
                        url=r.get("url"),
                    )
                    for r in rows
                ]
        except Exception:
            log.warning("cache_announcements_read_failed", exc_info=True)

        if not self.live_scrape:
            return []
        return await self._scrape_announcements(limit)

    async def _scrape_announcements(self, limit: int = 50) -> list[AnnouncementItem]:
        items = await self.dps.fetch_announcements(offset=0, count=limit)
        if items:
            rows = [
                {
                    "id": item.id,
                    "symbol": item.symbol,
                    "posted_at": item.posted_at.isoformat() if hasattr(item.posted_at, "isoformat") else item.posted_at,
                    "title": item.title,
                    "category": item.category,
                    "url": item.url,
                    "refreshed_at": datetime.now(timezone.utc).isoformat(),
                }
                for item in items
            ]
            try:
                await async_execute(lambda c: c.table("psx_announcements").upsert(rows, on_conflict="id"))
            except Exception:
                log.warning("cache_announcements_write_failed", exc_info=True)
        return items[:limit]

    # ---------- dividends ----------

    async def get_dividends(self, symbol: str, max_age_seconds: int = 86400) -> list[DividendEvent]:
        sym = symbol.upper()
        try:
            result = await async_execute(lambda c: c.table("psx_dividends").select("*").eq("symbol", sym).order("ex_date", desc=True))
            rows = result.data or []
            if rows:
                return [
                    DividendEvent(
                        announcement_id=r["announcement_id"],
                        symbol=r["symbol"],
                        ex_date=_parse_iso_date(r.get("ex_date")),
                        announcement_date=_parse_iso_date(r.get("announcement_date")),
                        payout_type=r.get("payout_type", ""),
                        per_share=r.get("per_share"),
                        bonus_pct=r.get("bonus_pct"),
                    )
                    for r in rows
                ]
        except Exception:
            log.warning("cache_dividends_read_failed", symbol=sym, exc_info=True)

        if not self.live_scrape:
            return []
        events = await self.dps.fetch_payouts(sym)
        if events:
            rows = [
                {
                    "announcement_id": e.announcement_id,
                    "symbol": e.symbol,
                    "ex_date": e.ex_date.isoformat() if hasattr(e.ex_date, "isoformat") else e.ex_date,
                    "announcement_date": e.announcement_date.isoformat() if hasattr(e.announcement_date, "isoformat") else e.announcement_date,
                    "payout_type": e.payout_type,
                    "per_share": e.per_share,
                    "bonus_pct": e.bonus_pct,
                    "refreshed_at": datetime.now(timezone.utc).isoformat(),
                }
                for e in events
            ]
            try:
                await async_execute(lambda c: c.table("psx_dividends").upsert(rows, on_conflict="announcement_id"))
            except Exception:
                log.warning("cache_dividends_write_failed", symbol=sym, exc_info=True)
        return events

    # ---------- index EOD ----------

    async def get_index_eod(self, code: str, max_age_seconds: int = 3600) -> list[IndexBar]:
        c = code.upper()
        try:
            result = await async_execute(lambda q: q.table("psx_index_eod").select("*").eq("code", c).order("date", desc=True))
            rows = result.data or []
            if rows:
                bars = [_row_to_index_bar(r) for r in rows]
                if (
                    _index_bars_are_fresh(bars)
                    or not self.live_scrape
                    or not self._can_refresh_now(f"index:{c}")
                ):
                    return bars
                refreshed = await self._scrape_index_eod(c)
                return refreshed or bars
        except Exception:
            log.warning("cache_index_read_failed", code=c, exc_info=True)

        if not self.live_scrape:
            return []
        return await self._scrape_index_eod(c)

    async def get_live_index_snapshot(self, max_age_seconds: int = 900) -> list[dict]:
        """Read live index snapshot from DB; fall back to DPS scrape.

        The scheduler writes ``psx_index_live_snapshot`` every 5 min during
        market hours (Mon–Fri 09:00–17:00 PKT). The web process (which has
        ``live_scrape=False``) returns the scheduler's latest snapshot from
        the DB. The worker process (``live_scrape=True``) falls back to a
        direct DPS homepage scrape when the DB row is stale or missing.

        The cutoff is 900s, NOT the 300s that matches the cron interval. At 300s
        a row written at T expires at exactly T+300 — the instant the next run
        *starts*, before it has scraped DPS and written. That left a guaranteed
        dead window every single cycle where every index card silently dropped
        to the previous day's EOD close, held there for up to TTL_INDEX (60s) by
        the in-process memo. 900s absorbs two missed beats and still surfaces a
        genuinely dead scheduler within 15 minutes.
        """
        try:
            result = await async_execute(
                lambda c: c.table("psx_index_live_snapshot").select("*")
            )
            rows = result.data or []
            if rows:
                cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
                fresh: list[dict] = []
                for r in rows:
                    updated = r.get("updated_at")
                    if updated:
                        if isinstance(updated, str):
                            try:
                                updated = datetime.fromisoformat(
                                    updated.replace("Z", "+00:00")
                                )
                            except (ValueError, TypeError):
                                continue
                        if updated.tzinfo is None:
                            updated = updated.replace(tzinfo=timezone.utc)
                        if updated >= cutoff:
                            fresh.append(r)
                if fresh:
                    return fresh
        except Exception:
            log.warning("cache_live_snapshot_read_failed", exc_info=True)

        if not self.live_scrape:
            return []
        return await self.dps.fetch_index_snapshot()

    async def get_index_snapshot_any_age(self) -> list[dict]:
        """Every ``psx_index_live_snapshot`` row, with no freshness filter.

        ``get_live_index_snapshot`` discards rows past its cutoff on purpose: an
        intraday card must never present a stale tick as a live one. That rule
        stops being right once the session is over. The scheduler's last write
        of the day *is* that day's close, and after 17:10 PKT the 900s cutoff
        throws it away and the cards fall back to ``psx_index_eod`` — which,
        until the 18:00 PKT ingest lands, still holds the *previous* day. The
        result is a card that is confidently a full day wrong while the correct
        number sits unused in the database.

        Callers use this only to compare dates against an EOD bar and pick the
        later one. It never asserts liveness, so it does not fall back to a DPS
        scrape — an empty result simply means "nothing to compare against".
        """
        try:
            result = await async_execute(
                lambda c: c.table("psx_index_live_snapshot").select("*")
            )
            return result.data or []
        except Exception:
            log.warning("cache_index_snapshot_any_age_read_failed", exc_info=True)
            return []

    async def _scrape_index_eod(self, code: str) -> list[IndexBar]:
        bars = await self.dps.fetch_index_eod(code)
        if bars:
            rows = []
            for b in bars:
                row = {
                    "code": b.code,
                    "date": b.date.isoformat(),
                    "close": b.close,
                    "volume": b.volume,
                }
                if b.open is not None:
                    row["open"] = b.open
                if b.high is not None:
                    row["high"] = b.high
                if b.low is not None:
                    row["low"] = b.low
                rows.append(row)
            seen = set()
            deduped = []
            for r in rows:
                key = (r["code"], r["date"])
                if key not in seen:
                    seen.add(key)
                    deduped.append(r)
            try:
                await async_execute(lambda c: c.table("psx_index_eod").upsert(deduped, on_conflict="code,date"))
            except Exception:
                log.warning("cache_index_write_failed", code=code, exc_info=True)
        return bars

    async def get_index_latest(self, code: str, bars: int = 2) -> list[IndexBar]:
        """Newest `bars` rows for an index (date DESC) — for dashboard cards.

        Avoids pulling the full index history just to compute latest vs
        previous close. Falls back to the full path only when the table has
        no rows for the code.
        """
        c = code.upper()
        try:
            result = await async_execute(
                lambda cl: (
                    cl.table("psx_index_eod")
                    .select("*")
                    .eq("code", c)
                    .order("date", desc=True)
                    .limit(bars)
                )
            )
            rows = result.data or []
            if rows:
                latest = [_row_to_index_bar(r) for r in rows]
                if (
                    _index_bars_are_fresh(latest)
                    or not self.live_scrape
                    or not self._can_refresh_now(f"index:{c}")
                ):
                    return latest
                refreshed = await self._scrape_index_eod(c)
                newest_first = sorted(refreshed, key=lambda b: (b.date or date.min), reverse=True)
                return newest_first[:bars] or latest
        except Exception:
            log.warning("cache_index_latest_read_failed", code=c, exc_info=True)

        all_bars = await self.get_index_eod(c)
        newest_first = sorted(all_bars, key=lambda b: (b.date or date.min), reverse=True)
        return newest_first[:bars]

    def _can_refresh_now(self, key: str) -> bool:
        now = time.monotonic()
        if now - self._last_refresh_attempt.get(key, 0.0) < BACKGROUND_REFRESH_THROTTLE:
            return False
        self._last_refresh_attempt[key] = now
        return True

    # ---------- sectors ----------

    async def get_sectors(self) -> list[SectorDataItem]:
        """Build sector aggregates from cached snapshot + profile data."""
        try:
            rows = await select_all("psx_market_snapshot", "*", order_by="symbol")
            snapshot = [_row_to_market_snapshot(r) for r in rows]
        except Exception:
            snapshot = await self.dps.fetch_market_watch() if self.live_scrape else []

        sector_map: dict[str, str] = {}
        try:
            profiles = await select_all("psx_profile", "symbol,sector", order_by="symbol")
            for p in profiles:
                if p.get("symbol") and p.get("sector"):
                    sector_map[p["symbol"]] = p["sector"]
        except Exception:
            pass

        # Supplement from symbols API (worker only — web never scrapes).
        if len(sector_map) < 50 and self.live_scrape:
            try:
                symbols = await self.dps.fetch_symbols()
                for s in symbols:
                    if s.sector:
                        sector_map[s.symbol] = s.sector
            except Exception:
                pass

        sectors: dict[str, dict] = {}
        for item in snapshot:
            sector = sector_map.get(item.symbol, "Other")
            if sector not in sectors:
                sectors[sector] = {"sum_pct": 0.0, "sum_vol": 0, "sum_val": 0.0, "count": 0}
            sectors[sector]["sum_pct"] += (item.change_pct or 0)
            sectors[sector]["sum_vol"] += (item.volume or 0)
            sectors[sector]["sum_val"] += ((item.price or 0) * (item.volume or 0))
            sectors[sector]["count"] += 1

        return [
            SectorDataItem(
                name=name,
                pct=round(data["sum_pct"] / data["count"], 2) if data["count"] else 0,
                volume=data["sum_vol"],
                value=data["sum_val"],
            )
            for name, data in sorted(sectors.items())
        ]


# ---------- helpers ----------

def _row_to_market_snapshot(r: dict) -> MarketSnapshotItem:
    return MarketSnapshotItem(
        symbol=r["symbol"],
        price=r.get("price"),
        change=r.get("change"),
        change_pct=r.get("change_pct"),
        volume=r.get("volume", 0),
        day_high=r.get("day_high"),
        day_low=r.get("day_low"),
    )


def _row_to_bar(r: dict) -> OHLCVBar:
    return OHLCVBar(
        symbol=r["symbol"],
        date=_parse_iso_date(r["date"]),
        open=r.get("open", 0),
        high=r.get("high", 0),
        low=r.get("low", 0),
        close=r.get("close", 0),
        volume=r.get("volume", 0),
    )


def _row_to_index_bar(r: dict) -> IndexBar:
    close = r.get("close") or 0
    return IndexBar(
        code=r["code"],
        date=_parse_iso_date(r["date"]),
        open=r.get("open"),
        high=r.get("high"),
        low=r.get("low"),
        close=close,
        volume=r.get("volume"),
    )


def _index_bars_are_fresh(bars: list[IndexBar]) -> bool:
    latest = max((b.date for b in bars if b.date is not None), default=None)
    if latest is None:
        return False
    return latest >= _expected_latest_index_date()


def _expected_latest_index_date(now: datetime | None = None) -> date:
    current = now.astimezone(_PSX_TZ) if now else datetime.now(_PSX_TZ)
    expected = current.date()
    if current.weekday() >= 5:
        return _previous_weekday(expected)
    minutes = current.hour * 60 + current.minute
    if minutes < _INDEX_EOD_CUTOFF_MINUTES:
        return _previous_weekday(expected)
    return expected


def _previous_weekday(value: date) -> date:
    d = value - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _parse_iso_date(v) -> Optional[date]:
    from datetime import date as _date
    if v is None:
        return None
    if isinstance(v, _date):
        return v
    try:
        return _date.fromisoformat(str(v)[:10])
    except (ValueError, TypeError):
        return None
