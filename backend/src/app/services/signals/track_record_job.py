"""Daily jobs that build the live track record.

Two halves, deliberately separate so a failure in one cannot corrupt the other:

* ``record_todays_recommendations`` — snapshot what the engine is telling users
  right now. Must run *after* the cross-section precompute, since the reversal
  percentile it depends on comes from there.
* ``mature_recommendations`` — measure predictions whose horizon has elapsed,
  fold them into the permanent per-bucket rollup, and prune the raw rows past
  the retention window.

The recording half writes what was said *before* the outcome exists, which is
the whole point: a retrospective holdout can only show a relationship held on
data already in hand, while this can catch it decaying in real time.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

from app.db.supabase import select_all
from app.repositories import signals_repo
from app.services.signals import service
from app.services.signals.outcomes import (
    RETENTION_DAYS,
    mature_prediction,
    merge_rollup,
    probability_bucket,
    rollup,
)

#: Scoring the full universe is many DB round-trips per symbol; the same bound
#: the cross-section job uses.
CONCURRENCY = 6

#: A prediction is dated from the confirmed bar it was computed on. For a
#: delisted or long-suspended symbol that bar can be years old, and recording it
#: would write a "prediction" whose outcome *already exists* — maturation would
#: resolve it instantly from history. That is precisely the look-ahead the live
#: record exists to rule out, so stale symbols are skipped entirely.
#:
#: 7 calendar days spans a normal week plus a public holiday. Roughly 529 of 861
#: symbols are fresh within 7 days; the rest are not trading.
MAX_BAR_AGE_DAYS = 7


async def record_todays_recommendations(limit: int | None = None) -> dict[str, Any]:
    """Snapshot today's calibrated call for every ranked symbol."""
    profiles = await select_all("psx_profile", "symbol", order_by="symbol")
    symbols = [str(r["symbol"]).upper() for r in profiles if r.get("symbol")]
    if limit:
        symbols = symbols[:limit]

    as_of = date.today().isoformat()
    sem = asyncio.Semaphore(CONCURRENCY)
    rows: list[dict[str, Any]] = []

    async def one(symbol: str) -> None:
        async with sem:
            try:
                payload = await service.get_signal(symbol)
            except Exception:
                return
            rec = payload.get("recommendation")
            if not rec:
                return
            setup = payload.get("technical_setup") or {}
            bar_date = setup.get("bar_date")
            if not is_fresh(bar_date):
                return
            # Price the prediction from the same confirmed bar the setup used,
            # so the realised return is measured from what the user actually saw.
            close = _last_close(payload)
            rows.append({
                "symbol": symbol,
                "as_of": bar_date or as_of,
                "horizon_sessions": int(rec.get("horizon_sessions") or 20),
                "rating": rec.get("rating"),
                "p": rec.get("p"),
                "p_lower": rec.get("p_lower"),
                "p_upper": rec.get("p_upper"),
                "prob_bucket": probability_bucket(rec.get("p")),
                "close_at_prediction": close,
                "basis": rec.get("basis"),
                "sample_size": int(rec.get("sample_size") or 0),
            })

    await asyncio.gather(*(one(s) for s in symbols))
    # A prediction without a price cannot ever be measured, so do not store it.
    rows = [r for r in rows if r["close_at_prediction"]]
    written = await signals_repo.record_recommendations(rows)
    return {"symbols": len(symbols), "recorded": written}


def is_fresh(bar_date: Any, *, today: date | None = None,
             max_age_days: int = MAX_BAR_AGE_DAYS) -> bool:
    """Is this confirmed bar recent enough to date a live prediction from?

    A stale bar means the symbol is not trading. Recording against it would
    back-date a prediction into a period whose outcome is already known.
    """
    if not bar_date:
        return False
    try:
        parsed = bar_date if isinstance(bar_date, date) else date.fromisoformat(
            str(bar_date)[:10]
        )
    except (TypeError, ValueError):
        return False
    reference = today or date.today()
    # A bar dated in the future is a data error, not freshness.
    if parsed > reference:
        return False
    return (reference - parsed).days <= max_age_days


def _last_close(payload: dict[str, Any]) -> float | None:
    quality = payload.get("data_quality") or {}
    value = quality.get("last_close")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


async def mature_recommendations() -> dict[str, Any]:
    """Measure elapsed predictions and fold them into the permanent rollup."""
    candidates = await signals_repo.matured_candidates()
    if not candidates:
        return {"matured": 0, "buckets": 0, "pruned": False}

    matured = []
    updates: list[dict[str, Any]] = []
    for row in candidates:
        outcome = mature_prediction(row, close_now=row.get("close_now"))
        if outcome is None:
            # Unpriceable on one end; leave pending rather than score it a miss.
            continue
        matured.append(outcome)
        updates.append({
            "symbol": outcome.symbol,
            "as_of": str(row.get("as_of")),
            "horizon_sessions": outcome.horizon_sessions,
            "matured_on": str(row.get("matured_on")),
            "realized_return": outcome.realized_return,
            "outcome": outcome.outcome,
        })

    await signals_repo.mark_matured(updates)

    # Group by the day each prediction matured, so the rollup is a time series.
    by_day: dict[str, list] = {}
    for outcome, update in zip(matured, updates):
        by_day.setdefault(update["matured_on"], []).append(outcome)

    existing = {
        (str(r["matured_on"]), int(r["horizon_sessions"]), float(r["prob_bucket"])): r
        for r in await signals_repo.calibration_rows()
    }

    rollup_rows: list[dict[str, Any]] = []
    for matured_on, day_outcomes in by_day.items():
        for entry in rollup(day_outcomes):
            key = (matured_on, entry["horizon_sessions"], float(entry["prob_bucket"]))
            rollup_rows.append(
                merge_rollup(existing.get(key), {"matured_on": matured_on, **entry})
            )

    await signals_repo.upsert_calibration(rollup_rows)

    cutoff = (date.today() - timedelta(days=RETENTION_DAYS)).isoformat()
    await signals_repo.prune_matured_before(cutoff)

    return {"matured": len(matured), "buckets": len(rollup_rows), "pruned": True}
