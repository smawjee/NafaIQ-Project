"""Cross-cutting data checks — sector mapping, duplicates, nulls."""
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
port = os.environ.get("SUPABASE_POOLER_PORT", "6543")
user = os.environ.get("SUPABASE_POOLER_USER")

if not all([password, host, user]):
    print("ERROR: missing env vars", file=sys.stderr)
    sys.exit(1)

conn = psycopg2.connect(host=host, port=int(port), user=user, password=password, dbname="postgres", sslmode="require", connect_timeout=20)
conn.autocommit = True

try:
    with conn.cursor() as cur:
        print("=== Sector Distribution (top 25) ===")
        cur.execute("SELECT sector, COUNT(*) FROM psx_profile GROUP BY sector ORDER BY COUNT(*) DESC LIMIT 25")
        for r in cur.fetchall():
            print(f"  {str(r[0]):35s} {r[1]}")

        print("\n=== Finance-like sectors (any case) ===")
        cur.execute("SELECT DISTINCT sector FROM psx_profile WHERE LOWER(COALESCE(sector,'')) LIKE '%finance%'")
        for r in cur.fetchall():
            print(f"  {r[0]!r}")

        print("\n=== Shariah & listed_shares coverage ===")
        cur.execute("SELECT COUNT(*) FROM psx_profile WHERE is_shariah = true")
        print(f"  is_shariah=true: {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM psx_profile WHERE listed_shares IS NOT NULL AND listed_shares > 0")
        print(f"  listed_shares > 0: {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM psx_profile WHERE listed_in IS NOT NULL")
        print(f"  listed_in NOT NULL: {cur.fetchone()[0]}")

        print("\n=== Duplicate indexes ===")
        cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public' AND tablename IN ('psx_fund_nav_history','psx_index_eod') ORDER BY tablename, indexname")
        for r in cur.fetchall():
            print(f"  {r[0]}: {r[1]}")

        print("\n=== Orphan market_snapshot symbols ===")
        cur.execute("SELECT ms.symbol FROM psx_market_snapshot ms LEFT JOIN psx_profile p ON ms.symbol = p.symbol WHERE p.symbol IS NULL LIMIT 20")
        orphans = [r[0] for r in cur.fetchall()]
        print(f"  Orphan count: {len(orphans)}")
        if orphans:
            print(f"  Samples: {', '.join(orphans[:10])}")

        print("\n=== Mutual funds data ===")
        cur.execute("SELECT COUNT(*) FROM psx_mutual_funds")
        print(f"  Funds: {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM psx_fund_nav_history")
        print(f"  NAV history rows: {cur.fetchone()[0]}")

        print("\n=== Table sizes (top 10) ===")
        cur.execute("""
            SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) as size
            FROM pg_catalog.pg_statio_user_tables
            ORDER BY pg_total_relation_size(relid) DESC
            LIMIT 10
        """)
        for r in cur.fetchall():
            print(f"  {r[0]:35s} {r[1]}")

finally:
    conn.close()
