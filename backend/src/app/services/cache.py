from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timezone
from typing import Awaitable, Callable, Optional

import structlog

from app.db.supabase import async_execute, get_supabase, select_all
from app.scrapers.dps import DPSScraper
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

    def _refresh_in_background(self, key: str, refresh: Callable[[], Awaitable[object]]) -> None:
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

        # Nothing cached at all: a live scrape is the only option.
        return await self._scrape_market_snapshot()

    async def _scrape_market_snapshot(self) -> list[MarketSnapshotItem]:
        items = await self.dps.fetch_market_watch()
        if items:
            rows = [
                {
                    "symbol": i.symbol,
                    "price": i.price,
                    "change": i.change,
                    "change_pct": i.change_pct,
                    "volume": i.volume,
                    "day_high": i.day_high,
                    "day_low": i.day_low,
                    "refreshed_at": datetime.now(timezone.utc).isoformat(),
                }
                for i in items
            ]
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

        # Cache miss: scrape + bulk write
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

        # Nothing cached at all: a live scrape is the only option.
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
        sym = symbol.upper()
        try:
            result = await async_execute(lambda c: c.table("psx_profile").select("*").eq("symbol", sym))
            rows = result.data or []
            if rows:
                r = rows[0]
                last_refresh = datetime.fromisoformat(r["refreshed_at"].replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - last_refresh).total_seconds()
                if age < max_age_seconds:
                    return CompanyProfile(
                        symbol=r["symbol"],
                        name=r.get("name", ""),
                        sector=r.get("sector"),
                        listed_shares=r.get("listed_shares"),
                        free_float=r.get("free_float"),
                    )
        except Exception:
            log.warning("cache_profile_read_failed", symbol=sym, exc_info=True)

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
            pass
        return profile

    # ---------- fundamentals ----------

    async def get_fundamentals(self, symbol: str, max_age_seconds: int = 86400) -> FundamentalsData:
        sym = symbol.upper()
        try:
            result = await async_execute(lambda c: c.table("psx_fundamentals").select("*").eq("symbol", sym))
            rows = result.data or []
            if rows:
                r = rows[0]
                last_refresh = datetime.fromisoformat(r["refreshed_at"].replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - last_refresh).total_seconds()
                if age < max_age_seconds:
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
            pass
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
        try:
            result = await async_execute(
                lambda c: (
                    c.table("psx_announcements")
                    .select("refreshed_at")
                    .order("refreshed_at", desc=True)
                    .limit(1)
                )
            )
            rows = result.data or []
            if rows:
                last_refresh = datetime.fromisoformat(rows[0]["refreshed_at"].replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - last_refresh).total_seconds()
                if age < max_age_seconds:
                    def _q(c):
                        q = c.table("psx_announcements").select("*").order("posted_at", desc=True).limit(limit)
                        if symbol:
                            q = q.eq("symbol", symbol.upper())
                        return q
                    result = await async_execute(_q)
                    return [
                        AnnouncementItem(
                            id=r["id"],
                            symbol=r.get("symbol"),
                            posted_at=datetime.fromisoformat(r["posted_at"].replace("Z", "+00:00")),
                            title=r.get("title", ""),
                            category=r.get("category"),
                            url=r.get("url"),
                        )
                        for r in (result.data or [])
                    ]
        except Exception:
            log.warning("cache_announcements_read_failed", exc_info=True)

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
                return [
                    IndexBar(code=r["code"], date=_parse_iso_date(r["date"]), close=r["close"], volume=r.get("volume"))
                    for r in rows
                ]
        except Exception:
            log.warning("cache_index_read_failed", code=c, exc_info=True)

        bars = await self.dps.fetch_index_eod(c)
        if bars:
            rows = [
                {
                    "code": b.code,
                    "date": b.date.isoformat(),
                    "close": b.close,
                    "volume": b.volume,
                }
                for b in bars
            ]
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
                log.warning("cache_index_write_failed", code=c, exc_info=True)
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
                return [
                    IndexBar(code=r["code"], date=_parse_iso_date(r["date"]), close=r["close"], volume=r.get("volume"))
                    for r in rows
                ]
        except Exception:
            log.warning("cache_index_latest_read_failed", code=c, exc_info=True)

        all_bars = await self.get_index_eod(c)
        newest_first = sorted(all_bars, key=lambda b: (b.date or date.min), reverse=True)
        return newest_first[:bars]

    # ---------- sectors ----------

    async def get_sectors(self) -> list[SectorDataItem]:
        """Build sector aggregates from cached snapshot + profile data."""
        try:
            rows = await select_all("psx_market_snapshot", "*", order_by="symbol")
            snapshot = [_row_to_market_snapshot(r) for r in rows]
        except Exception:
            snapshot = await self.dps.fetch_market_watch()

        sector_map: dict[str, str] = {}
        try:
            profiles = await select_all("psx_profile", "symbol,sector", order_by="symbol")
            for p in profiles:
                if p.get("symbol") and p.get("sector"):
                    sector_map[p["symbol"]] = p["sector"]
        except Exception:
            pass

        # Supplement from symbols API
        if len(sector_map) < 50:
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
