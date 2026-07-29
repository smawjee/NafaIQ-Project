import json
from datetime import date, timedelta

import joblib
import numpy as np
import pytest

from app.services.signals_v2.feature_store import FEATURE_VERSION
from app.services.signals_v2.model_loader import SignalModelLoader
from app.services.signals_v2.ranking import DualCalibrator
from app.services.signals_v2.training import SIGNAL_FEATURES_V3


class _StubRanker:
    def predict(self, X):
        return np.asarray([2.5] * len(X))


class _StubClf:
    classes_ = np.asarray([0, 1])

    def predict_proba(self, X):
        return np.asarray([[0.3, 0.7]] * len(X))


class _StubReg:
    def predict(self, X):
        return np.asarray([0.02] * len(X))


def _write_artifacts(ml_dir, *, as_of=None, feature_version=FEATURE_VERSION):
    ml_dir.mkdir(parents=True, exist_ok=True)
    cal = DualCalibrator(beat_iso=None, pos_iso=None, support=500)
    joblib.dump({"model": _StubRanker(), "calibrator": cal, "config": {"name": "t"},
                 "feature_names": list(SIGNAL_FEATURES_V3), "horizon": "20D",
                 "feature_version": feature_version}, ml_dir / "ranker_20d.joblib")
    joblib.dump({"clf": _StubClf(), "reg": _StubReg(), "horizon": "20D",
                 "feature_names": list(SIGNAL_FEATURES_V3)}, ml_dir / "absolute_20d.joblib")
    as_of = as_of or date.today()
    # thresholds where score 2.5 lands in the top decile
    thresholds = list(np.linspace(0, 2.6, 101))
    (ml_dir / "rank_thresholds_20d.json").write_text(json.dumps(
        {"as_of": as_of.isoformat(), "horizon": "20D",
         "score_percentiles": thresholds, "count": 100}), encoding="utf-8")


def _features():
    return {name: 0.1 for name in SIGNAL_FEATURES_V3}


def test_fresh_ranker_predicts_with_isolation_fields(tmp_path):
    _write_artifacts(tmp_path)
    loader = SignalModelLoader(ml_dir=tmp_path)
    pred = loader.predict("20D", _features())
    assert pred.status != "UNAVAILABLE"
    assert pred.source == "ranker-v3.1"
    assert pred.eligible_for_fusion is False
    assert pred.signal is not None


def test_stale_thresholds_unavailable_no_classifier_fallback(tmp_path):
    _write_artifacts(tmp_path, as_of=date.today() - timedelta(days=30))
    loader = SignalModelLoader(ml_dir=tmp_path)
    pred = loader.predict("20D", _features())
    assert pred.status == "UNAVAILABLE"
    assert pred.signal is None


def test_feature_version_mismatch_unavailable(tmp_path):
    _write_artifacts(tmp_path, feature_version="v2-legacy")
    loader = SignalModelLoader(ml_dir=tmp_path)
    pred = loader.predict("20D", _features())
    assert pred.status == "UNAVAILABLE"


def test_missing_artifacts_unavailable(tmp_path):
    loader = SignalModelLoader(ml_dir=tmp_path)
    assert loader.predict("20D", _features()).status == "UNAVAILABLE"
