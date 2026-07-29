r"""One-shot script to apply the 6 new PSX fix migrations to live Supabase.

Follow-up to apply_migrations_20260715.py. These migrations are the result
of the Parallel Fix Plan (July 16 audit-driven fixes).

Usage (from the backend directory):
    python -m scripts.apply_migrations_20260716
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
    "20260716000000_add_listed_in.sql",
    "20260716010000_apply_sector_map.sql",
    "20260716020000_mufap_performance_indexes.sql",
    "20260716030000_tighten_grants.sql",
    "20260716040000_add_ttls.sql",
    "20260716050000_data_source_health.sql",
    "20260716060000_cleanup_duplicates_and_orphans.sql",
    "20260716070000_analyze_and_refresh.sql",
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

        # Verification
        print()
        print("=== Verification ===")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='psx_profile' AND column_name='listed_in'"
            )
            print(f"psx_profile.listed_in: {'present' if cur.fetchone() else 'MISSING'}")

            cur.execute(
                "SELECT sector FROM psx_profile WHERE sector = 'Finance' LIMIT 1"
            )
            leftover = cur.fetchone()
            print(f"TV-style 'Finance' sector rows: {0 if not leftover else 'REMAINING'}")

            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='psx_data_source_health'"
            )
            print(f"psx_data_source_health: {'present' if cur.fetchone() else 'MISSING'}")

            cur.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname='public' AND indexname='idx_psx_mutual_funds_category'"
            )
            print(f"idx_psx_mutual_funds_category: {'present' if cur.fetchone() else 'MISSING'}")

            cur.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname='public' AND indexname='idx_psx_fund_nav_history_fund_code'"
            )
            print(f"idx_psx_fund_nav_history_fund_code: {'present' if cur.fetchone() else 'MISSING'}")

            cur.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname='public' AND indexname='idx_psx_unusual_activity_ts'"
            )
            print(f"idx_psx_unusual_activity_ts: {'present' if cur.fetchone() else 'MISSING'}")

            cur.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname='public' AND indexname='psx_index_eod_unique'"
            )
            print(f"psx_index_eod_unique (should be GONE): {'STILL EXISTS' if cur.fetchone() else 'GONE'}")

            cur.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname='public' AND indexname='idx_psx_fund_nav_date'"
            )
            print(f"idx_psx_fund_nav_date (should be GONE): {'STILL EXISTS' if cur.fetchone() else 'GONE'}")

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
