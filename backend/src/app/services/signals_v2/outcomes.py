"""Signal track-record service: immutable daily snapshots + maturity evaluation.

Every trading day the CURRENT technical signals (exactly what users saw) are
snapshotted into the append-only psx_signals_v3_daily table via an atomic
scoring run. Once a signal's horizon elapses, its realized/benchmark/excess
returns are computed with the SAME execution convention as training (entry =
first valid close after as_of, exit = horizon sessions later) and inserted
into psx_signal_outcomes. The aggregation gives an honest, user-showable
track record — measured, never claimed.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

import structlog

from app.db.supabase import async_execute
from app.repositories import signals_v3_repo
from app.services.signals_v2.constants import (
    MAX_ENTRY_DELAY_TRADING_DAYS,
    ROUND_TRIP_COST,
)
from app.services.signals_v2.training import HORIZON_DAYS, _parse_date

log = structlog.get_logger()

EVALUATION_VERSION = "v3.1-outcome-1"
LARGE_LOSS_NET = -0.02
SNAPSHOT_MODEL_VERSION = "technical-v2.0"
SNAPSHOT_FEATURE_VERSION = "v3.1"


def mature_outcome(bars: list[dict], kse_by_date: dict[str, float], *,
                   as_of: date, horizon_days: int, max_entry_delay: int) -> dict | None:
    """Realized outcome for one signal, or None if the horizon has not elapsed."""
    ordered = sorted(bars, key=lambda r: str(r.get("date")))
    dates = [_parse_date(r.get("date")) for r in ordered]
    closes = [float(r.get("close") or 0) for r in ordered]

    entry_i = None
    seen_after = 0
    for i, d in enumerate(dates):
        if d <= as_of:
            continue
        seen_after += 1
        if closes[i] > 0:
            entry_i = i
            break
        if seen_after > max_entry_delay:
            break
    if entry_i is None:
        return None
    exit_i = entry_i + horizon_days
    if exit_i >= len(ordered) or closes[exit_i] <= 0:
        return None

    entry_d, exit_d = dates[entry_i], dates[exit_i]
    realized = closes[exit_i] / closes[entry_i] - 1
    k0 = kse_by_date.get(entry_d.isoformat())
    k1 = kse_by_date.get(exit_d.isoformat())
    benchmark = (k1 / k0 - 1) if k0 and k1 and k0 > 0 else 0.0
    net = realized - ROUND_TRIP_COST
    return {
        "maturity_status": "MATURED",
        "realized_return": round(float(realized), 6),
        "benchmark_return": round(float(benchmark), 6),
        "excess_return": round(float(realized - benchmark), 6),
        "large_loss": bool(net < LARGE_LOSS_NET),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_version": EVALUATION_VERSION,
    }


def v2_row_to_snapshot(row: dict[str, Any], *, as_of: str,
                       sector_map: dict[str, str]) -> dict[str, Any] | None:
    """Map a persisted psx_signals_v2 row to an immutable daily snapshot row."""
    signal = str(row.get("signal") or "")
    if not signal or signal == "NO_SIGNAL":
        return None
    symbol = str(row.get("symbol") or "").upper()
    if not symbol:
        return None
    return {
        "symbol": symbol,
        "as_of": as_of,
        "horizon": str(row.get("horizon") or "20D"),
        "signal": signal,
        "sector": sector_map.get(symbol),
        "rank_score": row.get("technical_score"),
        "data_quality_status": row.get("freshness"),
        "explanation_factors": {
            "confidence": row.get("confidence"),
            "trend_state": row.get("trend_state"),
            "consensus_agreement": row.get("consensus_agreement"),
        },
    }


def aggregate_track_record(joined: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate matured outcomes (joined with their signals) into a scoreboard."""
    by_signal: dict[str, list[dict]] = defaultdict(list)
    for r in joined:
        by_signal[str(r.get("signal") or "UNKNOWN")].append(r)

    out: dict[str, Any] = {"matured_total": len(joined), "by_signal": {}}
    for sig, rows in by_signal.items():
        n = len(rows)
        positives = sum(1 for r in rows if float(r.get("realized_return") or 0) > 0)
        entry: dict[str, Any] = {
            "n": n,
            "hit_rate": round(positives / n, 4),
            "avg_return": round(sum(float(r.get("realized_return") or 0) for r in rows) / n, 4),
            "avg_excess": round(sum(float(r.get("excess_return") or 0) for r in rows) / n, 4),
            "large_loss_rate": round(sum(1 for r in rows if r.get("large_loss")) / n, 4),
        }
        if sig in ("SELL", "STRONG_SELL"):
            # a SELL "wins" when the stock then fell
            entry["avoided_loss_rate"] = round(
                sum(1 for r in rows if float(r.get("realized_return") or 0) < 0) / n, 4)
        out["by_signal"][sig] = entry
    return out


