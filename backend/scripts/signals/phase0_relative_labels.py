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
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.signals_v2.constants import ROUND_TRIP_COST
from app.services.signals_v2.feature_store import load_verified_store
from app.services.signals_v2.ranking import excess_to_label
from app.services.signals_v2.training import HORIZON_DAYS, evaluate_walk_forward

MIN_OOS_DATES = 40
MIN_SAMPLES = 2000
PHASE0B_TOP_LIQUID = 300
PHASE0B_GRID_STRIDE = 5   # denser than TRAINING_GRID_STRIDE["20D"]=10: gate needs ~150+ OOS dates
PHASE0B_CONFIG = {"name": "baseline_lr05_d4", "learning_rate": 0.05, "max_depth": 4, "n_estimators": 300}


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


def _verdict_0a(a: dict) -> str:
    primary = a.get("20D") or {}
    if primary.get("status") in {"missing_feature_store", "unverified_store", "insufficient_samples"}:
        return "INCONCLUSIVE"
    excess = primary.get("avg_buy_excess_after_cost")
    folds_pos = primary.get("folds_positive", 0)
    folds_total = primary.get("folds_total", 0)
    if excess is None or folds_total < 2:
        return "INCONCLUSIVE"
    return "GREEN" if (excess > 0 and folds_pos > folds_total / 2) else "RED"


def _verdict_0b(b: dict) -> str:
    if "daily_rank_ic" not in b:
        return "INCONCLUSIVE"
    if int(b.get("n_dates") or 0) < MIN_OOS_DATES:
        return "INCONCLUSIVE"
    green = (float(b["daily_rank_ic"]) > 0
             and float(b["top_decile_excess_after_cost"]) > 0
             and float(b["folds_positive_frac"]) >= 0.5)
    return "GREEN" if green else "RED"


def _verdict(a: dict, b: dict) -> str:
    """0B is the shipped architecture (cross-sectional ranker) and is the primary
    gate; 0A (absolute relabeled classifier) is supporting evidence. GREEN on
    either unblocks Tier B — training itself re-validates on holdout + DSR/PBO."""
    va, vb = _verdict_0a(a), _verdict_0b(b)
    if "GREEN" in (va, vb):
        return "GREEN"
    if va == vb == "INCONCLUSIVE":
        return "INCONCLUSIVE"
    return "RED"


def _phase0b() -> dict:
    """Minimal aligned 20D cross-sectional ranker on the top liquid names (single fixed config)."""
    if os.getenv("PHASE0_SKIP_0B"):
        return {"status": "skipped"}
    try:
        import xgboost  # noqa: F401
    except ImportError:
        return {"status": "xgboost_unavailable"}
    try:
        from dotenv import load_dotenv

        from app.services.signals_v2.ranking import build_ranking_dataset, train_ranker
        from app.services.signals_v2.training import group_rows, map_rows
        from train_signals_v2 import _client, _select_all, _select_ohlcv_adjusted, _select_where

        load_dotenv(ROOT / ".env")
        client = _client()
        ohlcv = _select_ohlcv_adjusted(client, max_rows_per_symbol=1300, mode="price")
        profiles = map_rows(_select_all(client, "psx_profile", "*", order_by="symbol"))
        kse_rows = _select_where(client, "psx_index_eod", "date,close", order_by="date",
                                 filters=[("code", "eq", "KSE100")])
    except Exception as exc:
        return {"status": "no_data_access", "error": f"{exc.__class__.__name__}: {exc}"}

    histories = group_rows(ohlcv)
    # top ~N liquid names by median 20-bar turnover
    turnover = {}
    for sym, rows in histories.items():
        recent = sorted(rows, key=lambda r: str(r.get("date")))[-20:]
        if len(recent) < 20:
            continue
        turnover[sym] = float(np.median([float(r.get("close") or 0) * float(r.get("volume") or 0)
                                         for r in recent]))
    top = sorted(turnover, key=turnover.get, reverse=True)[:PHASE0B_TOP_LIQUID]
    histories = {s: histories[s] for s in top}

    audit_path = ROOT / "artifacts" / "signals" / "data_integrity_report.json"
    events = {}
    if audit_path.exists():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        # residual events = still-broken after price adjustment (the true
        # contamination set); the raw map over-excludes now-fixed bonus gaps
        events = (audit.get("residual_corp_action_events") or audit["corp_action_events"])["by_symbol"]

    ds = build_ranking_dataset(histories=histories, fundamentals={}, profiles=profiles,
                               kse_rows=kse_rows, horizon="20D", corp_action_events=events,
                               grid_stride=PHASE0B_GRID_STRIDE)
    if len(ds.y) < MIN_SAMPLES:
        return {"status": "insufficient_samples", "samples": int(len(ds.y))}
    result = train_ranker(ds, horizon="20D", configs=[PHASE0B_CONFIG], folds=4)
    m = result["metrics"]
    return {"daily_rank_ic": m["daily_rank_ic"],
            "top_decile_excess_after_cost": m["top_decile_excess_after_cost"],
            "precision_at_10": m["precision_at_10"],
            "folds_positive_frac": m["folds_positive_frac"],
            "n_dates": m["n_dates"], "samples": m["samples"],
            "universe": len(histories)}


def main() -> int:
    store_dir = Path(os.getenv("SIGNALS_V2_FEATURE_STORE_DIR",
                               str(ROOT / "artifacts" / "signals" / "feature_store_full")))
    a = _phase0a(store_dir)
    b = _phase0b()
    report = {"phase_0a": a, "phase_0b": b,
              "verdict_0a": _verdict_0a(a), "verdict_0b": _verdict_0b(b),
              "verdict": _verdict(a, b)}
    out = ROOT / "artifacts" / "signals" / "phase0_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "report": str(out)}, indent=2))
    return {"GREEN": 0, "RED": 2, "INCONCLUSIVE": 3}[report["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
