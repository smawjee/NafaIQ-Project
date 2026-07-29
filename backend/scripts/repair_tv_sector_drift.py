"""Repair psx_profile.sector rows that were clobbered with TradingView buckets.

Background
----------
`psx_profile.sector` is owned by `job_refresh_fundamentals`, which writes PSX's
own classification scraped from DPS (~35 real sectors: "Commercial Banks",
"Cement", "Oil & Gas Exploration Companies"). `job_refresh_tv_data` is only a
FALLBACK for symbols DPS has no company page for; TradingView collapses PSX's
taxonomy into 18 global buckets, so it is lossy by construction — its
"Process Industries" flattens Cement, Chemicals, Paper and Textile into one.

That TV job used to overwrite the column on every 5-minute run. The code has
since been fixed to preserve an existing sector, but the rows it already
clobbered were never repaired: symbols DPS *did* classify are still sitting on
generic TV buckets. `tests/test_migrations_applied.py` asserts this can't happen
and currently fails because of that stale data.

Why `listed_shares IS NOT NULL` identifies the victims: the TV job never writes
`listed_shares` (the TV scanner has no shares-outstanding column) — it only
preserves an existing value. So a non-null `listed_shares` means
`job_refresh_fundamentals` reached DPS for that symbol, which means DPS has a
company page for it, which means it should carry a real PSX sector.

What this fixes, visibly
------------------------
`psx_profile.sector` feeds the **treemap** (`/api/market/treemap` — the sector
heatmap in the UI), `sector_averages`, and the sector map/lookup endpoints. The
separate `/api/market/heatmap` reads TradingView's live scanner directly and is
unaffected either way.

Usage (from backend/):
    python -m scripts.repair_tv_sector_drift            # dry run, writes nothing
    python -m scripts.repair_tv_sector_drift --apply    # perform the update

Safe to re-run: it only ever writes `sector` (plus `refreshed_at`) for symbols
that currently hold a TV bucket AND for which DPS returns a different, non-empty
sector. A symbol DPS can't classify is left exactly as it is.
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from app.db.supabase import async_execute, select_all
from app.scrapers.dps import DPSScraper

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("repair_sector")

def _is_tv_sourced(sector: str) -> bool:
    """True when a sector value came from TradingView rather than DPS.

    Detected by CASE, not by an allow-list. DPS returns PSX's classification in
    upper case ("COMMERCIAL BANKS", "OIL & GAS EXPLORATION COMPANIES"); every
    TradingView value is title case, whether it was translated through
    TV_SECTOR_MAP ("Process Industries") or passed through raw because the map
    had no entry for it ("Consumer Services").

    An allow-list of the 18 mapped buckets misses exactly that raw pass-through
    case — which is why one symbol survived the first repair pass and why
    tests/test_migrations_applied.py, which hardcodes those 18 names, would
    never have flagged it.
    """
    return bool(sector) and sector != sector.upper()

# DPS is scraped one company page per symbol; keep the crawl gentle.
CONCURRENCY = 4


async def find_drifted() -> list[dict]:
    """Symbols DPS classified that are currently carrying a TradingView sector."""
    rows = await select_all("psx_profile", "symbol,sector,listed_shares", order_by="symbol")
    return [
        r
        for r in rows
        if r.get("listed_shares") is not None and _is_tv_sourced(r.get("sector") or "")
    ]


async def resolve(dps: DPSScraper, symbol: str) -> str | None:
    """DPS's authoritative sector for a symbol, or None if it has no page."""
    try:
        profile = await dps.fetch_profile(symbol)
    except Exception as e:  # noqa: BLE001 — a single bad page must not abort the run
        log.warning("  %-8s DPS fetch failed: %s", symbol, e)
        return None
    return (profile.sector or "").strip() or None


async def main(apply: bool) -> int:
    drifted = await find_drifted()
    if not drifted:
        log.info("No drifted symbols — psx_profile.sector is clean.")
        return 0

    log.info("Found %d symbol(s) on a raw TradingView bucket:", len(drifted))
    for r in drifted:
        log.info("  %-8s currently %r", r["symbol"], r["sector"])

    log.info("\nResolving authoritative sectors from DPS ...")
    dps = DPSScraper()
    sem = asyncio.Semaphore(CONCURRENCY)
    planned: list[tuple[str, str, str]] = []  # (symbol, old, new)
    unresolved: list[str] = []

    async def work(row: dict) -> None:
        sym, old = row["symbol"], row["sector"]
        async with sem:
            new = await resolve(dps, sym)
        if not new:
            unresolved.append(sym)
        elif new == old:
            # DPS genuinely classifies it into a name identical to the TV
            # bucket (e.g. "Technology Services"). Not drift — leave it.
            log.info("  %-8s DPS agrees (%r) — leaving alone", sym, old)
        else:
            planned.append((sym, old, new))

    try:
        await asyncio.gather(*(work(r) for r in drifted))
    finally:
        close = getattr(dps, "close", None)
        if close:
            await close()

    log.info("\n%d symbol(s) to update:", len(planned))
    for sym, old, new in sorted(planned):
        log.info("  %-8s %-28s -> %s", sym, old, new)
    if unresolved:
        log.info(
            "\n%d symbol(s) DPS could not classify (left unchanged): %s",
            len(unresolved),
            ", ".join(sorted(unresolved)),
        )

    if not apply:
        log.info("\nDRY RUN — nothing written. Re-run with --apply to perform the update.")
        return 0

    if not planned:
        log.info("\nNothing to write.")
        return 0

    # Only the sector column is touched. Upserting a partial row on the
    # symbol conflict target leaves listed_shares / free_float / name / logoid
    # exactly as they are.
    payload = [{"symbol": sym, "sector": new} for sym, _old, new in planned]
    await async_execute(
        lambda c: c.table("psx_profile").upsert(payload, on_conflict="symbol")
    )
    log.info("\nUpdated %d row(s).", len(payload))

    remaining = await find_drifted()
    log.info("Re-check: %d symbol(s) still on a TV bucket.", len(remaining))
    if remaining:
        log.info("  %s", ", ".join(sorted(r["symbol"] for r in remaining)))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.apply)))
