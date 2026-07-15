"""Stock treemap data: sectors → stocks, sized by market cap, colored by
% change. Mirrors the Google-Finance-style treemap rendered on the PSX page.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

import time

from app.db.supabase import async_execute

log = structlog.get_logger()

_last_treemap_cache: dict | None = None
_last_treemap_time: float = 0
_TREEMAP_CACHE_TTL = 15  # seconds

_STOCKS_PER_SECTOR_CAP = 20


def _empty() -> dict[str, Any]:
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "sectors": [],
        "stock_count": 0,
    }


def _to_float(v: Any) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _to_int(v: Any) -> int:
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return 0


async def get_treemap() -> dict[str, Any]:
    """Return a Google-Finance-style treemap payload.

    Sectors are sized by `Σ market_cap` of their constituent stocks, so the
    largest sector visually dominates the canvas the same way it does on
    Google Finance. Each stock tile carries enough fields to render a
    tooltip (name, price, ±%, volume, mkt cap) without a follow-up request.
    """
    global _last_treemap_cache, _last_treemap_time
    now = time.time()
    if _last_treemap_cache is not None and now - _last_treemap_time < _TREEMAP_CACHE_TTL:
        return _last_treemap_cache
    try:
        snap_res = await async_execute(
            lambda c: c.table("psx_market_snapshot").select("symbol,price,change_pct,volume")
        )
        snapshot_rows = snap_res.data or []

        prof_res = await async_execute(
            lambda c: c.table("psx_profile").select(
                "symbol,sector,name,listed_shares,logoid"
            )
        )
        profile_rows = prof_res.data or []
        profile_by_symbol = {p["symbol"]: p for p in profile_rows if p.get("symbol")}

        sectors: dict[str, dict[str, Any]] = {}
        stock_count = 0

        for row in snapshot_rows:
            sym = (row.get("symbol") or "").upper()
            if not sym:
                continue
            price = _to_float(row.get("price"))
            if price <= 0:
                continue
            change_pct = _to_float(row.get("change_pct"))
            volume = _to_int(row.get("volume"))

            profile = profile_by_symbol.get(sym) or {}
            sector_name = (profile.get("sector") or "Other").strip() or "Other"
            listed_shares = _to_float(profile.get("listed_shares"))
            if listed_shares > 0:
                market_cap = price * listed_shares
            else:
                continue  # skip stocks with no listed_shares data

            stock_entry = {
                "symbol": sym,
                "name": profile.get("name") or sym,
                "price": price,
                "change_pct": change_pct,
                "volume": volume,
                "market_cap": market_cap,
                "logoid": profile.get("logoid"),
            }

            bucket = sectors.setdefault(
                sector_name,
                {
                    "name": sector_name,
                    "stocks": [],
                    "total_change_pct_weighted": 0.0,
                    "total_market_cap": 0.0,
                },
            )
            bucket["stocks"].append(stock_entry)
            bucket["total_change_pct_weighted"] += change_pct * market_cap
            bucket["total_market_cap"] += market_cap
            stock_count += 1

        sector_payload: list[dict[str, Any]] = []
        for bucket in sectors.values():
            stocks_sorted = sorted(
                bucket["stocks"], key=lambda s: s["market_cap"], reverse=True
            )[:_STOCKS_PER_SECTOR_CAP]
            total_mc = bucket["total_market_cap"]
            avg_change_pct = (
                bucket["total_change_pct_weighted"] / total_mc if total_mc > 0 else 0.0
            )
            sector_payload.append(
                {
                    "name": bucket["name"],
                    "avg_change_pct": round(avg_change_pct, 4),
                    "total_market_cap": total_mc,
                    "stock_count": len(stocks_sorted),
                    "stocks": stocks_sorted,
                }
            )

        sector_payload.sort(key=lambda s: s["total_market_cap"], reverse=True)

        result = {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "sectors": sector_payload,
            "stock_count": stock_count,
        }
        _last_treemap_cache = result
        _last_treemap_time = now
        return result
    except Exception:
        log.warning("treemap_load_failed", exc_info=True)
        return _empty()
