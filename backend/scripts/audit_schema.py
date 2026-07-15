# -*- coding: utf-8 -*-
"""
Supabase Schema Audit Script
=============================
Read-only audit of all tables, columns, constraints, indexes, RLS,
row counts, data quality, and column-level null analysis.

Usage:  python -m scripts.audit_schema
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DB_CONFIG = {
    "host": os.environ.get("SUPABASE_POOLER_HOST", "aws-1-ap-southeast-1.pooler.supabase.com"),
    "port": int(os.environ.get("SUPABASE_POOLER_PORT", "6543")),
    "user": os.environ.get("SUPABASE_POOLER_USER", "postgres.gmonfgxmjgzipnbhgimv"),
    "dbname": "postgres",
    "password": os.environ.get("SUPABASE_DATABASE_PASSWORD", ""),
    "sslmode": "require",
    "connect_timeout": 30,
}


def run_query(cursor, label, sql):
    sep = "=" * 100
    print(f"\n{sep}")
    print(f"  {label}")
    print(sep)
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]
        print("  " + " | ".join(f"{c:<20}" for c in col_names))
        print("  " + "-" * (22 * len(col_names)))
        for row in rows:
            vals = []
            for v in row:
                s = str(v) if v is not None else "NULL"
                vals.append(f"{s:<20}")
            print("  " + " | ".join(vals))
        print(f"\n  -> {len(rows)} row(s) returned.\n")
    except Exception as e:
        print(f"  ERROR: {e}\n")


def main():
    if not DB_CONFIG["password"]:
        print(
            "ERROR: SUPABASE_DATABASE_PASSWORD is not set.\n"
            "Set it in backend/.env or the environment before running this audit.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Supabase Schema Audit - {datetime.now().isoformat()}")
    print(f"Database : {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}")
    print(f"User     : {DB_CONFIG['user']}")

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    # 1. ALL TABLES
    run_query(
        cur,
        "1. ALL TABLES (name, size, column count, comment)",
        """SELECT table_name,
                  pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) AS size,
                  (SELECT COUNT(*)
                   FROM information_schema.columns
                   WHERE table_schema = 'public'
                     AND table_name = t.table_name) AS column_count,
                  obj_description(quote_ident(table_name)::regclass, 'pg_class') AS comment
           FROM information_schema.tables t
           WHERE table_schema = 'public'
             AND table_type = 'BASE TABLE'
           ORDER BY table_name;""")

    # 2. ALL COLUMNS
    run_query(
        cur,
        "2. ALL COLUMNS (type, nullable, default, max length)",
        """SELECT table_name,
                  column_name,
                  data_type,
                  is_nullable,
                  column_default,
                  character_maximum_length
           FROM information_schema.columns
           WHERE table_schema = 'public'
           ORDER BY table_name, ordinal_position;""")

    # 3a. PRIMARY KEYS
    run_query(
        cur,
        "3a. PRIMARY KEYS",
        """SELECT tc.table_name,
                  kc.column_name,
                  tc.constraint_name
           FROM information_schema.table_constraints tc
           JOIN information_schema.key_column_usage kc
             ON tc.constraint_name = kc.constraint_name
           WHERE tc.constraint_type = 'PRIMARY KEY'
             AND tc.table_schema = 'public'
           ORDER BY tc.table_name, kc.ordinal_position;""")

    # 3b. FOREIGN KEYS
    run_query(
        cur,
        "3b. FOREIGN KEYS",
        """SELECT tc.table_name AS source_table,
                  kcu.column_name AS source_column,
                  ccu.table_name AS target_table,
                  ccu.column_name AS target_column,
                  tc.constraint_name
           FROM information_schema.table_constraints tc
           JOIN information_schema.key_column_usage kcu
             ON tc.constraint_name = kcu.constraint_name
           JOIN information_schema.constraint_column_usage ccu
             ON tc.constraint_name = ccu.constraint_name
           WHERE tc.constraint_type = 'FOREIGN KEY'
             AND tc.table_schema = 'public'
           ORDER BY tc.table_name;""")

    # 4. ALL INDEXES (non-PK)
    run_query(
        cur,
        "4. ALL INDEXES (excluding PK constraints)",
        """SELECT schemaname, tablename, indexname, indexdef
           FROM pg_indexes
           WHERE schemaname = 'public'
             AND indexname NOT IN (
                 SELECT constraint_name
                 FROM information_schema.table_constraints
                 WHERE constraint_type = 'PRIMARY KEY'
                   AND table_schema = 'public'
             )
           ORDER BY tablename, indexname;""")

    # 5. ROW COUNTS
    run_query(
        cur,
        "5. ROW COUNTS (every public table)",
        """WITH tbl AS (
             SELECT table_name
             FROM information_schema.tables
             WHERE table_schema = 'public'
               AND table_type = 'BASE TABLE'
           )
           SELECT t.table_name,
                  COALESCE(
                    (SELECT reltuples::bigint
                     FROM pg_class
                     WHERE relname = t.table_name
                       AND relnamespace = 'public'::regnamespace),
                    0
                  ) AS row_estimate
           FROM tbl t
           ORDER BY t.table_name;""")

    # 6. RLS STATUS
    run_query(
        cur,
        "6. ROW-LEVEL SECURITY (RLS) STATUS",
        """SELECT relname,
                  relrowsecurity,
                  relforcerowsecurity
           FROM pg_class
           WHERE relnamespace = 'public'::regnamespace
             AND relkind = 'r'
           ORDER BY relname;""")

    # 7a. OHLCV bad rows
    run_query(cur, "7a. OHLCV rows where open < low OR high < close",
              "SELECT COUNT(*) AS bad_ohlcv_rows FROM psx_ohlcv WHERE open < low OR high < close;")

    # 7b. profiles without symbol
    run_query(cur, "7b. psx_profile rows without symbol",
              "SELECT COUNT(*) AS profiles_no_symbol FROM psx_profile WHERE symbol IS NULL;")

    # 7c. orphan market_snapshot
    run_query(cur, "7c. Orphan market_snapshot (symbol not in psx_profile)",
              """SELECT COUNT(*) AS orphan_snapshot
                 FROM psx_market_snapshot ms
                 LEFT JOIN psx_profile p ON ms.symbol = p.symbol
                 WHERE p.symbol IS NULL;""")

    # 7d. filings without text_content
    run_query(cur, "7d. Filings without text_content",
              "SELECT COUNT(*) AS filings_no_text FROM filings WHERE text_content IS NULL;")

    # 7e. TV sector mapping
    run_query(cur, "7e. psx_profile still with sector = 'Finance' (TV mapping check)",
              "SELECT COUNT(*) AS tv_sector_remaining FROM psx_profile WHERE sector = 'Finance';")

    # 7f. SHARIAH count
    run_query(cur, "7f. SHARIAH-stock count",
              "SELECT COUNT(*) AS shariah_flagged FROM psx_profile WHERE is_shariah = true;")

    # 7g. OHLCV date range
    run_query(cur, "7g. OHLCV date range & symbol coverage",
              """SELECT MIN(date) AS earliest,
                        MAX(date) AS latest,
                        COUNT(DISTINCT symbol) AS symbols_with_data
                 FROM psx_ohlcv;""")

    # 7h. index_eod distinct codes
    run_query(cur, "7h. psx_index_eod - distinct index codes",
              "SELECT COUNT(DISTINCT code) AS index_codes FROM psx_index_eod;")

    # 7i. index_eod per-code
    run_query(cur, "7i. psx_index_eod - per-index rows & latest date",
              """SELECT code,
                        COUNT(*) AS rows,
                        MAX(date) AS latest_date
                 FROM psx_index_eod
                 GROUP BY code
                 ORDER BY code;""")

    # 7j. mutual fund count
    run_query(cur, "7j. Mutual funds - fund count",
              "SELECT COUNT(*) AS funds_with_history FROM psx_mutual_funds;")

    # 7k. fund codes in nav history
    run_query(cur, "7k. Mutual funds - distinct fund codes in nav_history",
              "SELECT COUNT(DISTINCT fund_code) AS codes_in_history FROM psx_fund_nav_history;")

    # 7l. sector distribution
    run_query(cur, "7l. psx_profile - top 20 sector distribution",
              """SELECT sector, COUNT(*)
                 FROM psx_profile
                 GROUP BY sector
                 ORDER BY COUNT(*) DESC
                 LIMIT 20;""")

    # 8a. psx_profile null counts
    run_query(cur, "8a. psx_profile - column-level null counts",
              """SELECT 'symbol' AS col,
                        COUNT(*) FILTER (WHERE symbol IS NULL) AS nulls,
                        COUNT(*) AS total
                 FROM psx_profile
                 UNION ALL
                 SELECT 'sector',
                        COUNT(*) FILTER (WHERE sector IS NULL),
                        COUNT(*)
                 FROM psx_profile
                 UNION ALL
                 SELECT 'name',
                        COUNT(*) FILTER (WHERE name IS NULL),
                        COUNT(*)
                 FROM psx_profile
                 UNION ALL
                 SELECT 'listed_shares',
                        COUNT(*) FILTER (WHERE listed_shares IS NULL),
                        COUNT(*)
                 FROM psx_profile
                 UNION ALL
                 SELECT 'listed_in',
                        COUNT(*) FILTER (WHERE listed_in IS NULL),
                        COUNT(*)
                 FROM psx_profile;""")

    # 8b. psx_ohlcv null counts
    run_query(cur, "8b. psx_ohlcv - column-level null counts",
              """SELECT 'symbol' AS col,
                        COUNT(*) FILTER (WHERE symbol IS NULL) AS nulls,
                        COUNT(*) AS total
                 FROM psx_ohlcv
                 UNION ALL
                 SELECT 'open',
                        COUNT(*) FILTER (WHERE open IS NULL),
                        COUNT(*)
                 FROM psx_ohlcv
                 UNION ALL
                 SELECT 'high',
                        COUNT(*) FILTER (WHERE high IS NULL),
                        COUNT(*)
                 FROM psx_ohlcv
                 UNION ALL
                 SELECT 'low',
                        COUNT(*) FILTER (WHERE low IS NULL),
                        COUNT(*)
                 FROM psx_ohlcv
                 UNION ALL
                 SELECT 'close',
                        COUNT(*) FILTER (WHERE close IS NULL),
                        COUNT(*)
                 FROM psx_ohlcv
                 UNION ALL
                 SELECT 'volume',
                        COUNT(*) FILTER (WHERE volume IS NULL),
                        COUNT(*)
                 FROM psx_ohlcv;""")

    cur.close()
    conn.close()
    print(f"\n{'=' * 100}")
    print("  Audit complete. No data was modified.")
    print(f"{'=' * 100}")


if __name__ == "__main__":
    main()
