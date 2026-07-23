#!/usr/bin/env python
"""Ingest daily FIPI/LIPI investor flows into psx_fipi_daily.

Default: yesterday -> today (daily job). Backfill: --from 2026-05-25 --to ...
Skips days that return no rows (weekends/holidays).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from app.repositories.market import fipi_repo
from app.scrapers.fipi import fetch_day

MIRROR_HISTORY_START = "2026-05-25"   # finhisaab's earliest data


async def _run(start: date, end: date) -> dict:
    written: dict[str, int] = {}
    d = start
    while d <= end:
        if d.weekday() < 5:              # PSX trades Mon-Fri
            rows = await fetch_day(d.isoformat())
            if rows:
                n = await fipi_repo.upsert_fipi_rows(rows)
                written[d.isoformat()] = n
            await asyncio.sleep(0.5)     # be polite to the mirror
        d += timedelta(days=1)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest FIPI/LIPI daily flows")
    parser.add_argument("--from", dest="date_from", default=None,
                        help=f"start date (backfill floor: {MIRROR_HISTORY_START})")
    parser.add_argument("--to", dest="date_to", default=None)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    today = date.today()
    start = date.fromisoformat(args.date_from) if args.date_from else today - timedelta(days=1)
    end = date.fromisoformat(args.date_to) if args.date_to else today
    written = asyncio.run(_run(start, end))
    print(json.dumps({"days_written": len(written), "total_rows": sum(written.values()),
                      "first": min(written) if written else None,
                      "last": max(written) if written else None}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
