r"""Apply the NafaIQ Assistant migration to live Supabase.

Follows the pattern of apply_migrations_20260716.py: connect through the
transaction pooler, run each file, verify, and record the result in the
_applied_migrations ledger so the state is auditable afterwards.

The migration is purely additive (CREATE TABLE IF NOT EXISTS + REVOKE/GRANT on a
brand-new table) and re-runnable, so a repeat run is a no-op.

Usage (from the backend directory):
    python -m scripts.apply_migrations_20260722
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

MIGRATIONS = [
    "20260722100000_assistant_usage.sql",
]


def main() -> int:
    password = os.environ.get("SUPABASE_DATABASE_PASSWORD")
    host = os.environ.get("SUPABASE_POOLER_HOST")
    port = os.environ.get("SUPABASE_POOLER_PORT", "6543")
    user = os.environ.get("SUPABASE_POOLER_USER")

    missing = [
        k
        for k, v in {
            "SUPABASE_DATABASE_PASSWORD": password,
            "SUPABASE_POOLER_HOST": host,
            "SUPABASE_POOLER_USER": user,
        }.items()
        if not v
    ]
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)}", file=sys.stderr)
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
                    print(f"SKIP (not found): {fname}", file=sys.stderr)
                    return 2
                sql = path.read_text(encoding="utf-8")
                print(f"--- Applying {fname} ({len(sql)} bytes) ---")
                try:
                    cur.execute(sql)
                    print(f"OK: {fname}")
                except psycopg2.Error as e:
                    print(f"FAIL: {fname}: {e.pgerror or e}", file=sys.stderr)
                    return 2

                cur.execute(
                    "INSERT INTO public._applied_migrations (filename, sha256) "
                    "VALUES (%s, %s) ON CONFLICT (filename) DO NOTHING",
                    (fname, hashlib.sha256(sql.encode("utf-8")).hexdigest()),
                )

        print()
        print("=== Verification ===")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='assistant_usage' "
                "ORDER BY ordinal_position"
            )
            cols = cur.fetchall()
            print(f"assistant_usage columns: {cols or 'MISSING'}")

            cur.execute(
                "SELECT relrowsecurity FROM pg_class "
                "WHERE relname='assistant_usage' AND relnamespace='public'::regnamespace"
            )
            row = cur.fetchone()
            print(f"RLS enabled: {row[0] if row else 'MISSING'}")

            # The important one: the anon key ships in the browser bundle, and a
            # client that can UPDATE this table can reset its own quota.
            cur.execute(
                "SELECT grantee, privilege_type FROM information_schema.role_table_grants "
                "WHERE table_schema='public' AND table_name='assistant_usage' "
                "AND grantee IN ('anon','authenticated')"
            )
            leaked = cur.fetchall()
            print(f"anon/authenticated grants (must be empty): {leaked or 'none'}")

            cur.execute(
                "SELECT filename, applied_at FROM public._applied_migrations "
                "WHERE filename = ANY(%s)",
                (MIGRATIONS,),
            )
            print(f"ledger: {cur.fetchall()}")

            if not cols or leaked:
                print("VERIFICATION FAILED", file=sys.stderr)
                return 3
    finally:
        conn.close()

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
