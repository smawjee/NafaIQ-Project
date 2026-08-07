"""Intraday (5-minute) bar capture and reads.

Background: the only price history the system stored was `psx_ohlcv` — one bar
per day. Both live tables (`psx_market_snapshot`, `psx_index_live_snapshot`) are
upsert-on-key, so each refresh overwrote the previous tick and no series
survived. That is why the chart's "1D" timeframe had nothing to draw.

`psx_intraday` fills the gap. The scheduler samples the market snapshot every
minute during market hours; each sample is folded into the 5-minute bucket it
lands in. Everything in this module that decides *what* to write is a pure
function so it can be tested without a database — only `capture_snapshot` and
`intraday` touch Supabase.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

import structlog

from app.db.supabase import async_execute
from app.services.market._base import get_cache
from app.services.memcache import mem_cache

log = structlog.get_logger()

BUCKET_MINUTES = 5
PKT = timezone(timedelta(hours=5))

# Serve the intraday read from memory for one bucket-refresh cycle. The writer
# runs every 60s, so a shorter TTL would only add Supabase round-trips without
# ever surfacing a newer bar.
TTL_INTRADAY = 30.0

# How many trading sessions the chart may ask for, and how long rows survive.
MAX_SESSIONS = 5
RETENTION_DAYS = 10


def bucket_start(moment: datetime, minutes: int = BUCKET_MINUTES) -> datetime:
    """Floor `moment` to the start of its bucket, in UTC.

    A naive datetime is read as UTC — the callers here all pass aware values,
    but a silent local-time reinterpretation would corrupt every bucket, so the
    assumption is made explicit rather than left to `astimezone`'s default.
    """
    aware = moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment
    utc = aware.astimezone(timezone.utc)
    return utc.replace(minute=utc.minute - (utc.minute % minutes), second=0, microsecond=0)


def session_date_for(moment: datetime) -> date:
    """The PKT trading date a UTC instant belongs to.

    PSX trades 09:30-15:30 PKT, which is 04:30-10:30 UTC, so a session never
    straddles UTC midnight and a plain timezone conversion is sufficient.
    """
    aware = moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment
    return aware.astimezone(PKT).date()


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and out not in (float("inf"), float("-inf")) else None


def merge_sample(
    existing: dict[str, Any] | None,
    *,
    symbol: str,
    price: float,
    ts: datetime,
    day_high: Any = None,
    day_low: Any = None,
    volume: Any = None,
) -> dict[str, Any]:
    """Fold one snapshot sample into its bucket and return the row to upsert.

    First sample of a bucket sets `open`; later samples widen `high`/`low` and
    move `close`. `day_high`/`day_low` are session-wide extremes, so they are
    only allowed to widen a bucket that already exists — seeding a fresh bucket
    with them would draw a candle spanning the whole day's range at whatever
    minute the bucket opened.

    `cum_volume` never decreases: the snapshot is day-cumulative, and a
    momentarily stale read must not make a later bucket look emptier than an
    earlier one (the reader diffs consecutive buckets and would emit a
    negative).
    """
    prev_high = _num((existing or {}).get("high"))
    prev_low = _num((existing or {}).get("low"))
    prev_vol = _num((existing or {}).get("cum_volume")) or 0.0

    highs = [price, prev_high]
    lows = [price, prev_low]
    if existing is not None:
        # Widen an in-progress bucket toward the session extremes only if the
        # snapshot has already printed through them.
        highs.append(_num(day_high))
        lows.append(_num(day_low))

    cum = _num(volume)
    # A stored row whose `open` failed to parse falls back to the current price
    # rather than to None — the column is NOT NULL, and a dropped write would
    # lose the whole bucket over one bad field.
    prev_open = _num((existing or {}).get("open"))
    return {
        "symbol": symbol,
        "ts": bucket_start(ts).isoformat(),
        "session_date": session_date_for(ts).isoformat(),
        "open": prev_open if prev_open is not None else price,
        "high": max(v for v in highs if v is not None),
        "low": min(v for v in lows if v is not None),
        "close": price,
        "cum_volume": int(max(cum or 0.0, prev_vol)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def to_bars(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Shape stored rows into chart-ready bars, oldest first.

    Turns day-cumulative `cum_volume` into per-bar volume by diffing
    consecutive buckets *within a session*. The first bar of each session keeps
    its cumulative value — it is the volume traded since the open, which is
    exactly that bar's volume. A diff is clamped at zero so a snapshot that
    reset or arrived out of order cannot emit a negative bar.
    """
    ordered = sorted(
        (r for r in rows if r.get("ts") is not None),
        key=lambda r: str(r["ts"]),
    )
    out: list[dict[str, Any]] = []
    prev_cum_by_session: dict[str, float] = {}
    for row in ordered:
        session = str(row.get("session_date") or "")
        cum = _num(row.get("cum_volume")) or 0.0
        prev = prev_cum_by_session.get(session)
        volume = cum if prev is None else max(0.0, cum - prev)
        prev_cum_by_session[session] = cum
        out.append(
            {
                "ts": _iso_utc(row["ts"]),
                "session_date": session or None,
                "open": _num(row.get("open")) or 0.0,
                "high": _num(row.get("high")) or 0.0,
                "low": _num(row.get("low")) or 0.0,
                "close": _num(row.get("close")) or 0.0,
                "volume": int(volume),
            }
        )
    return out


