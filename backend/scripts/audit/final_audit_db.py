# -*- coding: utf-8 -*-
"""
Final Database Audit Script
============================
Runs a comprehensive read-only audit against the Supabase (Postgres) database.
All 6 query blocks specified in the audit request are executed in full.

Usage:
    python -m scripts.audit.final_audit_db
"""

import os
import sys
from pathlib import Path
from datetime import datetime

import psycopg2
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DB_CONFIG = {
    "host": os.environ.get("SUPABASE_POOLER_HOST", "aws-1-ap-southeast-1.pooler.supabase.com"),
    "port": int(os.environ.get("SUPABASE_POOLER_PORT", "6543")),
    "user": os.environ.get("SUPABASE_POOLER_USER", "postgres.gmonfgxmjgzipnbhgimv"),
    "password": os.environ.get("SUPABASE_DATABASE_PASSWORD", ""),
    "dbname": "postgres",
    "sslmode": "require",
    "connect_timeout": 30,
}

SEP = "=" * 120
SUB = "-" * 80


def heading(text: str) -> None:
    print(f"\n{SEP}")
    print(f"  ** {text} **")
    print(SEP)


def run_query(cur, label: str, sql: str) -> None:
    print(f"\n{SUB}")
    print(f"  >>> {label}")
    print(SUB)
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description] if cur.description else []
        if col_names:
            header = " | ".join(f"{c:<30}" for c in col_names)
            print(f"  {header}")
            print(f"  {'-' * len(header)}")
            for row in rows:
                vals = []
                for v in row:
                    s = str(v) if v is not None else "NULL"
                    vals.append(f"{s:<30}")
                print("  " + " | ".join(vals))
        else:
            for row in rows:
                print(f"  {row}")
        print(f"\n  -> {len(rows)} row(s) returned.")
    except Exception as e:
        print(f"  ERROR: {e}")


