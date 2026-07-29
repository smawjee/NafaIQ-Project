#!/usr/bin/env python
"""Horizon scan for the 0B cross-sectional ranker (report-only).

Phase0's pre-registered gate tests 20D. On v3.2 adjusted data the 0A
relative-label experiment turned after-cost positive at 5D (4/4 folds) while
20D stayed negative — short-horizon signal decaying by 20D. This scan runs the
IDENTICAL 0B protocol at 5D/20D/60D so the next decision (which horizon to
train) is made on evidence, not default. Writes its own artifact; never
touches phase0_report.json.
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

MIN_SAMPLES = 2000
TOP_LIQUID = 300
GRID_STRIDE = 5
CONFIG = {"name": "baseline_lr05_d4", "learning_rate": 0.05, "max_depth": 4, "n_estimators": 300}


def main() -> int:
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

    histories = group_rows(ohlcv)
    turnover = {}
    for sym, rows in histories.items():
        recent = sorted(rows, key=lambda r: str(r.get("date")))[-20:]
        if len(recent) < 20:
            continue
        turnover[sym] = float(np.median([float(r.get("close") or 0) * float(r.get("volume") or 0)
                                         for r in recent]))
    top = sorted(turnover, key=turnover.get, reverse=True)[:TOP_LIQUID]
    histories = {s: histories[s] for s in top}

    audit_path = ROOT / "artifacts" / "signals" / "data_integrity_report.json"
    events = {}
    if audit_path.exists():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        events = (audit.get("residual_corp_action_events") or audit["corp_action_events"])["by_symbol"]

    results: dict = {}
    for horizon in ("5D", "20D", "60D"):
        ds = build_ranking_dataset(histories=histories, fundamentals={}, profiles=profiles,
                                   kse_rows=kse_rows, horizon=horizon, corp_action_events=events,
                                   grid_stride=GRID_STRIDE)
        if len(ds.y) < MIN_SAMPLES:
            results[horizon] = {"status": "insufficient_samples", "samples": int(len(ds.y))}
            continue
        r = train_ranker(ds, horizon=horizon, configs=[CONFIG], folds=4)
        m = r["metrics"]
        results[horizon] = {k: m[k] for k in
                            ("daily_rank_ic", "ndcg_at_5", "ndcg_at_10", "precision_at_5",
                             "precision_at_10", "top_decile_excess_after_cost",
                             "folds_positive_frac", "n_dates", "samples")}

    out = ROOT / "artifacts" / "signals" / "ranker_horizon_scan.json"
    out.write_text(json.dumps({"results": results, "universe": len(histories),
                               "protocol": "phase0b-identical, grid_stride=5"}, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({"results": results, "report": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