def _iso_utc(value: Any) -> str:
    """Normalise a stored timestamp to an ISO-8601 UTC string.

    PostgREST hands back `2026-08-06T09:35:00+00:00`, tests hand back
    datetimes, and a hand-applied migration could yield either. The frontend
    parses this with `new Date()`, which needs the offset present.
    """
    if isinstance(value, datetime):
        aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        return aware.astimezone(timezone.utc).isoformat()
    text = str(value)
    return text if ("+" in text[10:] or text.endswith("Z")) else f"{text}+00:00"


def latest_sessions(bars: list[dict[str, Any]], sessions: int) -> list[dict[str, Any]]:
    """Keep only the newest `sessions` trading days present in `bars`."""
    if sessions <= 0:
        return []
    seen = sorted({b["session_date"] for b in bars if b.get("session_date")})
    if not seen:
        return bars
    keep = set(seen[-sessions:])
    return [b for b in bars if b.get("session_date") in keep]


# ---------- capture (writer) ----------


async def capture_snapshot(now: datetime | None = None) -> int:
    """Fold the current market snapshot into its 5-minute bucket.

    Returns the number of rows written. Reads the snapshot through the same
    cache layer the API uses, so this costs no extra DPS traffic.
    """
    moment = now or datetime.now(timezone.utc)
    bucket = bucket_start(moment)

    items = await get_cache().get_market_snapshot()
    samples = [
        (i.symbol, price, i)
        for i in items
        if i.symbol and (price := _num(getattr(i, "price", None))) and price > 0
    ]
    if not samples:
        return 0

    existing = await _rows_at_bucket(bucket)
    rows = [
        merge_sample(
            existing.get(symbol),
            symbol=symbol,
            price=price,
            ts=bucket,
            day_high=getattr(item, "day_high", None),
            day_low=getattr(item, "day_low", None),
            volume=getattr(item, "volume", None),
        )
        for symbol, price, item in samples
    ]
    await async_execute(
        lambda c: c.table("psx_intraday").upsert(rows, on_conflict="symbol,ts")
    )
    return len(rows)


async def _rows_at_bucket(bucket: datetime) -> dict[str, dict[str, Any]]:
    """Every stored row for one bucket, keyed by symbol.

    Paged: PostgREST caps a response at ~1000 rows and reports no error when it
    clips, and the snapshot covers ~500 symbols today with room to grow.
    """
    out: dict[str, dict[str, Any]] = {}
    offset = 0
    page_size = 1000
    while True:
        res = await async_execute(
            lambda c, o=offset: c.table("psx_intraday")
            .select("symbol,ts,open,high,low,close,cum_volume")
            .eq("ts", bucket.isoformat())
            .order("symbol")
            .range(o, o + page_size - 1)
        )
        page = res.data or []
        for row in page:
            out[row["symbol"]] = row
        if len(page) < page_size:
            return out
        offset += page_size


async def prune(retention_days: int = RETENTION_DAYS) -> None:
    """Drop bars older than `retention_days`. This table is a chart window."""
    cutoff = (datetime.now(PKT).date() - timedelta(days=retention_days)).isoformat()
    await async_execute(
        lambda c: c.table("psx_intraday").delete().lt("session_date", cutoff)
    )


# ---------- read ----------


async def intraday(symbol: str, sessions: int = 1) -> list[dict[str, Any]]:
    """5-minute bars for the newest `sessions` trading days, oldest first.

    Returns `[]` — never raises — when the table is missing or empty, so a
    deployment where the migration has not landed yet degrades to "no intraday
    data" and the chart falls back to daily bars.
    """
    sym = symbol.upper()
    count = max(1, min(sessions, MAX_SESSIONS))

    async def load() -> list[dict[str, Any]]:
        try:
            res = await async_execute(
                lambda c: c.table("psx_intraday")
                .select("ts,session_date,open,high,low,close,cum_volume")
                .eq("symbol", sym)
                .order("ts", desc=True)
                # 78 buckets per session; take headroom for a long session and
                # trim to whole sessions below.
                .limit(count * 120)
            )
        except Exception:
            log.warning("intraday_read_failed", symbol=sym, exc_info=True)
            return []
        return latest_sessions(to_bars(res.data or []), count)

    return await mem_cache.get_or_load(f"intraday:{sym}:{count}", TTL_INTRADAY, load)
