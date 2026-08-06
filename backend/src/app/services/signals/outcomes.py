"""Live track record — record what was said, then measure what happened.

The calibration artifact proves the probabilities hold on a 2025-2026 holdout
the cells never saw. That is a *retrospective* proof. This module closes the
remaining loop: every recommendation the engine actually serves is recorded,
and once its horizon elapses the realised outcome is measured and folded into a
permanent reliability record.

Why both are needed. A retrospective holdout can only ever show that the
relationship held on data already in hand. A live record answers the harder
question — does it still hold *now*, on predictions made before the outcome
existed? Only the second one can catch the relationship decaying.

Design constraints that shaped this:

* **Storage is bounded.** Raw predictions are pruned to a 90-day window after
  maturation; the permanent artefact is a per-day, per-bucket rollup of roughly
  ten rows a day. Keeping raw rows forever would add ~18 MB/year to a database
  that has no headroom to spare.
* **Outcomes are measured, never edited.** A matured row is written once. There
  is deliberately no path here that revises an outcome after the fact — that is
  the mechanism by which a "track record" becomes marketing.
* **The bucket is fixed at prediction time.** Rounding `p` when the prediction
  is made, rather than at maturation, means a later change to the bucketing
  cannot retroactively reshape history.

Pure functions only: no DB, no clock, no I/O. The scheduler job supplies rows
and persists results.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

#: Reliability-diagram granularity. 0.05 keeps buckets populated: the engine's
#: probabilities cluster tightly around the ~0.47 base rate, so finer buckets
#: would split a real signal into noise.
BUCKET_WIDTH = 0.05

#: Raw predictions older than this (post-maturation) are deleted; the rollup
#: carries the permanent record.
RETENTION_DAYS = 90

#: A bucket needs at least this many matured predictions before it is worth
#: reporting a hit rate for.
MIN_BUCKET_N = 30


def probability_bucket(p: Optional[float], width: float = BUCKET_WIDTH) -> Optional[float]:
    """Round a probability to its reliability-diagram bucket.

    Computed at prediction time and stored, so re-bucketing later cannot
    retroactively rewrite the historical record.
    """
    if p is None:
        return None
    try:
        value = float(p)
    except (TypeError, ValueError):
        return None
    if not (0.0 <= value <= 1.0):
        return None
    return round(round(value / width) * width, 4)


@dataclass(frozen=True)
class MaturedOutcome:
    """One prediction whose horizon has elapsed."""
    symbol: str
    as_of: Any
    horizon_sessions: int
    prob_bucket: Optional[float]
    realized_return: float
    #: The measured event: did the stock rise over the horizon?
    outcome: bool


def mature_prediction(
    row: dict[str, Any],
    *,
    close_now: Optional[float],
) -> Optional[MaturedOutcome]:
    """Measure a prediction against the price actually reached.

    Returns None when the outcome cannot be measured honestly — a missing or
    non-positive price on either end. An unmeasurable prediction is left pending
    rather than recorded as a miss, because counting "we could not price it" as
    a failure would understate calibration for reasons unrelated to the model.
    """
    start = _num(row.get("close_at_prediction"))
    end = _num(close_now)
    if start is None or end is None or start <= 0 or end <= 0:
        return None

    realized = end / start - 1.0
    return MaturedOutcome(
        symbol=str(row.get("symbol") or "").upper(),
        as_of=row.get("as_of"),
        horizon_sessions=int(row.get("horizon_sessions") or 20),
        prob_bucket=_num(row.get("prob_bucket")),
        realized_return=round(realized, 6),
        outcome=realized > 0,
    )


def rollup(outcomes: Iterable[MaturedOutcome]) -> list[dict[str, Any]]:
    """Aggregate matured outcomes into (horizon, bucket) -> n, hits.

    Rows without a probability bucket are dropped: they carry no calibration
    information and would silently dilute the denominator.
    """
    buckets: dict[tuple[int, float], list[int]] = {}
    for outcome in outcomes:
        if outcome.prob_bucket is None:
            continue
        key = (outcome.horizon_sessions, float(outcome.prob_bucket))
        counts = buckets.setdefault(key, [0, 0])
        counts[0] += 1
        if outcome.outcome:
            counts[1] += 1

    return [
        {"horizon_sessions": horizon, "prob_bucket": bucket, "n": n, "hits": hits}
        for (horizon, bucket), (n, hits) in sorted(buckets.items())
    ]


def merge_rollup(existing: dict[str, Any] | None, addition: dict[str, Any]) -> dict[str, Any]:
    """Combine a new rollup row with whatever is already stored for that key.

    Maturation may run more than once for a given day (a retry, a backfill), so
    counts accumulate rather than overwrite.
    """
    if not existing:
        return dict(addition)
    return {
        **addition,
        "n": int(existing.get("n", 0)) + int(addition.get("n", 0)),
        "hits": int(existing.get("hits", 0)) + int(addition.get("hits", 0)),
    }


def reliability_from_rollup(rows: Iterable[dict[str, Any]],
                            *, min_n: int = MIN_BUCKET_N) -> dict[str, Any]:
    """Build a reliability diagram from stored rollup rows.

    Returns the per-bucket predicted-vs-actual table plus the observation-
    weighted expected calibration error — the same shape the historical holdout
    reports, so the UI can render both with one component.
    """
    merged: dict[float, list[int]] = {}
    for row in rows:
        bucket = _num(row.get("prob_bucket"))
        if bucket is None:
            continue
        counts = merged.setdefault(float(bucket), [0, 0])
        counts[0] += int(row.get("n") or 0)
        counts[1] += int(row.get("hits") or 0)

    table: list[dict[str, Any]] = []
    total = 0
    weighted_error = 0.0
    for bucket in sorted(merged):
        n, hits = merged[bucket]
        if n < min_n:
            continue
        actual = hits / n
        table.append({
            "bucket": f"{bucket:.2f}",
            "n": n,
            "predicted": round(bucket, 4),
            "actual": round(actual, 4),
            "gap": round(actual - bucket, 4),
        })
        total += n
        weighted_error += n * abs(actual - bucket)

    return {
        "reliability": table,
        "n": total,
        "ece": round(weighted_error / total, 4) if total else None,
    }


def _num(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None
