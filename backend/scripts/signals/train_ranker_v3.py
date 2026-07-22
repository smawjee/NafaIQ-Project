#!/usr/bin/env python
"""T15c — train Model A + Model B, calibrate, simulate, evaluate holdout once.

Temporal protocol (three_layer_split):
  dev         -> model selection + fit (per-fold purged OOS inside dev)
  calibration -> scored by the final dev-fitted models; DualCalibrator fitted here;
                 shadow policy/portfolio/DSR metrics computed on this clean forward window
  holdout     -> untouched until --evaluate-holdout, which scores it EXACTLY ONCE
                 (guarded by holdout_manifest.json) and overwrites the gate metrics

Every config trial is appended to the experiment registry; DSR's n_trials is the
registry count within the frozen selection family, never a hardcoded number.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import joblib
import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from train_signals_v2 import _client, _select_all, _select_ohlcv, _select_where  # sibling

from app.services.signals_v2.constants import PORTFOLIO_REBALANCE_DAYS
from app.services.signals_v2.feature_store import FEATURE_VERSION, dataset_hash
from app.services.signals_v2.labels import SignalLabel
from app.services.signals_v2.portfolio_sim import simulate_topk
from app.services.signals_v2.ranking import (
    DEFAULT_RANKER_CONFIGS,
    DualCalibrator,
    MIN_CAL_SUPPORT,
    build_ranking_dataset,
    calibration_report,
    join_oos,
    policy_metrics,
    rank_to_signal,
    score_layer,
    three_layer_split,
    train_absolute_model,
    train_ranker,
)
from app.services.signals_v2.training import HORIZON_DAYS, group_rows, map_rows
from app.services.signals_v2.validation import (
    deflated_sharpe_ratio,
    probability_of_backtest_overfitting,
)

REGISTRY = ROOT / "artifacts" / "signals" / "experiment_registry.jsonl"
HOLDOUT_MANIFEST = ROOT / "artifacts" / "signals" / "holdout_manifest.json"
ML_DIR = ROOT / "src" / "app" / "ml" / "signals_v2"
MIN_DATASET_SAMPLES = 3000


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        return "unknown"


def _register(entry: dict) -> None:
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def _family_trial_count(family_id: str) -> int:
    if not REGISTRY.exists():
        return 1
    seen = set()
    for line in REGISTRY.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("selection_family_id") == family_id:
            seen.add((e.get("config_name"), e.get("seed"), e.get("target_version")))
    return max(1, len(seen))


def _load_holdout_manifest() -> dict:
    if HOLDOUT_MANIFEST.exists():
        return json.loads(HOLDOUT_MANIFEST.read_text(encoding="utf-8"))
    return {}


def _write_holdout_manifest(manifest: dict) -> None:
    HOLDOUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    HOLDOUT_MANIFEST.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")


def _layer_metrics(records, calibrator, histories, kse_rows, horizon, *, n_trials) -> dict:
    """Policy + portfolio + DSR metrics for one scored time-layer."""
    calibrated = [calibrator.apply(c) for c in records]
    pol = policy_metrics(calibrated)
    picks: dict = {}
    for c in calibrated:
        lab = rank_to_signal(percentile=c.raw.percentile, p_beat_market=c.p_beat_market,
                             expected_excess_net=c.expected_excess_net,
                             p_positive_absolute=c.p_positive_absolute,
                             expected_absolute_net=c.expected_absolute_net,
                             data_quality_ok=True, liquidity_ok=True, risk_ok=True,
                             calibration_support_ok=c.calibration_support >= MIN_CAL_SUPPORT)
        if lab in (SignalLabel.BUY, SignalLabel.STRONG_BUY):
            picks.setdefault(c.raw.entry_date, []).append(c.raw.symbol)
    sim = _simulate_from_picks(picks, histories, kse_rows, horizon,
                               start=min((c.raw.entry_date for c in calibrated), default=None),
                               end=max((c.raw.exit_date for c in calibrated), default=None))
    dsr = deflated_sharpe_ratio(sim["nav_returns"], n_trials=n_trials) \
        if len(sim["nav_returns"]) > 10 else 0.0
    return {**pol,
            "max_drawdown": sim["max_drawdown"], "turnover": sim["turnover"],
            "sim_net_return": sim["net_return"], "sim_excess_return": sim["excess_return"],
            "sharpe": sim["sharpe"], "dsr": round(float(dsr), 4)}


def _simulate_from_picks(picks, histories, kse_rows, horizon, *, start=None, end=None):
    from datetime import date as _date
    prices: dict = {}
    for sym, rows in histories.items():
        series = {}
        for r in sorted(rows, key=lambda x: str(x.get("date"))):
            series[_date.fromisoformat(str(r.get("date"))[:10])] = float(r.get("close") or 0)
        prices[sym.upper()] = series
    kse = {_date.fromisoformat(str(r.get("date"))[:10]): float(r.get("close") or 0) for r in kse_rows}
    if start is not None and end is not None:
        kse = {d: v for d, v in kse.items() if start <= d <= end}
    picks_upper = {d: [s.upper() for s in syms] for d, syms in picks.items()}
    return simulate_topk(picks_upper, prices, kse, k=10, rebalance_days=PORTFOLIO_REBALANCE_DAYS[horizon])


def _technical_precision_at_5(combined) -> float:
    buys = [c for c in combined if c.technical_label in ("BUY", "STRONG_BUY")]
    if not buys:
        return 0.0
    top = sorted(buys, key=lambda c: c.percentile, reverse=True)[:5]
    return round(float(np.mean([c.excess_return > 0 for c in top])), 4)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train Signals V3.1 ranker + absolute models")
    parser.add_argument("--evaluate-holdout", action="store_true",
                        help="score the untouched holdout layer ONCE (manifest-guarded)")
    parser.add_argument("--horizons", nargs="*", default=list(HORIZON_DAYS),
                        help="horizons to train (default: all)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    audit = ROOT / "artifacts" / "signals" / "data_integrity_report.json"
    audit_data = json.loads(audit.read_text(encoding="utf-8")) if audit.exists() else {}
    events = (audit_data.get("corp_action_events") or {}).get("by_symbol", {})
    audit_passed = audit_data.get("status") == "pass"

    client = _client()
    ohlcv = _select_ohlcv(client, max_rows_per_symbol=1300)
    profiles = map_rows(_select_all(client, "psx_profile", "*", order_by="symbol"))
    kse_rows = _select_where(client, "psx_index_eod", "date,close", order_by="date",
                             filters=[("code", "eq", "KSE100")])
    histories = group_rows(ohlcv)
    ML_DIR.mkdir(parents=True, exist_ok=True)

    all_metrics: dict = {}
    for horizon in args.horizons:
        ds = build_ranking_dataset(histories=histories, fundamentals={}, profiles=profiles,
                                   kse_rows=kse_rows, horizon=horizon, corp_action_events=events)
        if len(ds.y) < MIN_DATASET_SAMPLES:
            all_metrics[horizon] = {"status": "skipped", "samples": int(len(ds.y))}
            continue
        layers = three_layer_split(ds.feature_dates)
        if layers.get("status") == "INCONCLUSIVE":
            all_metrics[horizon] = {"status": "inconclusive", "reason": layers["reason"]}
            continue

        ds_hash = dataset_hash(ds.X, ds.feature_names)
        family_id = f"{horizon}|{FEATURE_VERSION}|dh:{ds_hash}"
        ranker = train_ranker(ds, horizon=horizon, split_indices=layers["dev"])
        absolute = train_absolute_model(ds, horizon=horizon, split_indices=layers["dev"])
        combined_dev = join_oos(ranker["oos"], absolute["oos"])
        for cfg in DEFAULT_RANKER_CONFIGS:
            _register({"selection_family_id": family_id, "config_name": cfg["name"], "seed": 42,
                       "target_version": "excess_decile_v1", "execution_policy_version": "T+1_close_v1",
                       "universe_version": "eligible_v1", "git_commit": _git_commit(),
                       "dataset_hash": ds_hash, "horizon": horizon})
        n_trials = _family_trial_count(family_id)

        # calibration layer: scored by final dev models -> calibrator fitted here
        cal_records = score_layer(ranker["model"], absolute["clf"], absolute["reg"],
                                  ds, layers["calibration"], horizon)
        calibrator = DualCalibrator.fit(cal_records)
        cal_report = calibration_report(cal_records, calibrator)

        shadow = _layer_metrics(cal_records, calibrator, histories, kse_rows, horizon,
                                n_trials=n_trials)
        matrix = np.asarray(ranker["trial_matrix"]["matrix"], dtype=np.float64)
        pbo = probability_of_backtest_overfitting(matrix) \
            if matrix.ndim == 2 and matrix.shape[1] >= 2 else 1.0

        joblib.dump({"model": ranker["model"], "config": ranker["config"], "calibrator": calibrator,
                     "feature_names": ds.feature_names, "horizon": horizon,
                     "feature_version": FEATURE_VERSION}, ML_DIR / f"ranker_{horizon.lower()}.joblib")
        joblib.dump({"clf": absolute["clf"], "reg": absolute["reg"], "horizon": horizon,
                     "feature_names": ds.feature_names}, ML_DIR / f"absolute_{horizon.lower()}.joblib")

        metrics = {
            "data_audit_passed": audit_passed,
            **ranker["metrics"], **shadow,
            "technical_precision_at_5": _technical_precision_at_5(combined_dev),
            "calibration_ece": cal_report["beat_market"]["ece"],
            "calibration_brier": cal_report["beat_market"]["brier"],
            "pbo": round(float(pbo), 4),
            "n_trials": n_trials,
            "evaluated_on": "calibration_window",
            "layer_sizes": {"dev": int(len(layers["dev"])),
                            "calibration": int(len(layers["calibration"])),
                            "holdout": int(len(layers["holdout"]))},
        }

        manifest = _load_holdout_manifest()
        entry = manifest.get(horizon) or {}
        if entry.get("generation") != family_id:
            entry = {"generation": family_id, "result": "PENDING",
                     "n_dates": int(len({ds.feature_dates[i] for i in layers["holdout"]}))}
            manifest[horizon] = entry
            _write_holdout_manifest(manifest)

        if args.evaluate_holdout:
            if entry.get("result") == "EVALUATED":
                metrics["holdout"] = {"status": "refused", "reason": "holdout already evaluated for this generation"}
            else:
                hold_records = score_layer(ranker["model"], absolute["clf"], absolute["reg"],
                                           ds, layers["holdout"], horizon)
                hold = _layer_metrics(hold_records, calibrator, histories, kse_rows, horizon,
                                      n_trials=n_trials)
                hold_cal = calibration_report(hold_records, calibrator)
                metrics.update(hold)
                metrics["calibration_ece"] = hold_cal["beat_market"]["ece"]
                metrics["calibration_brier"] = hold_cal["beat_market"]["brier"]
                metrics["evaluated_on"] = "holdout"
                entry["result"] = "EVALUATED"
                manifest[horizon] = entry
                _write_holdout_manifest(manifest)

        all_metrics[horizon] = metrics

    (ML_DIR / "ranker_metrics.json").write_text(
        json.dumps(all_metrics, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"horizons": {h: (m.get("status") or m.get("evaluated_on"))
                                   for h, m in all_metrics.items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
