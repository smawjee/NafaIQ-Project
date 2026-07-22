#!/usr/bin/env python
"""Phase 0 — does the PIT-safe feature set carry beta-free (relative) alpha?

0A: relabel a manifested V3 store with market-relative classes, re-run walk-forward.
0B: minimal aligned 20D cross-sectional ranker on the top liquid names.

GREEN (exit 0): valid OOS AND positive 20D after-cost top-selection excess AND majority folds positive AND min support.
RED   (exit 2): valid OOS but the signal is absent.
INCONCLUSIVE (exit 3): missing store/benchmark/support — NEVER conflate with RED.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from app.services.signals_v2.constants import ROUND_TRIP_COST
from app.services.signals_v2.feature_store import load_verified_store
from app.services.signals_v2.ranking import excess_to_label
from app.services.signals_v2.training import HORIZON_DAYS, evaluate_walk_forward

MIN_OOS_DATES = 40
MIN_SAMPLES = 2000


def _model_factory():
    try:
        import lightgbm
        return lambda: lightgbm.LGBMClassifier(
            n_estimators=400, learning_rate=0.04, num_leaves=31, subsample=0.85,
            colsample_bytree=0.85, reg_lambda=0.8, objective="multiclass", random_state=42, verbose=-1)
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingClassifier
        return lambda: HistGradientBoostingClassifier(max_iter=260, learning_rate=0.045, random_state=42)


def _phase0a(store_dir: Path) -> dict:
    out: dict = {}
    for horizon in HORIZON_DAYS:
        path = store_dir / f"signals_v2_{horizon.lower()}.npz"
        if not path.exists():
            out[horizon] = {"status": "missing_feature_store"}
            continue
        try:
            ds, _ = load_verified_store(str(path))
        except ValueError as exc:
            out[horizon] = {"status": "unverified_store", "error": str(exc)}
            continue
        if len(ds.y) < MIN_SAMPLES:
            out[horizon] = {"status": "insufficient_samples", "samples": int(len(ds.y))}
            continue
        excess = ds.forward_returns - ds.benchmark_forward_returns
        y_rel = np.asarray([excess_to_label(float(e), horizon).value for e in excess], dtype=object)
        metrics, _, _, _ = evaluate_walk_forward(
            X=ds.X, y=y_rel, dates=ds.dates, forward_returns=ds.forward_returns,
            benchmark_forward_returns=ds.benchmark_forward_returns,
            technical_labels=ds.technical_labels, model_factory=_model_factory())
        folds = metrics.get("folds", [])
        pos = sum(1 for f in folds if float(f.get("avg_buy_excess_return") or 0) > 0)
        metrics["avg_buy_excess_after_cost"] = round(float(metrics.get("avg_buy_excess_return") or 0) - ROUND_TRIP_COST, 4)
        metrics["folds_positive"] = pos
        metrics["folds_total"] = len(folds)
        metrics.pop("folds", None)
        out[horizon] = metrics
    return out


def _verdict(a: dict) -> str:
    primary = a.get("20D") or {}
    if primary.get("status") in {"missing_feature_store", "unverified_store", "insufficient_samples"}:
        return "INCONCLUSIVE"
    excess = primary.get("avg_buy_excess_after_cost")
    folds_pos = primary.get("folds_positive", 0)
    folds_total = primary.get("folds_total", 0)
    if excess is None or folds_total < 2:
        return "INCONCLUSIVE"
    return "GREEN" if (excess > 0 and folds_pos > folds_total / 2) else "RED"


def main() -> int:
    store_dir = Path(os.getenv("SIGNALS_V2_FEATURE_STORE_DIR",
                               str(ROOT / "artifacts" / "signals" / "feature_store_full")))
    a = _phase0a(store_dir)
    report = {"phase_0a": a, "phase_0b": {"status": "run_after_T8"}, "verdict": _verdict(a)}
    out = ROOT / "artifacts" / "signals" / "phase0_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "report": str(out)}, indent=2))
    return {"GREEN": 0, "RED": 2, "INCONCLUSIVE": 3}[report["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
