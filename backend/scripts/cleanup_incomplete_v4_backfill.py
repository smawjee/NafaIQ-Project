"""Remove only the incomplete V4 raw backfill created during this task.

This refuses to run if any verified bars, events, or forecasts exist. It never
touches legacy PSX tables.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


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
    try:
        protected = await conn.fetchrow(
            """
            SELECT
              (SELECT COUNT(*) FROM public.psx_ohlcv_verified) AS verified,
              (SELECT COUNT(*) FROM public.psx_signal_events) AS events,
              (SELECT COUNT(*) FROM public.psx_signal_forecasts) AS forecasts
            """
        )
        if any(int(protected[key]) for key in ("verified", "events", "forecasts")):
            raise RuntimeError(f"refusing cleanup because V4 data is already promoted: {dict(protected)}")
        before = await conn.fetchval("SELECT COUNT(*) FROM public.psx_ohlcv_raw")
        legacy_before = await conn.fetchval("SELECT COUNT(*) FROM public.psx_ohlcv")
        await conn.execute("TRUNCATE TABLE public.psx_ohlcv_raw")
        after = await conn.fetchval("SELECT COUNT(*) FROM public.psx_ohlcv_raw")
        legacy_after = await conn.fetchval("SELECT COUNT(*) FROM public.psx_ohlcv")
        print({
            "raw_before": before,
            "raw_after": after,
            "legacy_before": legacy_before,
            "legacy_after": legacy_after,
        })
        if after != 0 or legacy_before != legacy_after:
            raise RuntimeError("storage cleanup verification failed")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
