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
        host=os.environ["SUPABASE_POOLER_HOST"], port=int(os.getenv("SUPABASE_POOLER_PORT", "6543")),
        user=os.environ["SUPABASE_POOLER_USER"], password=os.environ["SUPABASE_DATABASE_PASSWORD"],
        database="postgres", ssl="require", timeout=30, statement_cache_size=0,
    )
    try:
        row = await conn.fetchrow(
            """
            SELECT pg_size_pretty(pg_table_size('public.psx_ohlcv')) AS table_size,
                   pg_size_pretty(pg_indexes_size('public.psx_ohlcv')) AS index_size,
                   pg_size_pretty(pg_total_relation_size('public.psx_ohlcv')) AS total_size,
                   pg_stat_get_live_tuples('public.psx_ohlcv'::regclass) AS live_rows,
                   pg_stat_get_dead_tuples('public.psx_ohlcv'::regclass) AS dead_rows
            """
        )
        print(dict(row))
        indexes = await conn.fetch(
            """
            SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid)) AS size
            FROM pg_stat_user_indexes
            WHERE relname = 'psx_ohlcv'
            ORDER BY pg_relation_size(indexrelid) DESC
            """
        )
        for index in indexes:
            print(dict(index))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
