"""Promote clean immutable raw DPS observations into the V4 canonical view.

This is an explicit one-time operation. It never repairs OHLC values and keeps
PSX LDCP/traded-range semantics intact. Rows that fail basic presence checks
are excluded rather than rewritten.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.db.supabase import async_execute, select_all


def _valid(row: dict) -> bool:
    try:
        close = float(row["close"])
        high = float(row["high"])
        low = float(row["low"])
        return close > 0 and high > 0 and low > 0
    except (KeyError, TypeError, ValueError):
        return False


async def main() -> None:
    raw = await select_all("psx_ohlcv_raw", "*", order_by="source_record_hash")
    rows = []
    for row in raw:
        if row.get("source") != "dps_historical" or not _valid(row):
            continue
        rows.append({
            "symbol": row["symbol"],
            "date": row["date"],
            "raw_source": row["source"],
            "raw_record_hash": row["source_record_hash"],
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row.get("close"),
            "volume": row.get("volume"),
            "ldcp": row.get("ldcp"),
            "verification_status": "VERIFIED",
            "verification_version": "dps-v4-presence-only-1",
            "verified_at": datetime.now(timezone.utc).isoformat(),
        })
    if rows:
        await async_execute(lambda c: c.table("psx_ohlcv_verified").insert(rows))
    print(f"verified {len(rows)} bars; excluded {len(raw) - len(rows)}")


if __name__ == "__main__":
    asyncio.run(main())
