"""Apply the broker email-import migration via the configured Supabase pooler.

The broker_import_items / stock_transactions.broker_import_item_id schema
(20260805193000_broker_email_imports.sql) is required by
repositories/portfolio/trades.py (in-flight broker-import feature). Additive
only: CREATE TABLE IF NOT EXISTS + ADD COLUMN IF NOT EXISTS — idempotent.

    python scripts/apply_broker_email_imports_migration.py
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = "20260805193000_broker_email_imports.sql"


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
        path = ROOT / "database" / "migrations" / MIGRATION
        sql = path.read_text(encoding="utf-8")
        print(f"Applying {MIGRATION} ...")
        await connection.execute(sql)
        await connection.execute("""
            INSERT INTO public._applied_migrations(filename, applied_at)
            VALUES ($1, now())
            ON CONFLICT (filename) DO NOTHING
        """, MIGRATION)
        column = await connection.fetchval("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'stock_transactions'
              AND column_name = 'broker_import_item_id'
        """)
        if not column:
            raise RuntimeError("broker_import_item_id column missing after apply")
        ledger = await connection.fetchval("""
            SELECT count(*) FROM public._applied_migrations WHERE filename = $1
        """, MIGRATION)
        print(f"Applied {MIGRATION}: column verified, ledger entries {ledger}")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
