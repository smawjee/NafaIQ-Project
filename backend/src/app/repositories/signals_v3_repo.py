"""Insert-only persistence for Signals V3.1. Signal rows are never updated or deleted."""
from __future__ import annotations

from typing import Any

from app.db.supabase import async_execute


async def start_scoring_run(*, as_of: str, model_version: str, feature_version: str, expected: int) -> str:
    res = await async_execute(lambda c: c.table("psx_signal_scoring_runs").insert({
        "as_of": as_of, "model_version": model_version, "feature_version": feature_version,
        "expected_symbol_count": expected, "status": "STARTED"}))
    return str((res.data or [{}])[0].get("scoring_run_id"))


async def insert_signals(run_id: str, rows: list[dict[str, Any]], *, model_version: str, feature_version: str) -> int:
    if not rows:
        return 0
    payload = [{**r, "scoring_run_id": run_id, "model_version": model_version,
                "feature_version": feature_version} for r in rows]
    res = await async_execute(lambda c: c.table("psx_signals_v3_daily").insert(payload))
    return len(res.data or [])


async def complete_scoring_run(run_id: str, *, written: int, expected: int) -> str:
    status = "COMPLETE" if written == expected and expected > 0 else "FAILED"
    await async_execute(lambda c: c.table("psx_signal_scoring_runs").update(
        {"status": status, "written_symbol_count": written, "completed_at": "now()"})
        .eq("scoring_run_id", run_id))
    return status


async def latest_complete_run(horizon: str | None = None) -> dict[str, Any] | None:
    runs = await async_execute(lambda c: c.table("psx_signal_scoring_runs")
                               .select("*").eq("status", "COMPLETE")
                               .order("as_of", desc=True).order("started_at", desc=True).limit(1))
    return (runs.data or [None])[0]


async def latest_complete_signals(symbol: str, horizon: str) -> dict[str, Any] | None:
    run = await latest_complete_run(horizon)
    if not run:
        return None
    res = await async_execute(lambda c: c.table("psx_signals_v3_daily").select("*")
                              .eq("symbol", symbol.upper()).eq("horizon", horizon)
                              .eq("scoring_run_id", run["scoring_run_id"]).limit(1))
    return (res.data or [None])[0]


async def insert_outcome(signal_id: int, **fields: Any) -> None:
    await async_execute(lambda c: c.table("psx_signal_outcomes").insert({"signal_id": signal_id, **fields}))


async def signals_missing_outcomes(*, limit: int = 500) -> list[dict[str, Any]]:
    """Signal rows without any outcome row yet (maturity evaluation candidates)."""
    signals = await async_execute(lambda c: c.table("psx_signals_v3_daily")
                                  .select("id,symbol,as_of,horizon,signal")
                                  .order("as_of", desc=False).limit(limit))
    rows = signals.data or []
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    outcomes = await async_execute(lambda c: c.table("psx_signal_outcomes")
                                   .select("signal_id").in_("signal_id", ids))
    have = {o["signal_id"] for o in (outcomes.data or [])}
    return [r for r in rows if r["id"] not in have]
