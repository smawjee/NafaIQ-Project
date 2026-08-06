"""Retrospective base rates for the technical rating.

Answers an honest, backward-looking question: across PSX history, after a stock
showed a given technical rating, how did it actually move over the next N
sessions? This is a *measured base rate with dispersion and sample size* — never
a forecast. Wide dispersion / near-zero medians are reported faithfully (prior
research already showed price-only signals carry no stable directional edge).

The heavy walk (recompute the setup at each historical point) runs offline in a
script and writes a small JSON artifact that ships with the code; serving just
reads it. Pure aggregation lives here and is unit-tested.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import numpy as np

HORIZON = 20
_ARTIFACT = Path(__file__).resolve().parents[2] / "ml" / "signals" / "rating_stats.json"

RATING_BUCKETS = ("Strong Bullish", "Bullish", "Neutral", "Bearish", "Strong Bearish")


def summarize_returns(returns: list[float]) -> dict[str, Any]:
    """n, share-up, and the median/decile move for one rating bucket."""
    arr = np.asarray([r for r in returns if r is not None and np.isfinite(r)], dtype=np.float64)
    n = int(arr.size)
    if n == 0:
        return {"n": 0}
    return {
        "n": n,
        "p_up": round(float((arr > 0).mean()), 4),
        "median_return": round(float(np.median(arr)), 5),
        "mean_return": round(float(arr.mean()), 5),
        "p10": round(float(np.quantile(arr, 0.10)), 5),
        "p90": round(float(np.quantile(arr, 0.90)), 5),
    }


def aggregate(samples: list[tuple[str, float]]) -> dict[str, Any]:
    """samples = [(rating_bucket, forward_return)] → per-bucket base-rate stats."""
    by_bucket: dict[str, list[float]] = {b: [] for b in RATING_BUCKETS}
    for bucket, ret in samples:
        if bucket in by_bucket:
            by_bucket[bucket].append(ret)
    return {
        "horizon": HORIZON,
        "total_samples": len(samples),
        "buckets": {b: summarize_returns(rs) for b, rs in by_bucket.items()},
    }


def load_rating_stats() -> Optional[dict[str, Any]]:
    try:
        return json.loads(_ARTIFACT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def base_rate_for(rating: str | None, stats: dict[str, Any] | None) -> Optional[dict[str, Any]]:
    """The measured base rate for a given rating, if we have enough samples."""
    if not rating or not stats:
        return None
    bucket = (stats.get("buckets") or {}).get(rating)
    if not bucket or bucket.get("n", 0) < 100:
        return None
    return {"rating": rating, "horizon": stats.get("horizon", HORIZON), **bucket}


def write_artifact(stats: dict[str, Any]) -> Path:
    _ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    _ARTIFACT.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return _ARTIFACT
