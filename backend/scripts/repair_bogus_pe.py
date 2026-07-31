"""Null out the fabricated P/E values in psx_fundamentals.

Background
----------
`DPSScraper.fetch_fundamentals` extracted numbers with an UNBOUNDED regex:

    {label}[^0-9-]*(-?\\d+(\\.\\d+)?)

`[^0-9-]*` will happily consume hundreds of characters, so when a metric was
simply absent from the DPS company page the pattern did not fail — it kept
scanning and returned the next unrelated digit it found further down the page.

The result, measured against production on 2026-07-29:

    pe == 1.00 exactly ......... 387 of 758 rows (51% of the market)
    pe <= 1 (all artifacts) .... 399 rows

These are not valuations. ZHCM was stored at pe=0.01 with eps=7.08 — that
implies a 7-paisa share price. DLL at pe=0.23 with eps=288.2. A P/E at or below
1 does not occur on the PSX; every one of these is the stray-digit artifact.

This mattered more after the fundamentals cache fix (services/cache.py), which
stopped discarding stale rows — the bogus numbers went from "hidden behind an
all-null response" to "rendered on the stock page as fact".

The scraper is fixed (bounded gap + an explicit `pe <= 1 -> None` guard), so
`job_refresh_fundamentals` will overwrite these on its next Saturday run. This
script exists to repair them NOW rather than serving wrong valuations until then.

Usage (from backend/):
    python -m scripts.repair_bogus_pe            # dry run, writes nothing
    python -m scripts.repair_bogus_pe --apply    # perform the update

Safe to re-run: it only nulls `pe` on rows where `pe <= 1`, and touches no other
column. Nulling is the correct repair — "unknown" is honest, a fabricated 1.00
is not.
"""
from __future__ import annotations

import argparse
import asyncio

from app.db.supabase import async_execute

# A P/E at or below this is treated as the scraper artifact, not a valuation.
# Kept in sync with the guard in DPSScraper.fetch_fundamentals.
BOGUS_PE_CEILING = 1.0


async def _affected() -> list[dict]:
    result = await async_execute(
        lambda c: c.table("psx_fundamentals")
        .select("symbol,pe,eps")
        .lte("pe", BOGUS_PE_CEILING)
        .order("pe")
    )
    return result.data or []


async def main(apply: bool) -> int:
    rows = await _affected()
    if not rows:
        print("Nothing to repair — no psx_fundamentals row has pe <= "
              f"{BOGUS_PE_CEILING}.")
        return 0

    exact_one = sum(1 for r in rows if float(r["pe"]) == 1.0)
    print(f"{len(rows)} rows carry a fabricated P/E (pe <= {BOGUS_PE_CEILING}).")
    print(f"  of which exactly 1.00: {exact_one}")
    print("  sample:")
    for r in rows[:10]:
        print(f"    {r['symbol']:8} pe={r['pe']:<6} eps={r['eps']}")

    if not apply:
        # Plain ASCII: this prints to a Windows console under cp1252, where an
        # em dash renders as a replacement character.
        print("\nDry run - nothing written. Re-run with --apply to null these.")
        return 0

    await async_execute(
        lambda c: c.table("psx_fundamentals")
        .update({"pe": None})
        .lte("pe", BOGUS_PE_CEILING)
    )
    remaining = await _affected()
    print(f"\nDone. Nulled {len(rows) - len(remaining)} P/E values; "
          f"{len(remaining)} remain.")
    return 0 if not remaining else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="perform the update (default is a dry run)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.apply)))
