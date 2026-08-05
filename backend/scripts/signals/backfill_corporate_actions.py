"""Attribute corporate actions from the psx_announcements archive.

`psx_dividends` (the existing payout table) holds only a rolling ~18-month
window of *cash* dividends — no bonus, no rights, nothing before 2025-03
(verified by `scripts/signals/probe_payouts.py`). The announcement archive
(backfilled to 2023-12 by `scripts/signals/backfill_announcements.py`) does
carry them: "Credit of Bonus Shares", "Book Closure to Determine Right Issue
Entitlement", "Credit of Final Cash Dividend", etc.

This script copies those *audited* notices into the new
`psx_corporate_actions` table (INSERT-ONLY, idempotent via source_row_hash),
so the limit-day pilot can strip ex-cash / ex-bonus / ex-rights dates from its
event set instead of guessing at gaps. 2016-2022 stays quarantined exactly as
before — attribution covers 2023-12 onward only (user decision 2026-08-05).

A row is applied iff its title matches one of the audited patterns below AND
the symbol exists in psx_profile (equity check). Nothing is ever inferred
from price gaps — attribution only, never detection.

    python scripts/signals/backfill_corporate_actions.py
"""
from __future__ import annotations

import asyncio
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from sqlalchemy import text  # noqa: E402

from app.db.supabase import async_execute  # noqa: E402
from app.repositories.base import connect  # noqa: E402

# Audited title patterns. Group 1 is the canonical action_type.
PATTERNS = [
    (r"bonus share", "bonus"),
    (r"right issue|letter of rights|rights entitlement", "rights"),
    (r"cash dividend|dividend warrant|final dividend|interim dividend|second interim dividend|third interim dividend", "dividend"),
]

FLUSH = 500


def classify(title: str) -> str | None:
    t = (title or "").lower()
    for pat, kind in PATTERNS:
        import re
        if re.search(pat, t):
            return kind
    return None


def row_hash(symbol: str, ann_date: str, kind: str, title: str) -> str:
    blob = "|".join([symbol, ann_date, kind, title[:200]])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def main() -> None:
    async with connect() as conn:
        rows = (await conn.execute(text("""
            SELECT symbol, posted_at::date AS ann_date, title
            FROM psx_announcements
            WHERE symbol IS NOT NULL AND posted_at IS NOT NULL
              AND title ~* '(bonus|right issue|letter of rights|rights entitlement|cash dividend|dividend warrant|final dividend|interim dividend)'
            ORDER BY posted_at
        """))).mappings().all()
        symbols = {r["symbol"] for r in (await conn.execute(text(
            "SELECT symbol FROM psx_profile WHERE symbol IS NOT NULL"
        ))).mappings().all()}
    print(f"  {len(rows):,} candidate announcements, {len(symbols):,} known equities")

    buffer: list[dict] = []
    total = 0
    skipped = 0
    for r in rows:
        sym = str(r["symbol"]).upper()
        if sym not in symbols:
            skipped += 1
            continue
        kind = classify(r["title"])
        if not kind:
            skipped += 1
            continue
        buffer.append({
            "symbol": sym,
            "ann_date": r["ann_date"].isoformat(),
            "action_type": kind,
            "details": r["title"],
            "source_row_hash": row_hash(sym, r["ann_date"].isoformat(), kind, r["title"]),
            "inserted_at": datetime.now(timezone.utc).isoformat(),
        })
        if len(buffer) >= FLUSH:
            await _flush(buffer)
            total += len(buffer)
            buffer = []
            print(f"  {total:,} rows written...")
    if buffer:
        await _flush(buffer)
        total += len(buffer)
    print(f"  DONE: {total:,} corporate-action rows written, {skipped:,} skipped")


async def _flush(rows: list[dict]) -> None:
    by_hash = {r["source_row_hash"]: r for r in rows}
    await async_execute(
        lambda c, r=list(by_hash.values()): c.table("psx_corporate_actions").upsert(
            r, on_conflict="source_row_hash")
    )


if __name__ == "__main__":
    asyncio.run(main())
