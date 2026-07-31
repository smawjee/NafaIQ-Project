"""Watchlist data access (user_watchlist) with profile/snapshot enrichment."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any


async def count_watchlist(conn: Executor, user_id: str) -> int:
    """How many symbols the user is watching (for the max_watchlist quota)."""
    result = await conn.execute(
        text("SELECT COUNT(*) AS n FROM user_watchlist WHERE user_id = :uid"),
        {"uid": user_id},
    )
    row = result.mappings().first()
    return int(row["n"]) if row else 0


async def watchlist_has_symbol(conn: Executor, user_id: str, symbol: str) -> bool:
    """True if the symbol is already watched. Checked before the quota so a
    re-add of an existing symbol is idempotent rather than a 403 at the cap."""
    result = await conn.execute(
        text(
            """
            SELECT 1 FROM user_watchlist
            WHERE user_id = :uid AND upper(trim(symbol)) = upper(trim(:sym))
            LIMIT 1
            """
        ),
        {"uid": user_id, "sym": symbol},
    )
    return result.mappings().first() is not None


async def insert_watchlist_symbol(
    conn: Executor, user_id: str, symbol: str, notes: Optional[str] = None
) -> dict[str, Any]:
    """Upsert one symbol onto the user's watchlist.

    ON CONFLICT DO UPDATE (not DO NOTHING) so the statement always RETURNINGs a
    row — DO NOTHING returns nothing on a duplicate, which would make an
    idempotent re-add look like a failed insert to the caller.
    """
    result = await conn.execute(
        text(
            """
            INSERT INTO user_watchlist (user_id, symbol, notes)
            VALUES (:uid, upper(trim(:sym)), :notes)
            ON CONFLICT (user_id, symbol) DO UPDATE
                SET notes = COALESCE(EXCLUDED.notes, user_watchlist.notes)
            RETURNING id, symbol, added_at, notify_push, notify_email, notes
            """
        ),
        {"uid": user_id, "sym": symbol, "notes": notes},
    )
    row = result.mappings().first()
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "added_at": row["added_at"].isoformat() if row["added_at"] else None,
        "notify_push": bool(row["notify_push"]),
        "notify_email": bool(row["notify_email"]),
        "notes": row["notes"],
    }


async def delete_watchlist_symbol(conn: Executor, user_id: str, symbol: str) -> bool:
    """Remove a symbol; True if a row was actually deleted."""
    result = await conn.execute(
        text(
            """
            DELETE FROM user_watchlist
            WHERE user_id = :uid AND upper(trim(symbol)) = upper(trim(:sym))
            RETURNING id
            """
        ),
        {"uid": user_id, "sym": symbol},
    )
    return result.mappings().first() is not None


async def clear_watchlist(conn: Executor, user_id: str) -> int:
    """Remove EVERY symbol from this user's watchlist; returns the count."""
    result = await conn.execute(
        text("DELETE FROM user_watchlist WHERE user_id = :uid RETURNING id"),
        {"uid": user_id},
    )
    return len(result.mappings().fetchall())


async def fetch_watchlist_enriched(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    # Price resolves live snapshot -> latest daily close (psx_ohlcv), so a
    # symbol always shows a price outside market hours instead of a blank "—".
    # When falling back to EOD, change/change_pct are derived from the two most
    # recent closes. Mirrors the COALESCE(s.price, eod_close) pattern used by
    # the portfolio valuation queries.
    #
    # The EOD lookup MUST stay a per-symbol LATERAL with LIMIT 2. Ranking all of
    # psx_ohlcv up front (WITH ranked_close AS (... ROW_NUMBER() OVER (PARTITION
    # BY symbol ...) FROM psx_ohlcv)) and filtering to rn <= 2 afterwards makes
    # Postgres materialise and sort ~1M rows to serve a handful of watched
    # symbols — that took ~15s per request and blew the 45s asyncpg
    # command_timeout under concurrency. The LATERAL lets the planner walk
    # psx_ohlcv_symbol_date_key backwards and stop after 2 index tuples.
    #
    # Likewise, only the (tiny) user_watchlist side is wrapped in upper(trim()).
    # Wrapping the big-table side too (upper(trim(p.symbol)) = ...) makes the
    # join predicate non-sargable and forfeits psx_profile_pkey /
    # psx_market_snapshot_symbol_key, forcing a seq scan of each.
    result = await conn.execute(
        text(
            """
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
            LEFT JOIN psx_profile p ON p.symbol = upper(trim(w.symbol))
            LEFT JOIN psx_market_snapshot s ON s.symbol = upper(trim(w.symbol))
            LEFT JOIN LATERAL (
                SELECT
                    (array_agg(t.close ORDER BY t.date DESC))[1] AS eod_close,
                    (array_agg(t.date  ORDER BY t.date DESC))[1] AS eod_date,
                    (array_agg(t.close ORDER BY t.date DESC))[2] AS prev_close
                FROM (
                    SELECT o.close, o.date
                    FROM psx_ohlcv o
                    WHERE o.symbol = upper(trim(w.symbol))
                    ORDER BY o.date DESC
                    LIMIT 2
                ) t
            ) e ON TRUE
            WHERE w.user_id = :uid
            ORDER BY w.added_at DESC, w.id DESC
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
