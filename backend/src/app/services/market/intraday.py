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

import asyncio
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

# Buckets the tape writer restates each run: the one in progress, plus one back
# so a print that lands after the boundary still reaches its own bar.
RECENT_BUCKETS = 2


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
    move `close`. A bucket's range spans only the prices actually sampled
    inside it.

    `day_high`/`day_low` are accepted (the snapshot carries them) but never
    enter the bar. They are session-wide and carry no timestamp, so there is no
    minute they can honestly be attributed to. The previous rule folded them
    into any bucket that already existed, reasoning that such a bucket had
    "printed through" them — but the writer samples every 60s into a 5-minute
    bucket, so samples 2-5 always found an existing row and every bucket
    inherited the full session range. Since max/min never narrow, it stuck: on
    2026-08-07 MEBL had 3 distinct (high, low) pairs across all 58 bars of the
    session, and 28,276 of 29,518 bars market-wide had open == close. Every
    candle rendered as an identical full-height hairline with no body.

    The honest cost of dropping them: at 60s sampling a 5-minute bar sees ~5
    prices, so wicks understate the true intra-bucket range. An understated
    wick is a sampling limit; a day-wide one is a fabrication.

    `cum_volume` never decreases *within* a bucket: the snapshot is
    day-cumulative, and a momentarily stale read must not make a later bucket
    look emptier than an earlier one (the reader diffs consecutive buckets and
    would emit a negative). Across buckets the writer cannot enforce this — it
    only ever loads the current bucket — so `to_bars` holds the high-water mark
    on the read side.
    """
    prev_high = _num((existing or {}).get("high"))
    prev_low = _num((existing or {}).get("low"))
    prev_vol = _num((existing or {}).get("cum_volume")) or 0.0

    highs = [price, prev_high]
    lows = [price, prev_low]

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


def bars_from_trades(
    trades: Iterable[dict[str, Any]],
    *,
    symbol: str,
    session: date,
    minutes: int = BUCKET_MINUTES,
) -> list[dict[str, Any]]:
    """Build true OHLCV buckets from a trade tape, shaped for `psx_intraday`.

    Snapshot sampling can only ever approximate a bar: it sees ~5 prices per
    5-minute bucket, so the high and low are whichever of those happened to be
    sampled, and per-bar volume has to be reverse-engineered from a
    day-cumulative counter. A tape carries every print, so open/high/low/close
    are exact and volume is a plain sum.

    `cum_volume` is written as a running session total rather than the bar's own
    volume, because `to_bars` diffs consecutive buckets on the read side.
    Writing per-bar volume here would make the reader diff it a second time.

    Trade times are PKT wall-clock ("HH:MM:SS") with no date, which is why the
    session must be supplied. Rows that cannot be parsed, and non-positive
    prices, are skipped rather than allowed to open a bucket at zero.
    """
    by_bucket: dict[datetime, dict[str, Any]] = {}
    for trade in trades:
        moment = _trade_moment(trade.get("time"), session)
        if moment is None:
            continue
        price = _num(trade.get("price"))
        if price is None or price <= 0:
            continue
        size = _num(trade.get("volume")) or 0.0
        bucket = bucket_start(moment, minutes)
        bar = by_bucket.get(bucket)
        if bar is None:
            by_bucket[bucket] = {
                "open": price, "high": price, "low": price,
                "close": price, "volume": max(size, 0.0),
            }
            continue
        # The tape is ordered, so the last print in a bucket is its close.
        bar["high"] = max(bar["high"], price)
        bar["low"] = min(bar["low"], price)
        bar["close"] = price
        bar["volume"] += max(size, 0.0)

    out: list[dict[str, Any]] = []
    running = 0.0
    for bucket in sorted(by_bucket):
        bar = by_bucket[bucket]
        running += bar["volume"]
        out.append(
            {
                "symbol": symbol.upper(),
                "ts": bucket.isoformat(),
                "session_date": session.isoformat(),
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "cum_volume": int(running),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return out


def _trade_moment(value: Any, session: date) -> datetime | None:
    """A tape's "HH:MM:SS" PKT clock time as an aware UTC instant."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if not value:
        return None
    parts = str(value).strip().split(":")
    if len(parts) < 2:
        return None
    try:
        hour, minute = int(parts[0]), int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
    except (TypeError, ValueError):
        return None
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
        return None
    return datetime(
        session.year, session.month, session.day, hour, minute, second, tzinfo=PKT
    ).astimezone(timezone.utc)


