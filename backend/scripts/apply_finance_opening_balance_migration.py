"""Apply the finance opening-balance migration via the Supabase pooler.

Adds user_settings.opening_balance and .opening_balance_date, which anchor the
carried-forward finance balance. Until this runs, GET /api/finance/summary
raises UndefinedColumnError because get_settings_row selects both columns.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = "20260806170000_finance_opening_balance.sql"


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
        path = ROOT / "database" / "migrations" / MIGRATION
        sql = path.read_text(encoding="utf-8")
        print(f"Applying {MIGRATION} ...")
        await conn.execute(sql)
        rows = await conn.fetch(
            "SELECT filename, applied_at FROM public._applied_migrations WHERE filename = $1",
            MIGRATION,
        )
        if rows:
            print(f"Verified: {rows[0]['filename']} applied at {rows[0]['applied_at']}")
        else:
            raise RuntimeError("migration ledger entry not found")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