def main():
    start = datetime.now()
    print(f"{SEP}")
    print(f"  FINAL DATABASE AUDIT")
    print(f"  Started at : {start.isoformat()}")
    print(f"  Host       : {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"  Database   : {DB_CONFIG['dbname']}")
    print(f"  User       : {DB_CONFIG['user']}")
    print(SEP)

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    # =====================================================================
    # 1. TABLE OVERVIEW
    # =====================================================================
    heading("1. TABLE OVERVIEW (name, size, column count)")
    run_query(
        cur,
        "Table overview — size & column count, ordered by size descending",
        """SELECT table_name,
                  pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) AS size,
                  (SELECT COUNT(*)
                   FROM information_schema.columns
                   WHERE table_schema = 'public'
                     AND table_name = t.table_name) AS cols
           FROM information_schema.tables t
           WHERE table_schema = 'public'
             AND table_type = 'BASE TABLE'
           ORDER BY pg_total_relation_size(quote_ident(table_name)) DESC;""",
    )

    # =====================================================================
    # 2. ROW COUNTS FOR ALL PUBLIC TABLES (actual COUNT(*))
    # =====================================================================
    heading("2. ROW COUNTS (actual COUNT(*) for every public table)")

    cur.execute(
        """SELECT table_name
           FROM information_schema.tables
           WHERE table_schema = 'public'
             AND table_type = 'BASE TABLE'
           ORDER BY table_name;"""
    )
    tables = [row[0] for row in cur.fetchall()]
    print(f"\n  Found {len(tables)} public tables. Running COUNT(*) on each...\n")

    count_parts = []
    for t in tables:
        safe = t.replace("'", "''")
        count_parts.append(f"SELECT '{safe}' AS table_name, COUNT(*)::text AS row_count FROM {t}")

    if count_parts:
        count_sql = " UNION ALL\n".join(count_parts) + "\nORDER BY table_name;"
        run_query(cur, f"Row counts for all {len(tables)} tables", count_sql)
    else:
        print("  No tables found.")

    # =====================================================================
    # 3. DATA QUALITY CHECKS
    # =====================================================================
    heading("3. DATA QUALITY CHECKS (a–l)")

    data_quality_sql = """
-- a) Bad OHLCV (should be 0)
SELECT 'bad_ohlcv' AS check_name, COUNT(*)::text AS value FROM psx_ohlcv WHERE open < low OR high < close
UNION ALL
-- b) Orphan snapshots (should be 0)
SELECT 'orphan_snapshot' AS check_name, COUNT(*)::text FROM psx_market_snapshot ms LEFT JOIN psx_profile p ON ms.symbol = p.symbol WHERE p.symbol IS NULL
UNION ALL
-- c) Finance sectors remaining after TV mapping (should be 0)
SELECT 'tv_finance_remaining' AS check_name, COUNT(*)::text FROM psx_profile WHERE sector = 'Finance'
UNION ALL
-- d) Duplicate indexes (should be 0)
SELECT 'dup_indexes' AS check_name, COUNT(*)::text FROM pg_indexes WHERE schemaname='public' AND indexname IN ('psx_index_eod_unique','idx_psx_fund_nav_date')
UNION ALL
-- e) Shariah flagged count (should be > 0 after deploy)
SELECT 'shariah_true' AS check_name, COUNT(*)::text FROM psx_profile WHERE is_shariah = true
UNION ALL
-- f) Listed shares populated (should be > 0)
SELECT 'listed_shares_not_null' AS check_name, COUNT(*)::text FROM psx_profile WHERE listed_shares IS NOT NULL AND listed_shares > 0
UNION ALL
-- g) Filings without text content (should be 0 missing)
SELECT 'filings_no_text' AS check_name, COUNT(*)::text FROM filings WHERE text_content IS NULL
UNION ALL
-- h) Distinct index codes in index_eod
SELECT 'index_codes_in_eod' AS check_name, COUNT(DISTINCT code)::text FROM psx_index_eod
UNION ALL
-- i) Mutual funds count
SELECT 'mutual_funds_count' AS check_name, COUNT(*)::text FROM psx_mutual_funds
UNION ALL
-- j) Fund nav history rows
SELECT 'fund_nav_rows' AS check_name, COUNT(*)::text FROM psx_fund_nav_history
UNION ALL
-- k) Data source health rows
SELECT 'data_source_health' AS check_name, COUNT(*)::text FROM psx_data_source_health
UNION ALL
-- l) News count
SELECT 'news_count' AS check_name, COUNT(*)::text FROM psx_news;
"""
    run_query(cur, "Data quality checks (a–l)", data_quality_sql)

    # =====================================================================
    # 4. RLS STATUS
    # =====================================================================
    heading("4. RLS STATUS (per-table row-level security setting)")
    run_query(
        cur,
        "RLS enabled? relname, relrowsecurity",
        """SELECT relname,
                  relrowsecurity
           FROM pg_class
           WHERE relnamespace = 'public'::regnamespace
             AND relkind = 'r'
           ORDER BY relname;""",
    )

    # =====================================================================
    # 5. ALL INDEXES (NON-PK)
    # =====================================================================
    heading("5. ALL INDEXES (excluding primary-key constraints)")
    run_query(
        cur,
        "Non-PK indexes with definition",
        """SELECT tablename,
                  indexname,
                  indexdef
           FROM pg_indexes
           WHERE schemaname = 'public'
             AND indexname NOT IN (
                 SELECT constraint_name
                 FROM information_schema.table_constraints
                 WHERE constraint_type = 'PRIMARY KEY'
                   AND table_schema = 'public'
             )
           ORDER BY tablename, indexname;""",
    )

    # =====================================================================
    # 6. FOREIGN KEYS
    # =====================================================================
    heading("6. FOREIGN KEYS")
    run_query(
        cur,
        "All foreign key relationships",
        """SELECT tc.table_name,
                  kcu.column_name,
                  ccu.table_name AS foreign_table,
                  ccu.column_name AS foreign_column
           FROM information_schema.table_constraints tc
           JOIN information_schema.key_column_usage kcu
             ON tc.constraint_name = kcu.constraint_name
           JOIN information_schema.constraint_column_usage ccu
             ON tc.constraint_name = ccu.constraint_name
           WHERE tc.constraint_type = 'FOREIGN KEY'
             AND tc.table_schema = 'public'
           ORDER BY tc.table_name, kcu.ordinal_position;""",
    )

    # =====================================================================
    # DONE
    # =====================================================================
    cur.close()
    conn.close()

    elapsed = datetime.now() - start
    print(f"\n{SEP}")
    print(f"  AUDIT COMPLETE — {elapsed.total_seconds():.1f} seconds elapsed.")
    print(f"  No data was modified.")
    print(SEP)


if __name__ == "__main__":
    main()
