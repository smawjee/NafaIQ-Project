"""Price-alert data access (price_alerts table)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any


def _price_alert(r: Any) -> dict[str, Any]:
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "type": "stock_price",
        "symbol": r["symbol"],
        "condition": r["condition"],
        "price": float(r["price"]),
        "enabled": r["enabled"],
        "triggered_at": str(r["triggered_at"]) if r["triggered_at"] else None,
        "last_triggered_at": str(r["last_triggered_at"]) if r["last_triggered_at"] else None,
        "one_time": r["one_time"],
        "notify_push": r["notify_push"],
        "notify_email": r["notify_email"],
        "notes": r["notes"],
        "created_at": str(r["created_at"]),
    }


async def list_price_alerts(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    rows = await conn.execute(
        text(
            "SELECT id, user_id, symbol, condition, price, enabled, "
            "triggered_at, created_at, one_time, last_triggered_at, "
            "notify_push, notify_email, notes "
            "FROM price_alerts WHERE user_id = :uid "
            "ORDER BY created_at DESC"
        ),
        {"uid": user_id},
    )
    return [_price_alert(r) for r in rows.mappings().all()]


async def insert_price_alert(
    conn: Executor,
    user_id: str,
    symbol: str,
    condition: str,
    price: float,
    one_time: bool,
    notify_push: bool,
    notify_email: bool,
    notes: Optional[str],
) -> dict[str, Any]:
    row = await conn.execute(
        text(
            "INSERT INTO price_alerts "
            "(user_id, symbol, condition, price, enabled, one_time, "
            " notify_push, notify_email, notes) "
            "VALUES (:uid, :sym, :cond, :price, true, :ot, :np, :ne, :notes) "
            "RETURNING id, user_id, symbol, condition, price, enabled, "
            "          triggered_at, created_at, one_time, last_triggered_at, "
            "          notify_push, notify_email, notes"
        ),
        {
            "uid": user_id,
            "sym": symbol.upper(),
            "cond": condition,
            "price": price,
            "ot": one_time,
            "np": notify_push,
            "ne": notify_email,
            "notes": notes,
        },
    )
    return _price_alert(row.mappings().first())


async def count_price_alerts(conn: Executor, user_id: str) -> int:
    result = await conn.execute(
        text("SELECT COUNT(*) FROM price_alerts WHERE user_id = :uid"),
        {"uid": user_id},
    )
    return int(result.scalar() or 0)


async def find_active_price_alert(
    conn: Executor, user_id: str, symbol: str, condition: str, price: float
) -> Optional[dict[str, Any]]:
    """Return an existing enabled alert with the same (symbol, condition, price)
    for dedup — so re-arming the same alert doesn't create duplicate rows."""
    rows = await conn.execute(
        text(
            "SELECT id, user_id, symbol, condition, price, enabled, "
            "triggered_at, created_at, one_time, last_triggered_at, "
            "notify_push, notify_email, notes "
            "FROM price_alerts "
            "WHERE user_id = :uid AND symbol = :sym AND condition = :cond "
            # Round both sides: the bound price is a float and the column is
            # NUMERIC, so a bare `=` misses due to float representation.
            "AND ROUND(price, 2) = ROUND(CAST(:price AS numeric), 2) "
            "AND enabled = TRUE LIMIT 1"
        ),
        {"uid": user_id, "sym": symbol.upper(), "cond": condition, "price": price},
    )
    r = rows.mappings().first()
    return _price_alert(r) if r else None


async def delete_price_alert(conn: Executor, user_id: str, alert_id: int) -> Optional[int]:
    row = await conn.execute(
        text("DELETE FROM price_alerts WHERE id = :id AND user_id = :uid RETURNING id"),
        {"id": alert_id, "uid": user_id},
    )
    return alert_id if row.first() else None


async def fetch_enabled_price_alerts(conn: Executor) -> list[dict[str, Any]]:
    rows = await conn.execute(
        text(
            "SELECT id, user_id, symbol, condition, price, one_time, "
            "last_triggered_at, notify_push, notify_email "
            "FROM price_alerts WHERE enabled = TRUE"
        )
    )
    return [dict(r) for r in rows.mappings().all()]


async def fetch_symbol_stats(
    conn: Executor, symbols: list[str], *, lookback_days: int = 365
) -> dict[str, dict[str, Any]]:
    """52-week high/low and average volume for many symbols in ONE query.

    Serves the volume_spike and high_52w/low_52w conditions. Batched on purpose:
    the evaluator runs every 60 seconds over every enabled alert, so a per-alert
    query would be an N+1 firing 1,440 times a day per alert. One aggregate over
    the (symbol, date DESC) index covers the whole tick.

    `avg_volume` excludes today's own bar implicitly — psx_ohlcv is written by
    the nightly backfill, so the newest row is yesterday's close. Comparing live
    intraday volume against an average that already contains it would damp the
    very spike we are looking for.
    """
    if not symbols:
        return {}
    rows = await conn.execute(
        text(
            """
            SELECT symbol,
                   MAX(high)        AS high_52w,
                   MIN(low)         AS low_52w,
                   AVG(volume)      AS avg_volume,
                   COUNT(*)         AS bars
            FROM psx_ohlcv
            WHERE symbol = ANY(:syms)
              AND date >= CURRENT_DATE - MAKE_INTERVAL(days => :days)
            GROUP BY symbol
            """
        ),
        {"syms": [s.upper() for s in symbols], "days": int(lookback_days)},
    )
    out: dict[str, dict[str, Any]] = {}
    for r in rows.mappings().all():
        out[r["symbol"]] = {
            "high_52w": float(r["high_52w"]) if r["high_52w"] is not None else None,
            "low_52w": float(r["low_52w"]) if r["low_52w"] is not None else None,
            "avg_volume": float(r["avg_volume"]) if r["avg_volume"] is not None else None,
            "bars": int(r["bars"] or 0),
        }
    return out


async def mark_price_alert_triggered(
    conn: Executor, alert_id: int, disable: bool
) -> None:
    sql = (
        "UPDATE price_alerts SET last_triggered_at = now(), "
        "triggered_at = COALESCE(triggered_at, now())"
    )
    if disable:
        sql += ", enabled = FALSE"
    sql += " WHERE id = :id"
    await conn.execute(text(sql), {"id": alert_id})
