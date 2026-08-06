"""Probe what dps.fetch_payouts actually returns, before any backfill runs.

`job_refresh_dividends` already crawls every symbol daily at 05:30 PKT using
this exact function, and `announcement_id` already carries the D/B/R type
letter, so the old primary-key collision is fixed. Yet psx_dividends holds only
897 rows, all `cash`, 196 symbols, none before 2024-11.

Either DPS does not serve deep payout history, or it does and the parser drops
it. Those have completely different fixes, and a multi-day crawl of the wrong
one is exactly the kind of wasted effort this project cannot afford again.

Read-only: fetches pages, writes nothing.

    python scripts/signals/probe_payouts.py
"""
from __future__ import annotations

import asyncio
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.scrapers.dps import DPSScraper  # noqa: E402

# Large, long-listed names; several are known bonus/rights issuers on PSX.
PROBE = ["HBL", "OGDC", "MLCF", "LUCK", "ENGRO", "TRG", "PSO", "FFC", "UBL", "MEBL"]


async def main() -> None:
    client = DPSScraper()
    try:
        print("=" * 74)
        print("1. PARSED EVENTS PER SYMBOL")
        print("=" * 74)
        totals: Counter[str] = Counter()
        oldest = None
        for sym in PROBE:
            try:
                events = await client.fetch_payouts(sym)
            except Exception as exc:
                print(f"  {sym:8s} ERROR {type(exc).__name__}: {exc}")
                continue
            by_type = Counter(e.payout_type for e in events)
            totals.update(by_type)
            dates = [e.ex_date for e in events if e.ex_date]
            if dates:
                lo = min(dates)
                oldest = lo if oldest is None or lo < oldest else oldest
            span = f"{min(dates)} -> {max(dates)}" if dates else "no ex_dates"
            print(f"  {sym:8s} n={len(events):<4} {dict(by_type)!s:40s} {span}")
            await asyncio.sleep(0.4)

        print(f"\n  TOTAL BY TYPE: {dict(totals)}")
        print(f"  OLDEST EX-DATE SEEN: {oldest}")

        print()
        print("=" * 74)
        print("2. RAW PAGE INSPECTION (HBL) — what does DPS actually serve?")
        print("=" * 74)
        html = await client._post("/company/payouts", {"symbol": "HBL"})
        print(f"  page length: {len(html):,} chars")

        # How many table rows exist at all, vs how many the parser accepted?
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        all_rows = 0
        sample: list[list[str]] = []
        for table in soup.find_all("table"):
            tbody = table.find("tbody")
            if not tbody:
                continue
            for tr in tbody.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(cells) >= 4:
                    all_rows += 1
                    if len(sample) < 12:
                        sample.append(cells[:4])
        print(f"  table rows with >=4 cells: {all_rows}")
        print("  first rows as served:")
        for row in sample:
            print(f"    {row}")

        # Which rows does the details regex reject, and why?
        details_re = re.compile(r"\s*([\d.]+)%\s*\(([^)]+)\)\s*\(([A-Z])\)\s*")
        rejected = []
        letters: Counter[str] = Counter()
        for row in sample:
            m = details_re.match(row[2])
            if m:
                letters[m.group(3).upper()] += 1
            else:
                rejected.append(row[2])
        print(f"\n  type letters found in sample: {dict(letters)}")
        if rejected:
            print("  details strings the parser REJECTS:")
            for r in rejected[:8]:
                print(f"    {r!r}")

        print()
        print("=" * 74)
        print("3. IS THERE PAGINATION / A DEEPER ARCHIVE?")
        print("=" * 74)
        for token in ("pagination", "page=", "Load More", "loadmore", "year",
                      "History", "showAll"):
            if token.lower() in html.lower():
                print(f"  found marker: {token!r}")
        if "</table>" in html:
            print(f"  tables on page: {html.count('<table')}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
