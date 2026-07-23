#!/usr/bin/env python
"""Layer 3a — does 12-1 month momentum (ret_240d_ex20) carry after-cost alpha on PSX?

The literature finds PSX momentum at 3-12 MONTH formation. Phase 0 killed
5-60 day price prediction; this experiment tests the long-formation variant the
V3.1 grid never isolated, using the existing verified stores and cost model.
Report only — no serving change regardless of verdict.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from app.services.signals_v2.constants import ROUND_TRIP_COST
from app.services.signals_v2.feature_store import load_verified_store

MIN_DATES = 30


def momentum_quintile_report(feature_dates, symbols, momentum, forward_returns,
                             benchmark_returns, *, min_names: int = 30) -> dict:
    momentum = np.asarray(momentum, dtype=np.float64)
    fwd = np.asarray(forward_returns, dtype=np.float64)
    bench = np.asarray(benchmark_returns, dtype=np.float64)
    excess = fwd - bench

    by_date: dict = defaultdict(list)
    for i, d in enumerate(feature_dates):
        if np.isfinite(momentum[i]):
            by_date[d].append(i)

    per_q: dict[int, list[float]] = defaultdict(list)
    n_dates = 0
    for idxs in by_date.values():
        if len(idxs) < min_names:
            continue
        n_dates += 1
        arr = np.asarray(idxs)
        ranks = rankdata(momentum[arr], method="average") - 1
        quintile = np.clip((ranks * 5) // len(arr), 0, 4).astype(int)
        for q in range(5):
            sel = arr[quintile == q]
            if len(sel):
                per_q[q].append(float(np.mean(excess[sel])))

    if n_dates == 0:
        return {"q5_minus_q1_after_cost": 0.0, "q5_excess_after_cost": 0.0,
                "n_dates": 0, "monotonicity": 0.0, "by_quintile": {}}

    means = {q: float(np.mean(v)) for q, v in per_q.items()}
    q5 = means.get(4, 0.0) - ROUND_TRIP_COST
    q1 = means.get(0, 0.0)
    mono = spearmanr(list(means.keys()), list(means.values())).statistic if len(means) >= 3 else 0.0
    return {
        "q5_minus_q1_after_cost": round(q5 - q1, 4),
        "q5_excess_after_cost": round(q5, 4),
        "n_dates": n_dates,
        "monotonicity": round(float(mono) if np.isfinite(mono) else 0.0, 4),
        "by_quintile": {f"q{q + 1}": round(m, 4) for q, m in sorted(means.items())},
    }


def main() -> int:
    store_dir = Path(os.getenv("SIGNALS_V2_FEATURE_STORE_DIR",
                               str(ROOT / "artifacts" / "signals" / "feature_store_full")))
    results: dict = {}
    for horizon in ("20D", "60D"):
        path = store_dir / f"signals_v2_{horizon.lower()}.npz"
        if not path.exists():
            results[horizon] = {"status": "missing_store"}
            continue
        ds, _ = load_verified_store(str(path))
        col = ds.feature_names.index("ret_240d_ex20")
        report = momentum_quintile_report(ds.dates, ds.symbols, ds.X[:, col],
                                          ds.forward_returns, ds.benchmark_forward_returns)
        if report["n_dates"] < MIN_DATES:
            report["status"] = "insufficient_dates"
        results[horizon] = report

    primary = results.get("60D") or {}
    if primary.get("status") in ("missing_store", "insufficient_dates"):
        verdict = "INCONCLUSIVE"
    elif primary.get("q5_excess_after_cost", 0) > 0 and primary.get("monotonicity", 0) > 0.5:
        verdict = "GREEN"
    else:
        verdict = "RED"

    out = ROOT / "artifacts" / "signals" / "momentum_experiment.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"results": results, "verdict": verdict,
                               "signal": "ret_240d_ex20 (12-1 momentum)"},
                              indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict,
                      "60D_q5_after_cost": primary.get("q5_excess_after_cost"),
                      "report": str(out)}, indent=2))
    return {"GREEN": 0, "RED": 2, "INCONCLUSIVE": 3}[verdict]


if __name__ == "__main__":
    raise SystemExit(main())
