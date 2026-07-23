#!/usr/bin/env python
"""T16 — daily batch scorer. Scores one common trading date atomically.

Atomic sequence: start_scoring_run (STARTED) -> insert rows -> complete_scoring_run
(COMPLETE iff written == expected, else FAILED). The API serves only the latest
COMPLETE run, so a partial batch is never user-visible.
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import joblib
import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from train_signals_v2 import _client, _select_all, _select_ohlcv_adjusted, _select_where

from app.services.signals_v2.explain import top_contributions
from app.services.signals_v2.feature_store import FEATURE_VERSION
from app.services.signals_v2.features import build_feature_frame, compute_feature_snapshot
from app.services.signals_v2.ranking import (
    CombinedOOSPrediction,
    MIN_CAL_SUPPORT,
    eligible_universe,
    rank_to_signal,
)
from app.services.signals_v2.training import (
    SIGNAL_FEATURES_V3,
    _parse_date,
    group_rows,
    has_core_features,
    map_rows,
    vectorize_v3,
)

ML_DIR = ROOT / "src" / "app" / "ml" / "signals_v2"
PRIMARY = "20D"
MIN_CROSS_SECTION = 20


def latest_common_date(histories: dict[str, list[dict]], min_symbols: int = 50) -> date | None:
    counts: Counter = Counter()
    for rows in histories.values():
        for r in rows:
            if float(r.get("close") or 0) > 0:
                counts[_parse_date(r.get("date"))] += 1
    dense = [d for d, c in counts.items() if c >= min_symbols]
    return max(dense) if dense else None


def score_cross_section(histories, profiles, kse_rows, ranker_art, absolute_art, as_of, horizon) -> list[dict]:
    ranker, cal, feat_names = ranker_art["model"], ranker_art["calibrator"], ranker_art["feature_names"]
    clf, reg = absolute_art["clf"], absolute_art["reg"]
    universe = eligible_universe(histories, as_of)
    rows_out, scores, feats_by_sym = [], [], {}
    for sym in sorted(universe):
        rows = sorted(histories[sym], key=lambda r: str(r.get("date")))
        upto = [r for r in rows if _parse_date(r.get("date")) <= as_of]
        frame = build_feature_frame(symbol=sym, ohlcv_rows=upto, fundamentals={},
                                    profile=profiles.get(sym, {}), kse_rows=kse_rows)
        feats = compute_feature_snapshot(frame)
        if not has_core_features(feats):
            continue
        vec = vectorize_v3(feats, feat_names)
        feats_by_sym[sym] = vec
        scores.append((sym, float(ranker.predict(vec.reshape(1, -1))[0])))
    if len(scores) < MIN_CROSS_SECTION:
        return []
    from scipy.stats import rankdata
    svals = np.asarray([s for _, s in scores])
    pcts = (rankdata(svals, method="average") - 1) / (len(svals) - 1)
    thresholds = [float(v) for v in np.percentile(svals, np.arange(101))]
    ML_DIR.mkdir(parents=True, exist_ok=True)
    (ML_DIR / f"rank_thresholds_{horizon.lower()}.json").write_text(
        json.dumps({"as_of": as_of.isoformat(), "horizon": horizon,
                    "score_percentiles": thresholds, "count": len(svals)}, indent=2), encoding="utf-8")
    for (sym, score), pct in zip(scores, pcts):
        vec = feats_by_sym[sym].reshape(1, -1)
        p_pos = float(clf.predict_proba(vec)[0][list(clf.classes_).index(1)]) if 1 in list(clf.classes_) else 0.0
        e_abs = float(reg.predict(vec)[0])
        sector = str((profiles.get(sym) or {}).get("sector") or "UNKNOWN")
        # calibrate percentile -> p_beat via the stored calibrator
        dummy = CombinedOOSPrediction(0, sym, sector, as_of, as_of, as_of, horizon,
                                      score, float(pct), 0.0, 0.0, 0.0, "HOLD", p_pos, e_abs)
        cp = cal.apply(dummy)
        label = rank_to_signal(percentile=float(pct), p_beat_market=cp.p_beat_market,
                               expected_excess_net=cp.expected_excess_net,
                               p_positive_absolute=cp.p_positive_absolute,
                               expected_absolute_net=cp.expected_absolute_net,
                               data_quality_ok=True, liquidity_ok=True, risk_ok=True,
                               calibration_support_ok=cp.calibration_support >= MIN_CAL_SUPPORT)
        explanation = {"ranker": top_contributions(ranker, feats_by_sym[sym], feat_names),
                       "absolute": top_contributions(reg, feats_by_sym[sym], feat_names)}
        rows_out.append({"symbol": sym, "horizon": horizon, "as_of": as_of.isoformat(),
                         "rank_score": round(score, 6), "percentile": round(float(pct), 4),
                         "p_beat_market": cp.p_beat_market, "p_positive_absolute": cp.p_positive_absolute,
                         "expected_excess_return": cp.expected_excess_net,
                         "expected_absolute_return": cp.expected_absolute_net,
                         "signal": label.value, "sector": sector,
                         "explanation_factors": explanation})
    return rows_out


def main() -> int:
    from app.repositories import signals_v3_repo

    load_dotenv(ROOT / ".env")
    client = _client()
    ohlcv = _select_ohlcv_adjusted(client, max_rows_per_symbol=400, mode="price")
    profiles = map_rows(_select_all(client, "psx_profile", "*", order_by="symbol"))
    kse_rows = _select_where(client, "psx_index_eod", "date,close", order_by="date",
                             filters=[("code", "eq", "KSE100")])[-365:]
    histories = group_rows(ohlcv)
    as_of = latest_common_date(histories)
    if as_of is None:
        print(json.dumps({"status": "no_common_date"}))
        return 2

    horizon = PRIMARY
    ranker_path = ML_DIR / f"ranker_{horizon.lower()}.joblib"
    absolute_path = ML_DIR / f"absolute_{horizon.lower()}.joblib"
    if not ranker_path.exists() or not absolute_path.exists():
        print(json.dumps({"status": "no_artifacts"}))
        return 2
    ranker_art, absolute_art = joblib.load(ranker_path), joblib.load(absolute_path)
    if ranker_art.get("feature_version") != FEATURE_VERSION:
        print(json.dumps({"status": "feature_version_mismatch",
                          "artifact": ranker_art.get("feature_version"), "required": FEATURE_VERSION}))
        return 2
    model_version = f"ranker-v3.1-{horizon.lower()}"

    rows = score_cross_section(histories, profiles, kse_rows, ranker_art, absolute_art, as_of, horizon)
    if not rows:
        print(json.dumps({"status": "empty_cross_section", "as_of": as_of.isoformat()}))
        return 2

    async def _publish() -> tuple[str, int, str]:
        run_id = await signals_v3_repo.start_scoring_run(
            as_of=as_of.isoformat(), model_version=model_version,
            feature_version=FEATURE_VERSION, expected=len(rows))
        written = await signals_v3_repo.insert_signals(
            run_id, rows, model_version=model_version, feature_version=FEATURE_VERSION)
        status = await signals_v3_repo.complete_scoring_run(run_id, written=written, expected=len(rows))
        return run_id, written, status

    run_id, written, status = asyncio.run(_publish())
    print(json.dumps({"as_of": as_of.isoformat(), "rows": len(rows), "written": written,
                      "run_id": run_id, "run_status": status}))
    return 0 if status == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
