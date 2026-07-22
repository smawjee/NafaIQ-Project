"""V3.1-only model loader: cross-sectional ranker artifacts or nothing.

The V2 absolute classifier was retired (blocked shadow evaluation). The chain is:
(1) ranker + absolute artifacts with fresh rank thresholds and a matching feature
version -> shadow prediction with structural fusion isolation; (2) anything
missing/stale/mismatched -> UNAVAILABLE (the engine then shows the Technical
Rating and AI NO_SIGNAL). There is deliberately no legacy-classifier fallback.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.services.signals_v2.constants import RANK_STALENESS_DAYS
from app.services.signals_v2.schemas import MlPrediction

_DEFAULT_ML_DIR = Path(__file__).resolve().parents[2] / "ml" / "signals_v2"
_SOURCE = "ranker-v3.1"


class SignalModelLoader:
    def __init__(self, ml_dir: Path | None = None) -> None:
        self._ml_dir = Path(ml_dir) if ml_dir is not None else _DEFAULT_ML_DIR
        self._loaded: dict[str, tuple[Any, Any, dict] | None] = {}

    def predict(self, horizon: str, features: dict[str, Any]) -> MlPrediction:
        from app.services.signals_v2.feature_store import FEATURE_VERSION
        from app.services.signals_v2.ranking import (
            MIN_CAL_SUPPORT, CombinedOOSPrediction, rank_to_signal)
        from app.services.signals_v2.training import has_core_features, vectorize_v3

        loaded = self._load(horizon)
        if loaded is None:
            return MlPrediction(status="UNAVAILABLE", source=_SOURCE)
        ranker_art, absolute_art, thresholds = loaded

        if ranker_art.get("feature_version") != FEATURE_VERSION:
            return MlPrediction(status="UNAVAILABLE", source=_SOURCE)
        as_of = date.fromisoformat(str(thresholds.get("as_of"))[:10])
        if (date.today() - as_of).days > RANK_STALENESS_DAYS:
            return MlPrediction(status="UNAVAILABLE", source=_SOURCE)
        if not has_core_features(features):
            return MlPrediction(status="UNAVAILABLE", source=_SOURCE)

        feat_names = ranker_art["feature_names"]
        vec = vectorize_v3(features, feat_names).reshape(1, -1)
        score = float(ranker_art["model"].predict(vec)[0])
        pcts = np.asarray(thresholds["score_percentiles"], dtype=np.float64)
        percentile = float(np.clip(np.searchsorted(pcts, score, side="right") / max(1, len(pcts) - 1), 0.0, 1.0))

        clf, reg = absolute_art["clf"], absolute_art["reg"]
        p_pos_raw = float(clf.predict_proba(vec)[0][list(clf.classes_).index(1)]) \
            if 1 in list(clf.classes_) else 0.0
        e_abs = float(reg.predict(vec)[0])

        cal = ranker_art["calibrator"]
        dummy = CombinedOOSPrediction(0, "", "UNKNOWN", as_of, as_of, as_of, horizon,
                                      score, percentile, 0.0, 0.0, 0.0, "HOLD", p_pos_raw, e_abs)
        cp = cal.apply(dummy)
        label = rank_to_signal(percentile=percentile, p_beat_market=cp.p_beat_market,
                               expected_excess_net=cp.expected_excess_net,
                               p_positive_absolute=cp.p_positive_absolute,
                               expected_absolute_net=cp.expected_absolute_net,
                               data_quality_ok=True, liquidity_ok=True, risk_ok=True,
                               calibration_support_ok=cp.calibration_support >= MIN_CAL_SUPPORT)
        confidence = round(max(cp.p_beat_market, 1 - cp.p_beat_market) * 100, 1)
        return MlPrediction(
            signal=label,
            confidence=confidence,
            probabilities={"beat market": round(cp.p_beat_market * 100, 1),
                           "positive net return": round(cp.p_positive_absolute * 100, 1)},
            model_version=f"{_SOURCE}-{horizon.lower()}",
            status="SHADOW",
            eligible_for_fusion=False,
            source=_SOURCE,
        )

    def _load(self, horizon: str) -> tuple[Any, Any, dict] | None:
        key = horizon.upper()
        if key in self._loaded:
            return self._loaded[key]
        ranker_path = self._ml_dir / f"ranker_{key.lower()}.joblib"
        absolute_path = self._ml_dir / f"absolute_{key.lower()}.joblib"
        thresholds_path = self._ml_dir / f"rank_thresholds_{key.lower()}.json"
        if not (ranker_path.exists() and absolute_path.exists() and thresholds_path.exists()):
            self._loaded[key] = None
            return None
        try:
            ranker_art = joblib.load(ranker_path)
            absolute_art = joblib.load(absolute_path)
            thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
        except Exception:
            self._loaded[key] = None
            return None
        self._loaded[key] = (ranker_art, absolute_art, thresholds)
        return self._loaded[key]


model_loader = SignalModelLoader()
