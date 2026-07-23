"""One-time immutable OHLCV backfill for Signals V4.

Downloads official DPS history with bounded concurrency and writes directly to
Postgres in idempotent insert batches. It never modifies legacy psx_ohlcv.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

from app.scrapers.dps import DPSScraper

ROOT = Path(__file__).resolve().parents[2]
CONCURRENCY = 8


async def main() -> None:
    load_dotenv(ROOT / ".env")
    conn = await asyncpg.connect(
        host=os.environ["SUPABASE_POOLER_HOST"],
        port=int(os.getenv("SUPABASE_POOLER_PORT", "6543")),
        user=os.environ["SUPABASE_POOLER_USER"],
        password=os.environ["SUPABASE_DATABASE_PASSWORD"],
        database="postgres",
        ssl="require",
        timeout=30,
        statement_cache_size=0,
    )
    symbols = await conn.fetch("SELECT symbol FROM public.psx_profile WHERE symbol IS NOT NULL ORDER BY symbol")
    scraper = DPSScraper()
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def fetch_symbol(symbol: str):
        async with semaphore:
            try:
                bars = await scraper.fetch_historical(symbol)
                fetched_at = datetime.now(timezone.utc)
                rows = []
                for bar in bars:
                    payload = bar.to_dict()
                    rows.append((
                        payload.get("symbol") or symbol,
                        date.fromisoformat(str(payload.get("date"))[:10]),
                        "dps_historical",
                        hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
                        fetched_at,
                        payload.get("open"), payload.get("high"), payload.get("low"),
                        payload.get("close"), payload.get("volume"), payload.get("ldcp"),
                        json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    ))
                return symbol, rows, None
            except Exception as exc:
                return symbol, [], str(exc)

    insert_sql = """
        INSERT INTO public.psx_ohlcv_raw
        (symbol, date, source, source_record_hash, fetched_at, open, high, low,
         close, volume, ldcp, source_payload)
        VALUES ($1, $2::date, $3, $4, $5::timestamptz, $6, $7, $8, $9, $10, $11, $12::jsonb)
        ON CONFLICT DO NOTHING
    """
    completed = 0
    attempted = 0
    try:
        for start in range(0, len(symbols), CONCURRENCY):
            batch = [str(row["symbol"]).upper() for row in symbols[start:start + CONCURRENCY]]
            results = await asyncio.gather(*(fetch_symbol(symbol) for symbol in batch))
            for symbol, rows, error in results:
                if rows:
                    await conn.executemany(insert_sql, rows)
                    attempted += len(rows)
                completed += 1
                suffix = f" ERROR: {error}" if error else ""
                print(f"{completed}/{len(symbols)} {symbol}: {len(rows)} raw bars{suffix}")
        print(f"completed {completed} symbols; attempted {attempted} immutable raw rows")
    finally:
        await scraper.close()
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())