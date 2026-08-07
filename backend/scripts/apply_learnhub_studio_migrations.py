"""Apply and verify every database prerequisite for LearnHub Studio.

The migrations are additive/idempotent and are applied in dependency order.
After schema bootstrap, run ``scripts/data/ingest_learnhub.py`` whenever the
readiness report says the approved embedded corpus is empty.

    cd backend
    .venv/bin/python scripts/apply_learnhub_studio_migrations.py
    .venv/bin/python scripts/apply_learnhub_studio_migrations.py --check-only
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    "20260717100000_learnhub_rag.sql",
    "20260717200000_learnhub_ai_usage.sql",
    "20260805170000_learnhub_studio.sql",
    "20260806090000_learnhub_studio_pdf.sql",
    "20260807110000_learnhub_studio_media_bucket.sql",
)


def _required_env() -> None:
    required = (
        "SUPABASE_DATABASE_PASSWORD",
        "SUPABASE_POOLER_HOST",
        "SUPABASE_POOLER_USER",
    )
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"missing environment variables: {', '.join(missing)}")


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=os.environ["SUPABASE_POOLER_HOST"],
        port=int(os.getenv("SUPABASE_POOLER_PORT", "6543")),
        user=os.environ["SUPABASE_POOLER_USER"],
        password=os.environ["SUPABASE_DATABASE_PASSWORD"],
        database="postgres",
        ssl="require",
        timeout=30,
        statement_cache_size=0,
    )


async def _apply(connection: asyncpg.Connection) -> None:
    for filename in MIGRATIONS:
        path = ROOT / "database" / "migrations" / filename
        print(f"Applying {filename} ...")
        await connection.execute(path.read_text(encoding="utf-8"))
        # Older migrations predate the ledger footer. Converge their ledger
        # state here without changing the immutable historical SQL files.
        await connection.execute(
            """
            INSERT INTO public._applied_migrations(filename, applied_at)
            VALUES ($1, now())
            ON CONFLICT (filename) DO NOTHING
            """,
            filename,
        )


async def _verify(connection: asyncpg.Connection) -> None:
    tables = (
        "learnhub_knowledge_chunks",
        "learnhub_ai_usage",
        "learnhub_studio_projects",
        "learnhub_studio_artifacts",
        "learnhub_generation_jobs",
        "learnhub_studio_documents",
        "learnhub_studio_cleanup_jobs",
    )
    missing_tables = [
        table
        for table in tables
        if not await connection.fetchval("SELECT to_regclass($1) IS NOT NULL", f"public.{table}")
    ]
    if missing_tables:
        raise RuntimeError(f"Studio tables missing after bootstrap: {', '.join(missing_tables)}")

    bucket = await connection.fetchrow(
        """
        SELECT public, file_size_limit, allowed_mime_types
        FROM storage.buckets WHERE id = 'learnhub-studio'
        """
    )
    if not bucket or bucket["public"]:
        raise RuntimeError("private learnhub-studio storage bucket is missing")

    ledger_count = await connection.fetchval(
        "SELECT count(*) FROM public._applied_migrations WHERE filename = ANY($1::text[])",
        list(MIGRATIONS),
    )
    if ledger_count != len(MIGRATIONS):
        raise RuntimeError(f"Studio migration ledger incomplete: {ledger_count}/{len(MIGRATIONS)}")

    corpus = await connection.fetchrow(
        """
        SELECT count(*) FILTER (WHERE is_active) AS active,
               count(*) FILTER (WHERE is_active AND embedding IS NOT NULL) AS embedded
        FROM public.learnhub_knowledge_chunks
        """
    )
    print("LearnHub Studio database readiness:")
    print(f"  migrations: {ledger_count}/{len(MIGRATIONS)}")
    print(f"  private bucket: learnhub-studio ({bucket['file_size_limit']} byte object limit)")
    print(f"  active corpus: {corpus['active']} chunks ({corpus['embedded']} embedded)")
    if not corpus["active"] or not corpus["embedded"]:
        print("  NEXT: run scripts/data/ingest_learnhub.py before enabling Studio")


async def main(*, check_only: bool) -> None:
    load_dotenv(ROOT / ".env")
    _required_env()
    connection = await _connect()
    try:
        if not check_only:
            await _apply(connection)
        await _verify(connection)
    finally:
        await connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify schema, bucket, ledger, and corpus without writing.",
    )
    args = parser.parse_args()
    asyncio.run(main(check_only=args.check_only))