def to_bars(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Shape stored rows into chart-ready bars, oldest first.

    Turns day-cumulative `cum_volume` into per-bar volume by diffing
    consecutive buckets *within a session*. The first bar of each session keeps
    its cumulative value — it is the volume traded since the open, which is
    exactly that bar's volume.

    The baseline is a high-water mark, not the previous bucket's raw value. A
    cumulative that goes backwards means the snapshot's volume column regressed
    (a stale or corrupted read), not that shares were untraded, so adopting the
    lower figure would re-baseline every later diff against it. That is what
    zeroed a whole session on 2026-08-07: MEBL's stored cumulative read
    4,052,268 and then 587 for every remaining bucket, so each subsequent bar
    diffed 587-587 and the chart showed V 0 from the second bar onward. Holding
    the peak keeps the next genuine increase measurable and still clamps at
    zero, so no bar can ever report negative volume.
    """
    ordered = sorted(
        (r for r in rows if r.get("ts") is not None),
        key=lambda r: str(r["ts"]),
    )
    out: list[dict[str, Any]] = []
    peak_cum_by_session: dict[str, float] = {}
    for row in ordered:
        session = str(row.get("session_date") or "")
        cum = _num(row.get("cum_volume")) or 0.0
        peak = peak_cum_by_session.get(session)
        volume = cum if peak is None else max(0.0, cum - peak)
        peak_cum_by_session[session] = cum if peak is None else max(peak, cum)
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


async def capture_from_trades(
    fetch_trades: Any,
    symbols: Iterable[str],
    *,
    now: datetime | None = None,
    concurrency: int = 6,
    recent_buckets: int = RECENT_BUCKETS,
) -> int:
    """Write the newest buckets for `symbols` from their trade tapes.

    Preferred over `capture_snapshot`: a tape carries every print, so O/H/L/C
    are exact and volume is a sum rather than a diff of a day-cumulative
    counter that the writer cannot verify. It also only emits a bucket for a
    five-minute window that actually traded, where the sampler wrote one every
    five minutes regardless and left invented flat bars on illiquid symbols.

    Only the last `recent_buckets` windows are written. `bars_from_trades`
    rebuilds the whole session on every call, and re-upserting ~70 buckets for
    ~500 symbols every minute would be ~35,000 rows a minute to restate history
    that cannot change. The tail is the only part still moving — the current
    bucket, plus one back so a late print is not lost. Earlier buckets keep the
    running `cum_volume` written when they were current, which is what
    `to_bars` diffs against.

    `fetch_trades` is injected rather than imported so this stays unit-testable
    and the scheduler can share its existing pooled client. A symbol whose
    fetch raises is skipped: one dead symbol must not cost the other 500.
    """
    moment = now or datetime.now(timezone.utc)
    session = session_date_for(moment)
    cutoff = bucket_start(moment) - timedelta(minutes=BUCKET_MINUTES * (recent_buckets - 1))

    sem = asyncio.Semaphore(concurrency)
    rows: list[dict[str, Any]] = []

    async def one(symbol: str) -> None:
        async with sem:
            try:
                trades = await fetch_trades(symbol)
            except Exception:  # noqa: BLE001 - a dead symbol must not stop the run
                log.debug("intraday_tape_failed", symbol=symbol, exc_info=True)
                return
        for bar in bars_from_trades(trades or [], symbol=symbol, session=session):
            if datetime.fromisoformat(bar["ts"]) >= cutoff:
                rows.append(bar)

    await asyncio.gather(*(one(s) for s in symbols))
    if not rows:
        return 0
    await async_execute(
        lambda c: c.table("psx_intraday").upsert(rows, on_conflict="symbol,ts")
    )
    return len(rows)


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
