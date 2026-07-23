"""Drop the redundant non-unique OHLCV symbol/date index after verification."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
INDEX = "idx_psx_ohlcv_symbol_date_desc"


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
            SELECT indexrelname, idx_scan
            FROM pg_stat_user_indexes
            WHERE relname = 'psx_ohlcv' AND indexrelname = $1
            """,
            INDEX,
        )
        if not row:
            print({"status": "already_absent", "index": INDEX})
            return
        print({"status": "dropping_redundant_index", "index": INDEX, "idx_scan": row["idx_scan"]})
        await conn.execute(f'DROP INDEX IF EXISTS public."{INDEX}"')
        remaining = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_indexes WHERE schemaname='public' AND indexname=$1",
            INDEX,
        )
        if remaining:
            raise RuntimeError("index still exists after drop")
        print({"status": "dropped", "index": INDEX})
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
