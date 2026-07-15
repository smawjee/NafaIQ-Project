"""Stock treemap data: sectors → stocks, sized by ``size_metric``, colored by
% change. Mirrors the Google-Finance-style treemap rendered on the PSX page.

Sizing vs. market cap — these are deliberately NOT the same field:

* ``market_cap``  — the real figure (price x listed_shares), or **None** when
  ``psx_profile.listed_shares`` is unknown. Display only. Never invented.
* ``size_metric`` — always present; drives tile area. Equals ``market_cap``
  when that is known, else a ``price * sqrt(volume)`` proxy.
* ``sizing_basis`` — "market_cap" | "volume_proxy", so the UI can tell which.

``listed_shares`` is populated only by the weekly job_refresh_fundamentals and
is NULL for most symbols, so the proxy is the common path. Emitting the proxy
in a field named ``market_cap`` would show users an invented market cap in a
finance app — hence the split.
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
                # Real market cap when DPS fundamentals has populated listed_shares
                # (weekly — job_refresh_fundamentals).
                market_cap = price * listed_shares
                size_metric = market_cap
                sizing_basis = "market_cap"
            elif volume > 0:
                # Fallback SIZING proxy only: price * sqrt(volume). Gives a
                # sane relative tile ordering when shares-outstanding is
                # unknown, but it is NOT a market cap and must never be
                # presented as one — market_cap stays None so the UI can
                # render "—" instead of an invented figure.
                market_cap = None
                size_metric = price * (volume ** 0.5) * 100.0
                sizing_basis = "volume_proxy"
            else:
                # No listed_shares AND no volume — nothing to size by.
                continue

            stock_entry = {
                "symbol": sym,
                "name": profile.get("name") or sym,
                "price": price,
                "change_pct": change_pct,
                "volume": volume,
                "market_cap": market_cap,
                "size_metric": size_metric,
                "sizing_basis": sizing_basis,
                "logoid": profile.get("logoid"),
            }

            bucket = sectors.setdefault(
                sector_name,
                {
                    "name": sector_name,
                    "stocks": [],
                    "total_change_pct_weighted": 0.0,
                    "total_size_metric": 0.0,
                    "total_market_cap": 0.0,
                    "real_cap_count": 0,
                },
            )
            bucket["stocks"].append(stock_entry)
            # Weight by size_metric (always present); total_market_cap only
            # accumulates real caps so it is never a mix of real and proxy.
            bucket["total_change_pct_weighted"] += change_pct * size_metric
            bucket["total_size_metric"] += size_metric
            if market_cap is not None:
                bucket["total_market_cap"] += market_cap
                bucket["real_cap_count"] += 1
            stock_count += 1

        sector_payload: list[dict[str, Any]] = []
        for bucket in sectors.values():
            stocks_sorted = sorted(
                bucket["stocks"], key=lambda s: s["size_metric"], reverse=True
            )[:_STOCKS_PER_SECTOR_CAP]
            total_size = bucket["total_size_metric"]
            avg_change_pct = (
                bucket["total_change_pct_weighted"] / total_size
                if total_size > 0
                else 0.0
            )
            # Only report a sector market cap when every stock in it had a real
            # one; a partial sum would understate the sector without saying so.
            complete_cap = bucket["real_cap_count"] == len(bucket["stocks"])
            sector_payload.append(
                {
                    "name": bucket["name"],
                    "avg_change_pct": round(avg_change_pct, 4),
                    "total_market_cap": (
                        bucket["total_market_cap"] if complete_cap else None
                    ),
                    "total_size_metric": total_size,
                    "stock_count": len(stocks_sorted),
                    "stocks": stocks_sorted,
                }
            )

        sector_payload.sort(key=lambda s: s["total_size_metric"], reverse=True)

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
