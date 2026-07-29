"""Market-wide foreign-investor flow context (FIPI) for signal responses.

Aggregates the daily FIPI client types (FOREIGN CORPORATES, FOREIGN INDIVIDUAL,
OVERSEAS PAKISTANI) from psx_fipi_daily into rolling 5- and 20-session net
flows. Display context only — flow *features* enter the ML lab through their
own Phase-0 gate once enough history has accumulated.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

import structlog

from app.db.supabase import async_execute

log = structlog.get_logger()

FOREIGN_CLIENT_TYPES = ("FOREIGN CORPORATES", "FOREIGN INDIVIDUAL", "OVERSEAS PAKISTANI")

_CACHE_TTL_SECONDS = 900
_cache: dict[str, tuple[float, dict | None]] = {}


async def _foreign_rows(days: int = 40) -> list[dict[str, Any]]:
    res = await async_execute(
        lambda c: c.table("psx_fipi_daily")
        .select("trade_date,client_type,net_value_pkr,net_value_usd")
        .eq("scope", "CLIENT_TYPE").in_("client_type", list(FOREIGN_CLIENT_TYPES))
        .order("trade_date", desc=True).limit(days * len(FOREIGN_CLIENT_TYPES))
    )
    return res.data or []


def classify_flow_trend(net_5d_pkr: float, net_20d_pkr: float) -> str:
    if net_5d_pkr > 0 and net_20d_pkr > 0:
        return "FOREIGN_BUYING"
    if net_5d_pkr < 0 and net_20d_pkr < 0:
        return "FOREIGN_SELLING"
    if net_5d_pkr == 0 and net_20d_pkr == 0:
        return "NEUTRAL"
    return "MIXED"


async def get_flow_context() -> dict[str, Any] | None:
    """Rolling foreign-flow summary, TTL-cached; None when data/DB unavailable."""
    hit = _cache.get("ctx")
    now = time.monotonic()
    if hit is not None and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]
    try:
        rows = await _foreign_rows()
    except Exception:
        log.warning("flow_context_query_failed", exc_info=True)
        return hit[1] if hit is not None else None
    if not rows:
        return None

    per_day_pkr: dict[str, float] = defaultdict(float)
    per_day_usd: dict[str, float] = defaultdict(float)
    for r in rows:
        d = str(r["trade_date"])[:10]
        per_day_pkr[d] += float(r.get("net_value_pkr") or 0)
        per_day_usd[d] += float(r.get("net_value_usd") or 0)
    days = sorted(per_day_pkr, reverse=True)
    net_5d = sum(per_day_pkr[d] for d in days[:5])
    net_20d = sum(per_day_pkr[d] for d in days[:20])
    ctx = {
        "foreign_net_5d_pkr": round(net_5d, 2),
        "foreign_net_20d_pkr": round(net_20d, 2),
        "foreign_net_5d_usd": round(sum(per_day_usd[d] for d in days[:5]), 2),
        "trend": classify_flow_trend(net_5d, net_20d),
        "last_date": days[0],
        "days_covered": len(days),
        "source": "nccpl-via-finhisaab",
    }
    _cache["ctx"] = (now, ctx)
    return ctx
