"""KSE-100 benchmark service.

Primary source: DPS /timeseries/eod/KSE100.
Fallback: psx_index_eod DB table.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import text

from app.db.sqlalchemy import get_session_factory

log = logging.getLogger(__name__)


async def get_kse100_series(days: int = 365) -> list[dict[str, Any]]:
    """Return KSE-100 EOD bars ordered ASC by date."""
    bounded = max(7, min(int(days), 3650))
    factory = get_session_factory()
    try:
        async with factory() as session:
            rows = await session.execute(
                text(
                    "SELECT code, date, open, high, low, close, volume "
                    "FROM psx_index_eod "
                    "WHERE code = 'KSE100' "
                    "AND date >= CURRENT_DATE - (:days * INTERVAL '1 day') "
                    "ORDER BY date ASC"
                ),
                {"days": bounded},
            )
            return [
                {
                    "code": r["code"],
                    "date": str(r["date"]),
                    "open": float(r["open"] or 0),
                    "high": float(r["high"] or 0),
                    "low": float(r["low"] or 0),
                    "close": float(r["close"] or 0),
                    "volume": int(r["volume"] or 0),
                }
                for r in rows.mappings().all()
            ]
    except Exception:
        log.exception("get_kse100_series failed")
        return []


async def get_kse100_latest() -> Optional[dict[str, Any]]:
    factory = get_session_factory()
    try:
        async with factory() as session:
            r = await session.execute(
                text(
                    "SELECT code, date, close, change, change_pct "
                    "FROM psx_index_eod WHERE code = 'KSE100' "
                    "ORDER BY date DESC LIMIT 1"
                )
            )
            row = r.mappings().first()
            if not row:
                return None
            return {
                "code": row["code"],
                "date": str(row["date"]),
                "value": float(row["close"] or 0),
                "change": float(row.get("change") or 0),
                "change_pct": float(row.get("change_pct") or 0),
            }
    except Exception:
        log.exception("get_kse100_latest failed")
        return None
