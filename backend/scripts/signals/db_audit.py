"""Read-only audit of the data the signals programme depends on.

Answers three questions before any research or backfill starts:

1. **Depth** — how many bars, how many symbols, how far back does psx_ohlcv
   actually go? Every horizon/fold decision depends on this.
2. **Storage** — how much room is left before a backfill becomes a problem?
   Supabase is a hard constraint here (no second account), so the announcement
   backfill is sized against this number, not guessed.
3. **Gaps** — current row counts for the tables the backfills will populate.

Writes nothing. Safe to run against production.

    python scripts/signals/db_audit.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from sqlalchemy import text  # noqa: E402

from app.repositories.base import connect  # noqa: E402

TABLES_OF_INTEREST = (
    "psx_ohlcv",
    "psx_dividends",
    "psx_announcements",
    "psx_signal_events",
    "psx_financials_quarterly",
    "psx_financials_annual",
    "psx_fipi_daily",
    "psx_index_eod",
    "psx_profile",
    "psx_market_snapshot",
    "psx_signal_cross_section",
    "psx_signal_forecasts",
    "filings",
    "macro_rates",
)


async def main() -> None:
    async with connect() as conn:
        print("=" * 72)
        print("OHLCV DEPTH")
        print("=" * 72)
        row = (await conn.execute(text("""
            SELECT count(*)                AS bars,
                   count(DISTINCT symbol)  AS symbols,
                   min(date)               AS first_bar,
                   max(date)               AS last_bar
            FROM psx_ohlcv
        """))).mappings().first()
        for k, v in dict(row).items():
            print(f"  {k:12s} {v}")

        print()
        print("  bars per symbol (distribution):")
        rows = (await conn.execute(text("""
            WITH per AS (
                SELECT symbol, count(*) AS n, max(date) AS last_bar
                FROM psx_ohlcv GROUP BY symbol
            )
            SELECT
                percentile_disc(0.10) WITHIN GROUP (ORDER BY n) AS p10,
                percentile_disc(0.50) WITHIN GROUP (ORDER BY n) AS p50,
                percentile_disc(0.90) WITHIN GROUP (ORDER BY n) AS p90,
                max(n)                                          AS max_n,
                count(*) FILTER (WHERE n >= 250)                AS symbols_250plus,
                count(*) FILTER (WHERE n >= 1000)               AS symbols_1000plus
            FROM per
        """))).mappings().first()
        for k, v in dict(rows).items():
            print(f"    {k:18s} {v}")

        print()
        print("  freshness (symbols by staleness of last bar):")
        rows = (await conn.execute(text("""
            WITH per AS (SELECT symbol, max(date) AS last_bar FROM psx_ohlcv GROUP BY symbol)
            SELECT
                count(*) FILTER (WHERE last_bar >= current_date - 7)   AS fresh_7d,
                count(*) FILTER (WHERE last_bar >= current_date - 30)  AS fresh_30d,
                count(*) FILTER (WHERE last_bar <  current_date - 365) AS stale_1y_plus,
                count(*)                                              AS total
            FROM per
        """))).mappings().first()
        for k, v in dict(rows).items():
            print(f"    {k:18s} {v}")

        print()
        print("=" * 72)
        print("STORAGE")
        print("=" * 72)
        rows = (await conn.execute(text("""
            SELECT c.relname AS table_name,
                   pg_size_pretty(pg_total_relation_size(c.oid)) AS total,
                   pg_total_relation_size(c.oid)                 AS total_bytes,
                   s.n_live_tup                                  AS approx_rows
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
            WHERE n.nspname = 'public' AND c.relkind = 'r'
            ORDER BY pg_total_relation_size(c.oid) DESC
            LIMIT 20
        """))).mappings().all()
        print(f"  {'table':34s} {'size':>10s} {'approx rows':>14s}")
        for r in rows:
            print(f"  {r['table_name']:34s} {r['total']:>10s} {str(r['approx_rows'] or '?'):>14s}")

        total = (await conn.execute(text(
            "SELECT pg_size_pretty(pg_database_size(current_database())) AS s, "
            "pg_database_size(current_database()) AS b"
        ))).mappings().first()
        print(f"\n  DATABASE TOTAL: {total['s']}  ({total['b']:,} bytes)")

        print()
        print("=" * 72)
        print("TABLE ROW COUNTS (exact)")
        print("=" * 72)
        for table in TABLES_OF_INTEREST:
            try:
                n = (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar()
                print(f"  {table:30s} {n:>12,}")
            except Exception as exc:  # table may not exist
                print(f"  {table:30s} {'ERROR':>12s}  ({type(exc).__name__})")

        print()
        print("=" * 72)
        print("CORPORATE ACTIONS (the adjustment-bias blocker)")
        print("=" * 72)
        try:
            rows = (await conn.execute(text("""
                SELECT payout_type, count(*) AS n,
                       min(ex_date) AS first_ex, max(ex_date) AS last_ex,
                       count(*) FILTER (WHERE ex_date IS NULL) AS null_ex_date
                FROM psx_dividends GROUP BY payout_type ORDER BY n DESC
            """))).mappings().all()
            for r in rows:
                print(f"  {str(r['payout_type']):14s} n={r['n']:<6} "
                      f"{r['first_ex']} -> {r['last_ex']}  null_ex={r['null_ex_date']}")
            n_sym = (await conn.execute(text(
                "SELECT count(DISTINCT symbol) FROM psx_dividends"
            ))).scalar()
            print(f"  symbols covered: {n_sym}")
        except Exception as exc:
            print(f"  ERROR: {exc}")

        print()
        print("=" * 72)
        print("ANNOUNCEMENT HISTORY (the PEAD blocker)")
        print("=" * 72)
        try:
            r = (await conn.execute(text("""
                SELECT count(*) AS n, min(posted_at) AS first, max(posted_at) AS last,
                       count(DISTINCT symbol) AS symbols
                FROM psx_announcements
            """))).mappings().first()
            print(f"  rows={r['n']:,}  symbols={r['symbols']}  {r['first']} -> {r['last']}")
        except Exception as exc:
            print(f"  ERROR: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
