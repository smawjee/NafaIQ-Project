"""Apply the LearnHub lectures migration via the Supabase pooler.

Creates public.learnhub_lectures (the admin-managed Learn Hub catalogue) and
seeds the learn.read / learn.write permissions onto the existing content_admin
role. Until this runs, /api/admin/lectures raises UndefinedTableError and the
admin console's Lectures page cannot load.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = "20260807100000_learnhub_lectures.sql"


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
        if not rows:
            raise RuntimeError("migration ledger entry not found")
        print(f"Verified: {rows[0]['filename']} applied at {rows[0]['applied_at']}")

        # Report what actually landed, rather than trusting the ledger alone.
        perms = await conn.fetchval(
            "SELECT COUNT(*) FROM public.admin_permissions "
            "WHERE slug IN ('learn.read', 'learn.write')"
        )
        grants = await conn.fetch(
            "SELECT role_slug, COUNT(*) AS n FROM public.admin_role_permissions "
            "WHERE permission_slug IN ('learn.read', 'learn.write') "
            "GROUP BY role_slug ORDER BY role_slug"
        )
        print(f"  permissions seeded: {perms}/2")
        for row in grants:
            print(f"  {row['role_slug']}: {row['n']} learn permission(s)")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
