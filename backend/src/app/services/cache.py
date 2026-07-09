from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

import structlog

from app.db.supabase import get_supabase
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


class CacheLayer:
    """Read-through cache: serve from Supabase if fresh, else scrape + write."""

    def __init__(self, dps: DPSScraper):
        self.dps = dps
        self.db = get_supabase()

    # ---------- market snapshot ----------

    async def get_market_snapshot(self, max_age_seconds: int = 5) -> list[MarketSnapshotItem]:
        # Check cache freshness
        try:
            result = (
                self.db.table("psx_market_snapshot")
                .select("refreshed_at")
                .order("refreshed_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            if rows:
                last_refresh = datetime.fromisoformat(rows[0]["refreshed_at"].replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - last_refresh).total_seconds()
                if age < max_age_seconds:
                    result = self.db.table("psx_market_snapshot").select("*").execute()
                    return [_row_to_market_snapshot(r) for r in (result.data or [])]
        except Exception:
            log.warning("cache_market_read_failed", exc_info=True)

        # Cache miss: scrape + bulk write
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
                self.db.table("psx_market_snapshot").upsert(rows, on_conflict="symbol").execute()
            except Exception:
                log.warning("cache_market_write_failed", exc_info=True)
        return items

    # ---------- OHLCV history ----------

    async def get_history(self, symbol: str, days: int = 250, max_age_seconds: int = 21600) -> list[OHLCVBar]:
        sym = symbol.upper()
        try:
            bars_result = (
                self.db.table("psx_ohlcv")
                .select("*", count="exact")
                .eq("symbol", sym)
                .order("date", desc=True)
                .limit(days)
                .execute()
            )
            if bars_result.count and bars_result.count > 0:
                rows = bars_result.data or []
                if rows:
                    return [_row_to_bar(r) for r in rows]
        except Exception:
            log.warning("cache_history_read_failed", symbol=sym, exc_info=True)

        # Cache miss: scrape + bulk write
        bars = await self.dps.fetch_historical(sym)
        if bars:
            rows = [b.to_dict() for b in bars]
            try:
                self.db.table("psx_ohlcv").upsert(rows, on_conflict="symbol,date").execute()
            except Exception:
                log.warning("cache_history_write_failed", symbol=sym, exc_info=True)
        return bars[-days:] if len(bars) > days else bars

    # ---------- symbols ----------

    async def get_symbols(self, max_age_seconds: int = 86400) -> list[SymbolInfo]:
        try:
            result = (
                self.db.table("psx_profile")
                .select("refreshed_at")
                .order("refreshed_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            if rows:
                last_refresh = datetime.fromisoformat(rows[0]["refreshed_at"].replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - last_refresh).total_seconds()
                if age < max_age_seconds:
                    result = self.db.table("psx_profile").select("symbol,name,sector,logoid").execute()
                    return [
                        SymbolInfo(
                            symbol=r["symbol"],
                            name=r.get("name", ""),
                            sector=r.get("sector"),
                            logoid=r.get("logoid"),
                        )
                        for r in (result.data or [])
                    ]
        except Exception:
            log.warning("cache_symbols_read_failed", exc_info=True)

        # Cache miss: scrape symbols, bulk write
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
                self.db.table("psx_profile").upsert(rows, on_conflict="symbol").execute()
            except Exception:
                log.warning("cache_symbols_write_failed", exc_info=True)
        return symbols

    # ---------- profile ----------

    async def get_profile(self, symbol: str, max_age_seconds: int = 604800) -> Optional[CompanyProfile]:
        sym = symbol.upper()
        try:
            result = self.db.table("psx_profile").select("*").eq("symbol", sym).execute()
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
            self.db.table("psx_profile").upsert({
                "symbol": profile.symbol,
                "name": profile.name,
                "sector": profile.sector,
                "listed_shares": profile.listed_shares,
                "free_float": profile.free_float,
                "refreshed_at": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="symbol").execute()
        except Exception:
            pass
        return profile

    # ---------- fundamentals ----------

    async def get_fundamentals(self, symbol: str, max_age_seconds: int = 86400) -> FundamentalsData:
        sym = symbol.upper()
        try:
            result = self.db.table("psx_fundamentals").select("*").eq("symbol", sym).execute()
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
            self.db.table("psx_fundamentals").upsert({
                "symbol": sym,
                "eps": fundamentals.eps,
                "pe": fundamentals.pe,
                "pb": fundamentals.pb,
                "div_yield": fundamentals.div_yield,
                "payout": fundamentals.payout,
                "roe": fundamentals.roe,
                "refreshed_at": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="symbol").execute()
        except Exception:
            pass
        return fundamentals

    # ---------- announcements ----------

    async def get_announcements(self, symbol: str | None = None, limit: int = 50, max_age_seconds: int = 900) -> list[AnnouncementItem]:
        try:
            result = (
                self.db.table("psx_announcements")
                .select("refreshed_at")
                .order("refreshed_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            if rows:
                last_refresh = datetime.fromisoformat(rows[0]["refreshed_at"].replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - last_refresh).total_seconds()
                if age < max_age_seconds:
                    query = self.db.table("psx_announcements").select("*").order("posted_at", desc=True).limit(limit)
                    if symbol:
                        query = query.eq("symbol", symbol.upper())
                    result = query.execute()
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
                    "posted_at": item.posted_at,
                    "title": item.title,
                    "category": item.category,
                    "url": item.url,
                    "refreshed_at": datetime.now(timezone.utc).isoformat(),
                }
                for item in items
            ]
            try:
                self.db.table("psx_announcements").upsert(rows, on_conflict="id").execute()
            except Exception:
                log.warning("cache_announcements_write_failed", exc_info=True)
        return items[:limit]

    # ---------- dividends ----------

    async def get_dividends(self, symbol: str, max_age_seconds: int = 86400) -> list[DividendEvent]:
        sym = symbol.upper()
        try:
            result = self.db.table("psx_dividends").select("*").eq("symbol", sym).order("ex_date", desc=True).execute()
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
                    "ex_date": e.ex_date,
                    "announcement_date": e.announcement_date,
                    "payout_type": e.payout_type,
                    "per_share": e.per_share,
                    "bonus_pct": e.bonus_pct,
                    "refreshed_at": datetime.now(timezone.utc).isoformat(),
                }
                for e in events
            ]
            try:
                self.db.table("psx_dividends").upsert(rows, on_conflict="announcement_id").execute()
            except Exception:
                log.warning("cache_dividends_write_failed", symbol=sym, exc_info=True)
        return events

    # ---------- index EOD ----------

    async def get_index_eod(self, code: str, max_age_seconds: int = 3600) -> list[IndexBar]:
        c = code.upper()
        try:
            result = self.db.table("psx_index_eod").select("*").eq("code", c).order("date", desc=True).execute()
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
                self.db.table("psx_index_eod").upsert(deduped, on_conflict="code,date").execute()
            except Exception:
                log.warning("cache_index_write_failed", code=c, exc_info=True)
        return bars

    # ---------- sectors ----------

    async def get_sectors(self) -> list[SectorDataItem]:
        """Build sector aggregates from cached snapshot + profile data."""
        try:
            result = self.db.table("psx_market_snapshot").select("*").execute()
            snapshot = [_row_to_market_snapshot(r) for r in (result.data or [])]
        except Exception:
            snapshot = await self.dps.fetch_market_watch()

        sector_map: dict[str, str] = {}
        try:
            profiles = self.db.table("psx_profile").select("symbol,sector").execute()
            for p in (profiles.data or []):
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
