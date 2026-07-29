"""TradingView technical-rating consensus for PSX stocks.

Batch-fetches TradingView's Recommend.All / Recommend.MA / Recommend.Other
columns (their Strong Buy..Strong Sell gauge) through the existing scanner
client. This is DISPLAY context ("market consensus"), clearly labeled
source=tradingview — it is never fed into fusion and never presented as our AI.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import structlog

from app.scrapers.tradingview import get_scanner

log = structlog.get_logger()

# TradingView interval suffix per NafaIQ horizon (base columns are 1D).
TV_INTERVAL = {"5D": "", "20D": "|1W", "60D": "|1M"}

_CACHE_TTL_SECONDS = 900
_cache: dict[str, tuple[float, dict[str, dict]]] = {}

_BULL = {"BUY", "STRONG_BUY"}
_BEAR = {"SELL", "STRONG_SELL"}


def tv_value_to_label(value: float | None) -> str | None:
    """TradingView's official thresholds on the [-1, 1] rating value."""
    if value is None:
        return None
    v = float(value)
    if v >= 0.5:
        return "STRONG_BUY"
    if v >= 0.1:
        return "BUY"
    if v > -0.1:
        return "HOLD"
    if v > -0.5:
        return "SELL"
    return "STRONG_SELL"


def consensus_agreement(our_label: str, tv_label: str | None) -> str | None:
    if tv_label is None:
        return None

    def _bucket(label: str) -> str:
        if label in _BULL:
            return "bull"
        if label in _BEAR:
            return "bear"
        return "neutral"

    ours, theirs = _bucket(our_label), _bucket(tv_label)
    if ours == theirs:
        return "AGREES"
    if "neutral" in (ours, theirs):
        return "MIXED"
    return "DISAGREES"


async def fetch_consensus(horizon: str = "20D") -> dict[str, dict]:
    """Symbol -> consensus block for every PSX stock, TTL-cached per horizon."""
    key = horizon.upper()
    hit = _cache.get(key)
    now = time.monotonic()
    if hit is not None and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]

    suffix = TV_INTERVAL.get(key, "")
    columns = [f"Recommend.All{suffix}", f"Recommend.MA{suffix}", f"Recommend.Other{suffix}"]
    try:
        rows = await get_scanner().scan(columns=columns, limit=600)
    except Exception:
        log.warning("tv_consensus_fetch_failed", exc_info=True)
        return hit[1] if hit is not None else {}

    as_of = datetime.now(timezone.utc).isoformat()
    out: dict[str, dict] = {}
    for row in rows:
        d = row.get("d") or []
        if len(d) < 3 or d[0] is None:
            continue
        symbol = str(row.get("s", "")).replace("PSX:", "").upper()
        if not symbol:
            continue
        out[symbol] = {
            "rating": round(float(d[0]), 4),
            "ma_rating": round(float(d[1]), 4) if d[1] is not None else None,
            "oscillator_rating": round(float(d[2]), 4) if d[2] is not None else None,
            "label": tv_value_to_label(d[0]),
            "source": "tradingview",
            "as_of": as_of,
        }
    if out:
        _cache[key] = (now, out)
    return out
