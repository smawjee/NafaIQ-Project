#!/usr/bin/env python
"""Calibrate trend-state continuation statistics on real PSX history.

Walks the verified 20D feature store, classifies every historical sample's
trend state from its stored feature vector, pairs it with the sample's realized
forward 20D return, and writes per-state continuation stats to
src/app/ml/signals_v2/trend_stats.json. These are the ONLY numbers the risk
engine is allowed to show users.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from app.services.signals_v2.feature_store import load_verified_store
from app.services.signals_v2.trend_state import classify_trend

ML_DIR = ROOT / "src" / "app" / "ml" / "signals_v2"


def measure_continuation(states_by_sample: list[tuple[str, float]]) -> dict:
    by_state: dict[str, list[float]] = defaultdict(list)
    for state, fwd in states_by_sample:
        by_state[state].append(float(fwd))
    out: dict[str, dict] = {}
    for state, rets in by_state.items():
        arr = np.asarray(rets)
        out[state] = {
            "n": int(len(arr)),
            "p_negative_20d": round(float(np.mean(arr < 0)), 4),
            "median_20d_return": round(float(np.median(arr)), 4),
        }
    return out


def main() -> int:
    store_dir = Path(os.getenv("SIGNALS_V2_FEATURE_STORE_DIR",
                               str(ROOT / "artifacts" / "signals" / "feature_store_full")))
    path = store_dir / "signals_v2_20d.npz"
    if not path.exists():
        print(json.dumps({"status": "missing_store", "path": str(path)}))
        return 2
    ds, _ = load_verified_store(str(path))
    names = ds.feature_names
    pairs: list[tuple[str, float]] = []
    for i in range(len(ds.y)):
        features = {name: (None if np.isnan(v) else float(v))
                    for name, v in zip(names, ds.X[i])}
        state = classify_trend(features).state
        pairs.append((state, float(ds.forward_returns[i])))
    stats = measure_continuation(pairs)
    ML_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "source_samples": int(len(pairs)), "states": stats}
    (ML_DIR / "trend_stats.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"samples": len(pairs),
                      "states": {s: v["n"] for s, v in stats.items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
