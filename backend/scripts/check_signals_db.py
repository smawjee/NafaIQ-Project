"""Read-only direct-Postgres verification for signals tables."""
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
        tables = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY($1::text[])
            ORDER BY table_name
            """,
            ["psx_ohlcv", "psx_signal_events", "psx_signal_forecasts", "psx_signal_model_registry"],
        )
        counts = {}
        for table in ("psx_ohlcv", "psx_signal_events", "psx_signal_forecasts"):
            counts[table] = await conn.fetchval(f"SELECT COUNT(*) FROM public.{table}")
        print({"tables": [row["table_name"] for row in tables], "counts": counts})
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
