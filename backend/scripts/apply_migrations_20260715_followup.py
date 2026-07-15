r"""Apply the RLS follow-up migration to live Supabase.

Run from the backend directory:
    python -m scripts.apply_migrations_20260715_followup
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

MIGRATION = "20260715030000_rls_grants_and_indexes.sql"


def main() -> int:
    password = os.environ.get("SUPABASE_DATABASE_PASSWORD")
    host = os.environ.get("SUPABASE_POOLER_HOST")
    port = os.environ.get("SUPABASE_POOLER_PORT", "6543")
    user = os.environ.get("SUPABASE_POOLER_USER")
    if not all([password, host, user]):
        print("ERROR: missing env vars", file=sys.stderr)
        return 1

    path = BACKEND_DIR / "database" / "migrations" / MIGRATION
    sql = path.read_text(encoding="utf-8")
    print(f"Connecting to {host}:{port} as {user} ...")
    conn = psycopg2.connect(
        host=host,
        port=int(port),
        user=user,
        password=password,
        dbname="postgres",
        sslmode="require",
        connect_timeout=20,
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            print(f"--- Applying {MIGRATION} ({len(sql)} bytes) ---")
            cur.execute(sql)
            print(f"OK: {MIGRATION}")

            cur.execute(
                """
                SELECT tablename, rowsecurity
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename IN (
                      'macro_rates', 'psx_mutual_funds', 'psx_fund_nav_history',
                      'psx_news', 'filings', 'psx_unusual_activity',
                      'psx_financials_annual', 'psx_financials_quarterly'
                  )
                ORDER BY tablename
                """
            )
            print()
            print("RLS status on the 8 new tables:")
            for name, rls in cur.fetchall():
                print(f"  {name}: RLS={'on' if rls else 'off'}")

            cur.execute(
                """
                SELECT polname, tablename
                FROM pg_policies
                WHERE schemaname = 'public'
                ORDER BY tablename, polname
                """
            )
            policies = cur.fetchall()
            print()
            print(f"Policies ({len(policies)} total):")
            for polname, tbl in policies:
                if tbl in (
                    "macro_rates", "psx_mutual_funds", "psx_fund_nav_history",
                    "psx_news", "filings", "psx_unusual_activity",
                    "psx_financials_annual", "psx_financials_quarterly",
                ):
                    print(f"  {tbl}.{polname}")

            cur.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname IN ('idx_psx_fa_sym_year', 'idx_psx_fq_sym_period')
                ORDER BY indexname
                """
            )
            indexes = [r[0] for r in cur.fetchall()]
            print()
            print(f"Financials DESC indexes present ({len(indexes)}/2): {', '.join(indexes) if indexes else 'NONE'}")

            cur.execute(
                """
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'psx_ohlcv'
                  AND column_name IN ('is_adjusted', 'adjustment_factor')
                ORDER BY column_name
                """
            )
            print()
            print("psx_ohlcv NOT NULL status:")
            for col, nullable in cur.fetchall():
                print(f"  {col}: nullable={nullable}")

            cur.execute(
                """
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'psx_profile'
                  AND column_name = 'is_shariah'
                """
            )
            row = cur.fetchone()
            print(f"  psx_profile.is_shariah: nullable={'YES' if row[1] == 'YES' else 'NO'}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
