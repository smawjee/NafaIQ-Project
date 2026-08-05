"""Apply the signal-recommendation outcome tables via the Supabase pooler.

Purely additive: two CREATE TABLE IF NOT EXISTS, their indexes, RLS policies
and grants. Touches no existing table and no existing row, so re-running is
safe. Without it the two new scheduler jobs error nightly.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = "20260805090000_signal_recommendation_outcomes.sql"


async def main() -> None:
    load_dotenv(ROOT / ".env")
    required = ("SUPABASE_DATABASE_PASSWORD", "SUPABASE_POOLER_HOST", "SUPABASE_POOLER_USER")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"missing environment variables: {', '.join(missing)}")

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
        sql = (ROOT / "database" / "migrations" / MIGRATION).read_text(encoding="utf-8")
        print(f"Applying {MIGRATION} ...")
        await conn.execute(sql)

        rows = await conn.fetch(
            "SELECT filename, applied_at FROM public._applied_migrations WHERE filename = $1",
            MIGRATION,
        )
        if not rows:
            raise RuntimeError("migration ledger entry not found")
        print(f"Verified ledger: {rows[0]['filename']} at {rows[0]['applied_at']}")

        for table in ("psx_signal_recommendations", "psx_signal_calibration_daily"):
            exists = await conn.fetchval(
                "SELECT to_regclass($1) IS NOT NULL", f"public.{table}"
            )
            size = await conn.fetchval(
                "SELECT pg_size_pretty(pg_total_relation_size($1))", f"public.{table}"
            )
            print(f"  {table}: exists={exists} size={size}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
