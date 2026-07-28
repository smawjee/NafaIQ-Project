"""Apply the email-import correlation migration using the Supabase pooler.

Idempotent: every statement in the migration is IF NOT EXISTS / ADD COLUMN IF
NOT EXISTS, and the ledger insert is ON CONFLICT DO NOTHING, so re-running is
safe. Verifies the schema afterwards rather than trusting the execute.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ("20260728120000_email_import_correlation.sql",)

# Mirrors the checks in tests/test_migrations_applied.py, so a green run here
# means that test will pass too.
VERIFY = (
    ("email_import_messages table", "SELECT to_regclass('public.email_import_messages') IS NOT NULL"),
    ("email_merchant_aliases table", "SELECT to_regclass('public.email_merchant_aliases') IS NOT NULL"),
    ("unique (user_id, message_id)", "SELECT to_regclass('public.uq_email_import_messages_user_message') IS NOT NULL"),
    ("reconcile index", "SELECT to_regclass('public.idx_email_import_messages_recon') IS NOT NULL"),
    ("user_transactions.order_ref", "SELECT 1 FROM information_schema.columns WHERE table_name='user_transactions' AND column_name='order_ref'"),
    ("user_transactions.account_tail", "SELECT 1 FROM information_schema.columns WHERE table_name='user_transactions' AND column_name='account_tail'"),
    ("user_transactions.correlation_key", "SELECT 1 FROM information_schema.columns WHERE table_name='user_transactions' AND column_name='correlation_key'"),
    ("user_transactions.reverses_transaction_id", "SELECT 1 FROM information_schema.columns WHERE table_name='user_transactions' AND column_name='reverses_transaction_id'"),
    ("user_transactions.edited_at", "SELECT 1 FROM information_schema.columns WHERE table_name='user_transactions' AND column_name='edited_at'"),
    ("user_bills.correlation_key", "SELECT 1 FROM information_schema.columns WHERE table_name='user_bills' AND column_name='correlation_key'"),
    ("RLS on email_import_messages", "SELECT relrowsecurity FROM pg_class WHERE relname='email_import_messages'"),
    ("no policy for authenticated", "SELECT NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='email_import_messages')"),
    ("RLS on email_merchant_aliases", "SELECT relrowsecurity FROM pg_class WHERE relname='email_merchant_aliases'"),
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

        failures = []
        for name, check_sql in VERIFY:
            row = await connection.fetchrow(check_sql)
            if not (row and row[0]):
                failures.append(name)
            print(f"  {'OK  ' if not (name in failures) else 'FAIL'} {name}")
        if failures:
            raise RuntimeError(f"schema verification failed: {', '.join(failures)}")

        rows = await connection.fetch(
            "SELECT filename, applied_at FROM public._applied_migrations "
            "WHERE filename = ANY($1::text[]) ORDER BY filename",
            list(MIGRATIONS),
        )
        print(f"Ledger entries verified: {len(rows)}/{len(MIGRATIONS)}")
        if len(rows) != len(MIGRATIONS):
            raise RuntimeError("migration ledger verification failed")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
