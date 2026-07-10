"""Watchlist data access (user_watchlist) with profile/snapshot enrichment."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

Executor = Any


async def fetch_watchlist_enriched(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            """
            SELECT
                w.symbol,
                COALESCE(p.name, w.symbol) AS company_name,
                COALESCE(p.sector, 'Other') AS sector,
                p.logoid,
                s.price,
                s.change,
                s.change_pct,
                s.volume,
                s.refreshed_at AS last_updated
            FROM user_watchlist w
            LEFT JOIN psx_profile p ON upper(trim(p.symbol)) = upper(trim(w.symbol))
            LEFT JOIN psx_market_snapshot s ON upper(trim(s.symbol)) = upper(trim(w.symbol))
            WHERE w.user_id = :uid
            ORDER BY w.added_at DESC
            """
        ),
        {"uid": user_id},
    )
    return [
        {
            "symbol": r["symbol"],
            "company_name": r["company_name"],
            "sector": r["sector"],
            "logoid": r["logoid"],
            "price": float(r["price"]) if r["price"] is not None else None,
            "change": float(r["change"]) if r["change"] is not None else None,
            "change_pct": float(r["change_pct"]) if r["change_pct"] is not None else None,
            "volume": int(r["volume"]) if r["volume"] else 0,
            "last_updated": r["last_updated"].isoformat() if r["last_updated"] else None,
        }
        for r in result.mappings().all()
    ]
