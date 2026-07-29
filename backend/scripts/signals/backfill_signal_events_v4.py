"""Paginate the official PSX announcement feed into point-in-time events."""
from __future__ import annotations

import asyncio
import hashlib
from datetime import timezone
from zoneinfo import ZoneInfo

from app.db.supabase import async_execute
from app.scrapers.dps import DPSScraper
from app.services.signals_v4.events import event_identity


def _event_type(category: str | None, title: str) -> str:
    text = f"{category or ''} {title}".lower()
    if "financial result" in text or "quarterly" in text or "annual report" in text:
        return "EARNINGS"
    if "dividend" in text or "payout" in text:
        return "DIVIDEND"
    if "disclosure of interest" in text or "director" in text:
        return "INSIDER"
    if "material" in text or "board meeting" in text:
        return "MATERIAL"
    return "OTHER"


async def main() -> None:
    scraper = DPSScraper()
    offset = 0
    try:
        while True:
            items = await scraper.fetch_announcements(offset=offset, count=50)
            if not items:
                break
            rows = []
            for item in items:
                if not item.symbol or not item.posted_at:
                    continue
                published = item.posted_at.replace(tzinfo=item.posted_at.tzinfo or ZoneInfo("Asia/Karachi")).astimezone(timezone.utc)
                source_hash = hashlib.sha256((item.url or item.title).encode("utf-8")).hexdigest()
                rows.append({
                    "event_id": event_identity(symbol=item.symbol, published_at=published, source_url=item.url, source_hash=source_hash),
                    "symbol": item.symbol,
                    "event_type": _event_type(item.category, item.title),
                    "title": item.title,
                    "published_at": published.isoformat(),
                    "source_url": item.url,
                    "source_hash": source_hash,
                    "facts": {},
                })
            if rows:
                await async_execute(lambda c, _rows=rows: c.table("psx_signal_events").insert(_rows))
            offset += len(items)
            print(f"events through offset {offset}")
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
