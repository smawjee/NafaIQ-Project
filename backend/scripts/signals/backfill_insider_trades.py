"""Backfill psx_insider_transactions from the DPS disclosure feed.

Crawls `/announcements?type=C&query=Disclosure of Interest` from the newest
announcement backwards to `--since`, downloads each Form-29 PDF, parses the
text layer, and upserts rows into the new `psx_insider_transactions` table
(idempotent via `source_row_hash`). Scanned (image-only) PDFs are counted and
skipped — never fabricated.

INSERT-ONLY against the new table; no existing table is written. Resumable via
a checkpoint file; safe to re-run at any time.

    python scripts/signals/backfill_insider_trades.py [--since YYYY-MM-DD] [--limit N]
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
from app.scrapers.insider_dps import InsiderDPSScraper  # noqa: E402

ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "signals"
CHECKPOINT = ARTIFACT_DIR / "backfill_insider_checkpoint.json"

PAGE = 50
FLUSH_EVERY = 5
DELAY_SECONDS = 0.25
DEFAULT_SINCE = date(2016, 1, 1)
EMPTY_PAGES_TO_STOP = 3
# The title filter narrows the feed a lot; the archive terminates at the
# same place the announcements archive does (~47k global offset).
DEFAULT_MAX_OFFSET = 60_000


def _load_checkpoint() -> dict:
    try:
        return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_checkpoint(state: dict) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_bytes(json.dumps(state, indent=2).encode("utf-8"))


async def _flush(buffer: list[dict]) -> int:
    if not buffer:
        return 0
    by_hash = {row["source_row_hash"]: row for row in buffer}
    rows = list(by_hash.values())
    await async_execute(
        lambda c, r=rows: c.table("psx_insider_transactions").upsert(
            r, on_conflict="source_row_hash")
    )
    return len(rows)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=str, default=DEFAULT_SINCE.isoformat())
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after N notices (probe mode)")
    ap.add_argument("--max-offset", type=int, default=DEFAULT_MAX_OFFSET)
    ap.add_argument("--restart", action="store_true")
    args = ap.parse_args()

    since = date.fromisoformat(args.since)
    checkpoint = {} if args.restart else _load_checkpoint()
    offset = int(checkpoint.get("next_offset", 0))
    written = int(checkpoint.get("written", 0))
    seen = set(checkpoint.get("seen_ids", []))

    print(f"  backfilling insider disclosures from offset {offset}, floor {since}")

    scraper = InsiderDPSScraper()
    buffer: list[dict] = []
    pages = 0
    empty_streak = 0
    scanned_total = 0
    oldest_seen: str | None = checkpoint.get("oldest_seen")
    notices_total = 0

    try:
        while offset < args.max_offset:
            if args.limit and notices_total >= args.limit:
                break
            try:
                notices = await scraper.fetch_notices(offset=offset, count=PAGE)
            except Exception as exc:
                print(f"  offset {offset}: {type(exc).__name__}: {exc} — retrying once")
                await asyncio.sleep(3)
                try:
                    notices = await scraper.fetch_notices(offset=offset, count=PAGE)
                except Exception as exc2:
                    print(f"  offset {offset}: failed twice ({exc2}); stopping")
                    break

            if not notices:
                empty_streak += 1
                if empty_streak >= EMPTY_PAGES_TO_STOP:
                    print(f"  offset {offset}: feed exhausted")
                    break
                offset += PAGE
                continue
            empty_streak = 0

            page_oldest: date | None = None
            for notice in notices:
                if notice.notice_id in seen:
                    continue
                seen.add(notice.notice_id)
                notices_total += 1
                if page_oldest is None or notice.posted.date() < page_oldest:
                    page_oldest = notice.posted.date()

                rows, scanned = await scraper.fetch_pdf_rows(notice)
                if scanned:
                    scanned_total += 1
                for row in rows:
                    buffer.append(row.to_db_row())

            if page_oldest is not None:
                oldest_seen = page_oldest.isoformat()

            pages += 1
            offset += PAGE

            if pages % FLUSH_EVERY == 0:
                written += await _flush(buffer)
                buffer.clear()
                _save_checkpoint({
                    "next_offset": offset, "written": written,
                    "oldest_seen": oldest_seen, "seen_ids": sorted(seen),
                    "scanned": scanned_total,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                print(f"  offset {offset:>6} | oldest {oldest_seen} | "
                      f"notices {notices_total:>6,} | rows {written:>6,} | "
                      f"scanned {scanned_total:>5,}")

            if page_oldest is not None and page_oldest < since:
                print(f"  reached floor {since} at offset {offset}")
                break

            await asyncio.sleep(DELAY_SECONDS)

        written += await _flush(buffer)
        _save_checkpoint({
            "next_offset": offset, "written": written,
            "oldest_seen": oldest_seen, "seen_ids": sorted(seen),
            "scanned": scanned_total,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    finally:
        await scraper.close()

    print(f"\n  DONE: {notices_total:,} notices, {written:,} txn rows, "
          f"{scanned_total:,} scanned PDFs skipped")
    print(f"  oldest seen: {oldest_seen}")
    print(f"  checkpoint: {CHECKPOINT}")


if __name__ == "__main__":
    asyncio.run(main())
