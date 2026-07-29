"""Archive every official PSX announcement PDF for V4 research.

This is intentionally separate from the 15-minute product refresh, which is
bounded for latency. It paginates the DPS archive and writes the existing
filings shape; event rows remain point-in-time metadata and never contain PDF
text in live prediction objects.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from datetime import datetime, timezone

from app.db.supabase import async_execute
from app.scrapers.dps import DPSScraper
from app.scrapers.pdf_fetcher import PDFFetcher


async def main() -> None:
    dps = DPSScraper()
    pdfs = PDFFetcher()
    offset = 0
    archived = 0
    try:
        while True:
            items = await dps.fetch_announcements(offset=offset, count=50)
            if not items:
                break
            rows: list[dict] = []
            for item in items:
                url = item.url
                if not url or not url.lower().endswith(".pdf"):
                    continue
                dest = tempfile.mktemp(suffix=".pdf")
                try:
                    ok, text, page_count = await pdfs.process_url(url, dest)
                    if not ok or not text:
                        continue
                    with open(dest, "rb") as handle:
                        document_hash = hashlib.sha256(handle.read()).hexdigest()
                    rows.append({
                        "announcement_id": item.id,
                        "symbol": item.symbol,
                        "type": "PSX_ANNOUNCEMENT",
                        "filed_at": item.posted_at.date().isoformat() if item.posted_at else None,
                        "pdf_url": url,
                        "text_content": text,
                        "page_count": page_count,
                        "refreshed_at": datetime.now(timezone.utc).isoformat(),
                        "document_hash": document_hash,
                    })
                finally:
                    try:
                        os.unlink(dest)
                    except FileNotFoundError:
                        pass
            if rows:
                await async_execute(lambda c, _rows=rows: c.table("filings").upsert(_rows, on_conflict="announcement_id"))
                archived += len(rows)
            offset += len(items)
            print(f"archive offset {offset}; PDFs archived {archived}")
    finally:
        await dps.close()
        await pdfs.close()


if __name__ == "__main__":
    asyncio.run(main())
