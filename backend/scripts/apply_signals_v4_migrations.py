"""Apply Signals V4 migrations using the configured Supabase pooler."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    "20260723100000_signals_v4_foundation.sql",
    "20260723100500_signals_v4_model_registry.sql",
    "20260723101000_signals_v4_document_provenance.sql",
)


async def main() -> None:
    load_dotenv(ROOT / ".env")
    required = ("SUPABASE_DATABASE_PASSWORD", "SUPABASE_POOLER_HOST", "SUPABASE_POOLER_USER")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"missing environment variables: {', '.join(missing)}")
    connection = await asyncpg.connect(
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
        for filename in MIGRATIONS:
            path = ROOT / "database" / "migrations" / filename
            sql = path.read_text(encoding="utf-8")
            print(f"Applying {filename} ...")
            await connection.execute(sql)
            print(f"Applied {filename}")
        rows = await connection.fetch(
            """
            SELECT filename, applied_at
            FROM public._applied_migrations
            WHERE filename = ANY($1::text[])
            ORDER BY filename
            """,
            list(MIGRATIONS),
        )
        print(f"Ledger entries verified: {len(rows)}/{len(MIGRATIONS)}")
        if len(rows) != len(MIGRATIONS):
            raise RuntimeError("migration ledger verification failed")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