async def snapshot_current_signals() -> dict[str, Any]:
    """Snapshot current psx_signals_v2 rows into an atomic append-only run (idempotent per day)."""
    kse = await async_execute(lambda c: c.table("psx_index_eod").select("date")
                              .eq("code", "KSE100").order("date", desc=True).limit(1))
    latest = (kse.data or [None])[0]
    if not latest:
        return {"status": "no_benchmark_date"}
    as_of = str(latest["date"])[:10]

    if await signals_v3_repo.complete_run_exists(as_of=as_of, model_version=SNAPSHOT_MODEL_VERSION):
        return {"status": "already_snapshotted", "as_of": as_of}

    signals = await async_execute(lambda c: c.table("psx_signals_v2").select("*"))
    profiles = await async_execute(lambda c: c.table("psx_profile").select("symbol,sector"))
    sector_map = {str(p.get("symbol") or "").upper(): p.get("sector")
                  for p in (profiles.data or [])}

    rows = []
    for r in signals.data or []:
        snap = v2_row_to_snapshot(r, as_of=as_of, sector_map=sector_map)
        if snap is not None:
            rows.append(snap)
    if not rows:
        return {"status": "no_signals", "as_of": as_of}

    run_id = await signals_v3_repo.start_scoring_run(
        as_of=as_of, model_version=SNAPSHOT_MODEL_VERSION,
        feature_version=SNAPSHOT_FEATURE_VERSION, expected=len(rows))
    written = await signals_v3_repo.insert_signals(
        run_id, rows, model_version=SNAPSHOT_MODEL_VERSION,
        feature_version=SNAPSHOT_FEATURE_VERSION)
    status = await signals_v3_repo.complete_scoring_run(run_id, written=written, expected=len(rows))
    return {"status": status, "as_of": as_of, "rows": len(rows), "written": written}


async def evaluate_pending_outcomes(*, limit: int = 1000) -> dict[str, Any]:
    """Insert outcome rows for every snapshot whose horizon has elapsed."""
    pending = await signals_v3_repo.signals_missing_outcomes(limit=limit)
    if not pending:
        return {"outcomes_inserted": 0, "still_pending": 0}

    kse = await async_execute(lambda c: c.table("psx_index_eod").select("date,close")
                              .eq("code", "KSE100").order("date"))
    kse_by_date = {str(r["date"])[:10]: float(r.get("close") or 0) for r in (kse.data or [])}

    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for row in pending:
        by_symbol[str(row["symbol"]).upper()].append(row)

    inserted, immature = 0, 0
    for sym, signal_rows in by_symbol.items():
        bars_res = await async_execute(lambda c, s=sym: c.table("psx_ohlcv")
                                       .select("date,close").eq("symbol", s)
                                       .order("date", desc=True).limit(400))
        bars = list(reversed(bars_res.data or []))
        for row in signal_rows:
            horizon_days = HORIZON_DAYS.get(str(row["horizon"]), 20)
            out = mature_outcome(bars, kse_by_date, as_of=_parse_date(row["as_of"]),
                                 horizon_days=horizon_days,
                                 max_entry_delay=MAX_ENTRY_DELAY_TRADING_DAYS)
            if out is None:
                immature += 1
                continue
            await signals_v3_repo.insert_outcome(row["id"], **out)
            inserted += 1
    return {"outcomes_inserted": inserted, "still_pending": immature}
