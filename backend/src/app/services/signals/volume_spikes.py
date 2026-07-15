"""Volume spike detector.

For every symbol present in ``psx_market_snapshot``, compare today's volume
to the 30-day trailing average from ``psx_ohlcv`` and emit a row when the
ratio exceeds a threshold AND the %change is non-trivial. Writes the result
to ``psx_unusual_activity`` for the /api/market/unusual endpoint.

Uses a single batch OHLCV query instead of per-symbol loops.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import structlog

from app.db.supabase import async_execute

log = structlog.get_logger()

VOLUME_RATIO_THRESHOLD = 3.0
PCT_CHANGE_THRESHOLD = 2.0
WINDOW_DAYS = 30


class VolumeSpikeDetector:
    """Detect symbols whose volume is ≫ 30d average."""

    async def detect(self) -> list[dict]:
        try:
            snapshot = await async_execute(
                lambda c: c.table("psx_market_snapshot").select(
                    "symbol,price,change_pct,volume,refreshed_at"
                )
            )
            rows = snapshot.data or []
            if not rows:
                return []
        except Exception:
            log.warning("volume_spike_snapshot_failed", exc_info=True)
            return []

        now_iso = datetime.now(timezone.utc).isoformat()

        # Get last 31 days of volume for all symbols with volume > 0
        thirty_one_days_ago = (date.today() - timedelta(days=31)).isoformat()
        today_iso = date.today().isoformat()

        try:
            ohlcv_res = await async_execute(
                lambda c: c.table("psx_ohlcv")
                .select("symbol,volume,date")
                .gte("date", thirty_one_days_ago)
                .lt("date", today_iso)
                .gte("volume", 1)
            )
        except Exception:
            log.warning("volume_spike_ohlcv_failed", exc_info=True)
            return []

        ohlcv_rows = ohlcv_res.data or []

        # Group by symbol, compute avg of last 30 days
        vol_by_sym: dict[str, list[float]] = defaultdict(list)
        for r in ohlcv_rows:
            sym = r.get("symbol")
            vol = r.get("volume")
            if sym and vol:
                vol_by_sym[sym.upper()].append(float(vol))

        avg_by_sym: dict[str, float] = {}
        for sym, vols in vol_by_sym.items():
            if len(vols) >= 5:  # need at least 5 days for a meaningful average
                avg_by_sym[sym] = sum(vols[-30:]) / min(len(vols), 30)

        triggered: list[dict] = []
        for row in rows:
            sym = row.get("symbol")
            if not sym:
                continue
            vol_today = row.get("volume") or 0
            price = row.get("price")
            change_pct = row.get("change_pct") or 0
            if abs(change_pct) < PCT_CHANGE_THRESHOLD or vol_today <= 0:
                continue

            avg = avg_by_sym.get(sym.upper())
            if avg is None or avg <= 0:
                continue

            ratio = vol_today / avg
            if ratio < VOLUME_RATIO_THRESHOLD:
                continue

            reason = (
                f"Vol {ratio:.1f}x the {WINDOW_DAYS}-day avg of {avg:,.0f}; "
                f"change {change_pct:+.2f}%"
            )
            triggered.append({
                "symbol": sym,
                "ts": now_iso,
                "price": price,
                "change_pct": change_pct,
                "volume": int(vol_today),
                "volume_ratio": round(ratio, 2),
                "reason": reason,
            })

        if triggered:
            try:
                # Fix 11: Cleanup old unusual activity rows (keep last 7 days)
                seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
                await async_execute(
                    lambda c: c.table("psx_unusual_activity").delete().lt("ts", seven_days_ago)
                )
            except Exception:
                log.debug("volume_spike_cleanup_failed", exc_info=True)

            try:
                await async_execute(
                    lambda c: c.table("psx_unusual_activity").upsert(
                        triggered, on_conflict="symbol,ts"
                    )
                )
            except Exception:
                log.warning("volume_spike_upsert_failed", exc_info=True)

        return triggered