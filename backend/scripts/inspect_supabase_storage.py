"""Read-only storage inventory for Supabase Postgres."""
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
        rows = await conn.fetch(
            """
            SELECT c.relname AS table_name,
                   pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
                   pg_total_relation_size(c.oid) AS total_bytes,
                   COALESCE(s.n_live_tup, 0) AS estimated_rows
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
            WHERE n.nspname = 'public' AND c.relkind IN ('r', 'm')
            ORDER BY pg_total_relation_size(c.oid) DESC
            LIMIT 40
            """
        )
        for row in rows:
            print(dict(row))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
