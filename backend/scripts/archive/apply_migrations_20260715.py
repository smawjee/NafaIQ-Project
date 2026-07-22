r"""One-shot script to apply the 3 new PSX migrations to live Supabase.

Reads the connection details from the backend .env, opens a psycopg2
connection to the Supabase transaction pooler, and runs each migration file
in order. Each file is idempotent (CREATE OR REPLACE / IF NOT EXISTS), so
re-running this script is safe.

Usage (from the backend directory):
    python -m scripts.apply_migrations_20260715
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

MIGRATIONS = [
    "20260715000000_patch_market_snapshot.sql",  # B1 — AHL row-clobber fix
    "20260715010000_new_data_tables.sql",        # D   — 8 new tables
    "20260715020000_ohlcv_adjustment_and_shariah.sql",  # E   — split + shariah
]


def main() -> int:
    password = os.environ.get("SUPABASE_DATABASE_PASSWORD")
    host = os.environ.get("SUPABASE_POOLER_HOST")
    port = os.environ.get("SUPABASE_POOLER_PORT", "6543")
    user = os.environ.get("SUPABASE_POOLER_USER")

    missing = [k for k, v in {
        "SUPABASE_DATABASE_PASSWORD": password,
        "SUPABASE_POOLER_HOST": host,
        "SUPABASE_POOLER_USER": user,
    }.items() if not v]
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)}", file=sys.stderr)
        return 1

    if not password or not host or not user:
        print("ERROR: empty required env var", file=sys.stderr)
        return 1

    migrations_dir = BACKEND_DIR / "database" / "migrations"
    print(f"Connecting to {host}:{port} as {user} (transaction pooler) ...")
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
            for fname in MIGRATIONS:
                path = migrations_dir / fname
                if not path.exists():
                    print(f"SKIP (not found): {fname}")
                    continue
                sql = path.read_text(encoding="utf-8")
                print(f"--- Applying {fname} ({len(sql)} bytes) ---")
                try:
                    cur.execute(sql)
                    print(f"OK: {fname}")
                except psycopg2.Error as e:
                    print(f"FAIL: {fname}: {e.pgerror or e}", file=sys.stderr)
                    return 2

        # Verification — re-query the schema to confirm each migration took.
        print()
        print("=== Verification ===")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT routine_name
                FROM information_schema.routines
                WHERE routine_schema = 'public'
                  AND routine_name = 'patch_market_snapshot'
                """
            )
            print(f"patch_market_snapshot function: {'present' if cur.fetchone() else 'MISSING'}")

            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN (
                      'macro_rates', 'psx_mutual_funds', 'psx_fund_nav_history',
                      'psx_news', 'filings', 'psx_unusual_activity',
                      'psx_financials_annual', 'psx_financials_quarterly'
                  )
                ORDER BY table_name
                """
            )
            rows = [r[0] for r in cur.fetchall()]
            print(f"Workstream D tables present ({len(rows)}/8): {', '.join(rows) if rows else 'NONE'}")

            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'psx_ohlcv'
                  AND column_name IN ('is_adjusted', 'adjustment_factor', 'split_date')
                ORDER BY column_name
                """
            )
            cols = [r[0] for r in cur.fetchall()]
            print(f"psx_ohlcv new columns ({len(cols)}/3): {', '.join(cols) if cols else 'NONE'}")

            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'psx_profile'
                  AND column_name = 'is_shariah'
                """
            )
            print(f"psx_profile.is_shariah: {'present' if cur.fetchone() else 'MISSING'}")

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
