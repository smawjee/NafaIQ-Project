"""Precompute cross-sectional factor ranks for the liquid universe.

Heavy (one OHLCV read per symbol), so it runs as a daily job and writes ranks to
psx_signal_cross_section; the signal API then reads a single precomputed row.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Any

from app.db.supabase import async_execute, select_all
from app.repositories import signals_repo
from app.services.signals.features import build_feature_frame, compute_feature_snapshot
from app.services.signals.cross_section import factor_inputs, rank_universe

CONCURRENCY = 6


async def precompute_cross_section(limit: int | None = None) -> dict[str, Any]:
    # Universe = every listed symbol; the >=200-bar filter below selects the
    # investable set at rank time (a transient snapshot drops names like ENGRO
    # that simply didn't trade that minute).
    profiles = await select_all("psx_profile", "symbol", order_by="symbol")
    symbols = [str(r["symbol"]).upper() for r in profiles if r.get("symbol")]
    if limit:
        symbols = symbols[:limit]
    inputs = await signals_repo.context_inputs(symbols[0]) if symbols else {}
    kse_rows = inputs.get("kse_rows") or []

    sem = asyncio.Semaphore(CONCURRENCY)
    universe: list[tuple[str, dict[str, Any]]] = []

    async def one(sym: str) -> None:
        async with sem:
            try:
                bars = await signals_repo.adjusted_bars(sym)
                if len(bars) < 200:
                    return
                frame = build_feature_frame(symbol=sym, ohlcv_rows=bars, kse_rows=kse_rows)
                features = compute_feature_snapshot(frame)
                universe.append((sym, factor_inputs(features)))
            except Exception:
                return

    await asyncio.gather(*(one(s) for s in symbols))
    if len(universe) < 3:
        return {"universe": len(universe), "written": 0}

    ranked = rank_universe(universe)
    as_of = date.today().isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = [
        {
            "symbol": sym,
            "as_of": as_of,
            "composite_percentile": data.get("composite_percentile"),
            "universe_size": data.get("universe_size", len(universe)),
            "factors": {name: f["percentile"] for name, f in data.get("factors", {}).items()},
            "computed_at": now_iso,
        }
        for sym, data in ranked.items()
    ]
    written = 0
    for start in range(0, len(payload), 200):
        chunk = payload[start:start + 200]
        await async_execute(lambda c, _c=chunk: c.table("psx_signal_cross_section").upsert(_c, on_conflict="symbol"))
        written += len(chunk)
    return {"universe": len(universe), "written": written}
