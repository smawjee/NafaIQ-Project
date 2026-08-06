"""Backfill the PSX company-announcement archive.

`psx_announcements` holds ~26 days of history because `job_refresh_announcements`
only ever reads offset 0. The archive itself is deep — probing
`/announcements?type=C` reaches 2025-06-30 by offset 20,000 and keeps going, so
~18,500 announcements a year and roughly 185,000 for a decade.

Why this matters twice over:

1. **PEAD.** Point-in-time earnings dates are the one piece of orthogonal
   information the price series does not contain, and the closed research log
   names it as the only route back to a model.
2. **Corporate actions.** DPS `/company/payouts` serves only a rolling ~18-month
   window of *cash* dividends — no bonus, no rights, nothing before 2025-03
   (verified by `scripts/signals/probe_payouts.py`). The announcement archive
   does carry them ("Credit of Bonus Shares", "Book Closure to Determine Right
   Issue Entitlement"). Having a *confirmed* action on a specific date is what
   makes adjusting a price gap an attribution rather than a guess — which is
   precisely the objection that kept the price-gap detector off the product path.

Writes: idempotent `upsert(on_conflict="id")` into `psx_announcements`, exactly
the same shape `job_refresh_announcements` already writes. Adds only older rows,
so every consumer (all of which order by `posted_at desc` and limit) is
unaffected. Re-running is safe; a checkpoint file makes it resumable.

    python scripts/signals/backfill_announcements.py [--max-offset N] [--since YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.db.supabase import async_execute  # noqa: E402
from app.scrapers.dps import DPSScraper  # noqa: E402

ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "signals"
CHECKPOINT = ARTIFACT_DIR / "backfill_announcements_checkpoint.json"

PAGE = 50                 # rows per request (the endpoint's natural page size)
FLUSH_EVERY = 20          # pages buffered before a write
DELAY_SECONDS = 0.35      # politeness between requests
DEFAULT_SINCE = date(2016, 1, 1)
DEFAULT_MAX_OFFSET = 400_000
EMPTY_PAGES_TO_STOP = 3   # tolerate a transient blank page before concluding


async def _known_symbols() -> set[str]:
    """Equity symbols we actually track.

    The feed is heavily diluted with mutual-fund notices (daily NAV
    distributions from MCBIM-FUNDS and friends). Those are not PSX equities,
    carry no signal for this work, and would triple the row count.
    """
    res = await async_execute(lambda c: c.table("psx_profile").select("symbol"))
    return {str(r["symbol"]).upper() for r in (res.data or []) if r.get("symbol")}


def _load_checkpoint() -> dict:
    try:
        return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_checkpoint(offset: int, written: int, oldest: str | None) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_bytes(json.dumps(
        {"next_offset": offset, "written": written, "oldest_seen": oldest,
         "updated_at": datetime.now(timezone.utc).isoformat()},
        indent=2).encode("utf-8"))


async def _flush(buffer: list[dict]) -> int:
    """Upsert a batch, de-duplicated by id.

    Postgres rejects an entire ON CONFLICT batch with 21000 when two proposed
    rows share the conflict target, and the feed does repeat ids across page
    boundaries — so dedupe here rather than lose the batch.
    """
    if not buffer:
        return 0
    by_id = {row["id"]: row for row in buffer}
    rows = list(by_id.values())
    await async_execute(
        lambda c, r=rows: c.table("psx_announcements").upsert(r, on_conflict="id")
    )
    return len(rows)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-offset", type=int, default=DEFAULT_MAX_OFFSET)
    ap.add_argument("--since", type=str, default=DEFAULT_SINCE.isoformat(),
                    help="stop once the feed reaches dates older than this")
    ap.add_argument("--restart", action="store_true", help="ignore the checkpoint")
    args = ap.parse_args()

    since = date.fromisoformat(args.since)
    checkpoint = {} if args.restart else _load_checkpoint()
    offset = int(checkpoint.get("next_offset", 0))
    written = int(checkpoint.get("written", 0))

    print(f"  backfilling psx_announcements from offset {offset}, floor {since}")

    symbols = await _known_symbols()
    print(f"  {len(symbols)} tracked equity symbols (feed is filtered to these)")

    scraper = DPSScraper()
    buffer: list[dict] = []
    pages = 0
    empty_streak = 0
    oldest_seen: str | None = checkpoint.get("oldest_seen")
    skipped_unknown = 0

    try:
        while offset < args.max_offset:
            try:
                items = await scraper.fetch_announcements(offset=offset, count=PAGE)
            except Exception as exc:
                print(f"  offset {offset}: {type(exc).__name__}: {exc} — retrying once")
                await asyncio.sleep(3)
                try:
                    items = await scraper.fetch_announcements(offset=offset, count=PAGE)
                except Exception as exc2:
                    print(f"  offset {offset}: failed twice ({exc2}); stopping")
                    break

            if not items:
                empty_streak += 1
                if empty_streak >= EMPTY_PAGES_TO_STOP:
                    print(f"  offset {offset}: archive exhausted")
                    break
                offset += PAGE
                continue
            empty_streak = 0

            page_oldest: date | None = None
            for item in items:
                posted = getattr(item, "posted_at", None)
                if posted is not None:
                    d = posted.date() if hasattr(posted, "date") else posted
                    page_oldest = d if page_oldest is None or d < page_oldest else page_oldest

                sym = (getattr(item, "symbol", "") or "").upper()
                if sym not in symbols:
                    skipped_unknown += 1
                    continue
                buffer.append({
                    "id": item.id,
                    "symbol": sym,
                    "posted_at": posted.isoformat() if posted else None,
                    "title": getattr(item, "title", None),
                    "category": getattr(item, "category", None),
                    "url": getattr(item, "url", None),
                    "refreshed_at": datetime.now(timezone.utc).isoformat(),
                })

            if page_oldest is not None:
                oldest_seen = page_oldest.isoformat()

            pages += 1
            offset += PAGE

            if pages % FLUSH_EVERY == 0:
                written += await _flush(buffer)
                buffer.clear()
                _save_checkpoint(offset, written, oldest_seen)
                print(f"  offset {offset:>7} | oldest {oldest_seen} | "
                      f"written {written:>7,} | skipped(non-equity) {skipped_unknown:,}")

            if page_oldest is not None and page_oldest < since:
                print(f"  reached floor {since} at offset {offset}")
                break

            await asyncio.sleep(DELAY_SECONDS)

        written += await _flush(buffer)
        _save_checkpoint(offset, written, oldest_seen)
    finally:
        await scraper.close()

    print(f"\n  DONE: wrote {written:,} announcement rows, "
          f"skipped {skipped_unknown:,} non-equity notices")
    print(f"  oldest announcement reached: {oldest_seen}")
    print(f"  checkpoint: {CHECKPOINT}")


if __name__ == "__main__":
    asyncio.run(main())
