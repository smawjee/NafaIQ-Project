"""Apply the extended price-alert conditions migration via the Supabase pooler.

Widens the `price_alerts.condition` CHECK constraint so the four new alert types
(pct_change_*, volume_spike, high_52w/low_52w) can be stored. Until this runs,
the API accepts them and Postgres rejects the INSERT.

Usage (from backend/):
    python -m scripts.apply_price_alert_conditions_migration

Idempotent: the migration drops the constraint IF EXISTS before re-adding it,
and the ledger insert is ON CONFLICT DO NOTHING.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ("20260730090000_price_alerts_extended_conditions.sql",)

# The values the constraint must accept once this has run.
EXPECTED = (
    "above", "below", "cross_above", "cross_below",
    "pct_change_above", "pct_change_below",
    "volume_spike", "high_52w", "low_52w",
)


async def main() -> None:
    load_dotenv(ROOT / ".env")
    required = ("SUPABASE_DATABASE_PASSWORD", "SUPABASE_POOLER_HOST", "SUPABASE_POOLER_USER")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"missing environment variables: {', '.join(missing)}")

    connection = await asyncpg.connect(
        host=os.environ["SUPABASE_POOLER_HOST"],
        port=int(os.getenv("SUPABASE_POOLER_PORT", "6543")),
        user=os.environ["SUPABASE_POOLER_USER"],
        password=os.environ["SUPABASE_DATABASE_PASSWORD"],
        database="postgres",
        ssl="require",
        timeout=30,
        statement_cache_size=0,
    )
    try:
        for filename in MIGRATIONS:
            sql = (ROOT / "database" / "migrations" / filename).read_text(encoding="utf-8")
            print(f"Applying {filename} ...")
            await connection.execute(sql)
            print("  ok")

        # Verify rather than trust: read the constraint back and confirm every
        # new value is present. A migration that "ran" but left the old
        # constraint in place would otherwise only surface as a 500 the first
        # time a user saves a volume alert.
        definition = await connection.fetchval(
            """
            SELECT pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            WHERE t.relname = 'price_alerts' AND c.conname = 'price_alerts_condition_check'
            """
        )
        print(f"\nconstraint: {definition}")
        missing_vals = [v for v in EXPECTED if f"'{v}'" not in (definition or "")]
        if missing_vals:
            raise SystemExit(f"FAILED: constraint does not accept {missing_vals}")
        print(f"verified: all {len(EXPECTED)} conditions accepted")

        # And prove the threshold rule actually admits a 52-week alert. Checking
        # the condition list alone was not enough: the first run of this
        # migration left `price > 0` in place, so `high_52w` passed the condition
        # CHECK and was then rejected by the threshold CHECK.
        threshold_def = await connection.fetchval(
            """
            SELECT pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            WHERE t.relname = 'price_alerts'
              AND c.conname = 'price_alerts_price_positive'
            """
        )
        print(f"threshold rule: {threshold_def}")
        if "high_52w" not in (threshold_def or ""):
            raise SystemExit(
                "FAILED: price_alerts_price_positive is not condition-aware, so "
                "high_52w/low_52w (threshold 0) cannot be inserted"
            )
        print("verified: threshold rule admits the threshold-less conditions")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
