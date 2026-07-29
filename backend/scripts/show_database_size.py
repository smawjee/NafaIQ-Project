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
        row = await conn.fetchrow("SELECT pg_size_pretty(pg_database_size(current_database())) AS size, pg_database_size(current_database()) AS bytes")
        print(dict(row))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
