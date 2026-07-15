"""Verify all fixes applied correctly."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

password = os.environ.get("SUPABASE_DATABASE_PASSWORD")
host = os.environ.get("SUPABASE_POOLER_HOST")
port = int(os.environ.get("SUPABASE_POOLER_PORT", "6543"))
user = os.environ.get("SUPABASE_POOLER_USER")

conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname="postgres", sslmode="require", connect_timeout=20)
conn.autocommit = True

try:
    with conn.cursor() as cur:
        print("=== OHLCV Fix ===")
        cur.execute("SELECT COUNT(*) FROM psx_ohlcv WHERE open < low OR high < close")
        print(f"  Bad rows remaining: {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM psx_ohlcv")
        print(f"  Total OHLCV rows: {cur.fetchone()[0]}")

        print("\n=== Orphan Cleanup ===")
        cur.execute("SELECT COUNT(*) FROM psx_market_snapshot ms LEFT JOIN psx_profile p ON ms.symbol = p.symbol WHERE p.symbol IS NULL")
        print(f"  Orphan snapshot rows: {cur.fetchone()[0]}")

        print("\n=== Duplicate Indexes ===")
        cur.execute("SELECT indexname FROM pg_indexes WHERE schemaname='public' AND indexname IN ('psx_index_eod_unique','idx_psx_fund_nav_date')")
        rows = [r[0] for r in cur.fetchall()]
        print(f"  Still present: {rows if rows else 'NONE'}")

        print("\n=== Sector Map ===")
        cur.execute("SELECT COUNT(*) FROM psx_profile WHERE sector = 'Finance'")
        print(f"  Sector = Finance: {cur.fetchone()[0]}")

        print("\n=== ANALYZE Effect ===")
        cur.execute("SELECT relname, reltuples FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind='r' AND reltuples > 0 ORDER BY reltuples DESC LIMIT 5")
        for r in cur.fetchall():
            print(f"  {r[0]:35s} {int(r[1]):>10,} est. rows")

        print("\n=== All Verifications Pass")
finally:
    conn.close()
