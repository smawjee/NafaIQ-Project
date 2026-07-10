"""Watchlist data access (user_watchlist) with profile/snapshot enrichment."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

Executor = Any


async def fetch_watchlist_enriched(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    # Price resolves live snapshot -> latest daily close (psx_ohlcv), so a
    # symbol always shows a price outside market hours instead of a blank "—".
    # When falling back to EOD, change/change_pct are derived from the two most
    # recent closes. Mirrors the COALESCE(s.price, eod_close) pattern used by
    # the portfolio valuation queries.
    result = await conn.execute(
        text(
            """
            WITH ranked_close AS (
                SELECT
                    symbol,
                    close,
                    date,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                FROM psx_ohlcv
            ),
            eod AS (
                SELECT
                    latest.symbol,
                    latest.close AS eod_close,
                    latest.date  AS eod_date,
                    prev.close   AS prev_close
                FROM ranked_close latest
                LEFT JOIN ranked_close prev
                    ON prev.symbol = latest.symbol AND prev.rn = 2
                WHERE latest.rn = 1
            )
            SELECT
                w.symbol,
                COALESCE(p.name, w.symbol) AS company_name,
                COALESCE(p.sector, 'Other') AS sector,
                p.logoid,
                COALESCE(s.price, e.eod_close) AS price,
                COALESCE(
                    s.change,
                    CASE WHEN e.prev_close IS NOT NULL
                         THEN e.eod_close - e.prev_close END
                ) AS change,
                COALESCE(
                    s.change_pct,
                    CASE WHEN e.prev_close IS NOT NULL AND e.prev_close <> 0
                         THEN ROUND(((e.eod_close - e.prev_close) / e.prev_close) * 100, 2)
                    END
                ) AS change_pct,
                s.volume,
                COALESCE(s.refreshed_at, e.eod_date::timestamptz) AS last_updated
            FROM user_watchlist w
            LEFT JOIN psx_profile p ON upper(trim(p.symbol)) = upper(trim(w.symbol))
            LEFT JOIN psx_market_snapshot s ON upper(trim(s.symbol)) = upper(trim(w.symbol))
            LEFT JOIN eod e ON upper(trim(e.symbol)) = upper(trim(w.symbol))
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
