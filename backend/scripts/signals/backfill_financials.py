"""Full financials backfill for every profiled PSX symbol.

Reads dps.psx.com.pk company pages (the fixed FinancialsPSXScraper) and upserts
annual + quarterly income into psx_financials_annual / _quarterly. Idempotent:
re-running upserts in place. Bounded concurrency; special instruments that
return DPS 500s are skipped and reported, never fatal.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.db.supabase import async_execute, select_all
from app.scrapers.financials_psx import FinancialsPSXScraper

CONCURRENCY = 4


async def main() -> None:
    profiles = await select_all("psx_profile", "symbol", order_by="symbol")
    symbols = [str(r["symbol"]).upper() for r in profiles if r.get("symbol")]
    scraper = FinancialsPSXScraper()
    now_iso = datetime.now(timezone.utc).isoformat()
    sem = asyncio.Semaphore(CONCURRENCY)
    stats = {"annual": 0, "quarterly": 0, "with_data": 0, "empty": 0, "done": 0}

    async def one(sym: str) -> None:
        async with sem:
            try:
                annual, quarterly = await scraper.fetch_financials(sym)
            except Exception:
                annual, quarterly = [], []
            try:
                if annual:
                    await async_execute(lambda c, _p=[{**r, "refreshed_at": now_iso} for r in annual]:
                                        c.table("psx_financials_annual").upsert(_p, on_conflict="symbol,year"))
                    stats["annual"] += len(annual)
                if quarterly:
                    await async_execute(lambda c, _p=[{**r, "refreshed_at": now_iso} for r in quarterly]:
                                        c.table("psx_financials_quarterly").upsert(_p, on_conflict="symbol,period"))
                    stats["quarterly"] += len(quarterly)
                stats["with_data" if (annual or quarterly) else "empty"] += 1
            except Exception as e:
                stats["errors"] = stats.get("errors", 0) + 1
                if len(stats.setdefault("error_syms", [])) < 15:
                    stats["error_syms"].append(f"{sym}:{str(e)[:60]}")
            stats["done"] += 1
            if stats["done"] % 100 == 0:
                print(f"  {stats['done']}/{len(symbols)}  annual={stats['annual']} quarterly={stats['quarterly']} "
                      f"empty={stats['empty']} errors={stats.get('errors', 0)}", flush=True)

    try:
        await asyncio.gather(*(one(s) for s in symbols))
    finally:
        await scraper.close()

    print(f"DONE symbols={len(symbols)} with_data={stats['with_data']} empty={stats['empty']} "
          f"annual_rows={stats['annual']} quarterly_rows={stats['quarterly']} errors={stats.get('errors', 0)}", flush=True)
    if stats.get("error_syms"):
        print("sample errors:", stats["error_syms"], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
