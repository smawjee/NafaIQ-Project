"""Verify migration 20260715030000 took effect."""
from __future__ import annotations

import os
from dotenv import load_dotenv
import psycopg2

load_dotenv(".env")
conn = psycopg2.connect(
    host=os.environ["SUPABASE_POOLER_HOST"],
    port=int(os.environ["SUPABASE_POOLER_PORT"]),
    user=os.environ["SUPABASE_POOLER_USER"],
    password=os.environ["SUPABASE_DATABASE_PASSWORD"],
    dbname="postgres",
    sslmode="require",
)
cur = conn.cursor()

cur.execute("""
    SELECT indexname
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND indexname IN (
          'idx_psx_fa_sym_year', 'idx_psx_fq_sym_period',
          'idx_psx_ohlcv_split', 'idx_psx_profile_shariah'
      )
    ORDER BY indexname
""")
print("Indexes created:", [r[0] for r in cur.fetchall()])

cur.execute("""
    SELECT policyname, tablename
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename IN (
          'macro_rates', 'psx_mutual_funds', 'psx_fund_nav_history',
          'psx_news', 'filings', 'psx_unusual_activity',
          'psx_financials_annual', 'psx_financials_quarterly'
      )
    ORDER BY tablename
""")
policies = cur.fetchall()
print(f"Policies on new tables ({len(policies)}):")
for p, t in policies:
    print(f"  {t}.{p}")

cur.execute("""
    SELECT table_name, column_name, is_nullable
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND ((table_name = 'psx_ohlcv' AND column_name IN ('is_adjusted', 'adjustment_factor'))
        OR (table_name = 'psx_profile' AND column_name = 'is_shariah'))
    ORDER BY table_name, column_name
""")
print("Not-null status after tightening:")
for t, c, n in cur.fetchall():
    print(f"  {t}.{c}: nullable={n}")

cur.execute("""
    SELECT table_name, has_table_privilege('anon', table_name, 'SELECT') AS anon_sel
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name IN (
          'macro_rates', 'psx_mutual_funds', 'psx_fund_nav_history',
          'psx_news', 'filings', 'psx_unusual_activity',
          'psx_financials_annual', 'psx_financials_quarterly'
      )
    ORDER BY table_name
""")
print("anon SELECT grants:")
for t, g in cur.fetchall():
    print(f"  {t}: {g}")

conn.close()
