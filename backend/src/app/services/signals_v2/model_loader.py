from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.services.signals_v2.labels import SignalLabel
from app.services.signals_v2.schemas import MlPrediction

ML_DIR = Path(__file__).resolve().parents[2] / "ml" / "signals_v2"


class SignalModelLoader:
    def __init__(self) -> None:
        self._loaded: dict[str, tuple[Any, Any, Any, list[str], dict[str, Any]]] = {}

    def predict(self, horizon: str, features: dict[str, Any]) -> MlPrediction:
        loaded = self._load(horizon)
        if loaded is None:
            return MlPrediction(status="UNAVAILABLE")
        model, scaler, calibrator, feature_names, meta = loaded
        x = np.asarray([[float(features.get(name) or 0) for name in feature_names]], dtype=np.float64)
        if scaler is not None:
            x = scaler.transform(x)
        if not hasattr(model, "predict_proba"):
            return MlPrediction(status="UNAVAILABLE")
        probs = model.predict_proba(x)[0]
        if calibrator is not None and hasattr(calibrator, "transform"):
            probs = calibrator.transform(np.asarray([probs], dtype=np.float64))[0]
        classes = [str(c) for c in getattr(model, "classes_", [])]
        if not classes:
            return MlPrediction(status="UNAVAILABLE")
        idx = int(np.argmax(probs))
        label = _class_to_label(classes[idx])
        prob_map = {_class_to_display(cls): round(float(prob) * 100, 1) for cls, prob in zip(classes, probs)}
        return MlPrediction(
            signal=label,
            confidence=round(float(probs[idx]) * 100, 1),
            probabilities=prob_map,
            model_version=str(meta.get("model_version") or f"ml-v2-{horizon.lower()}"),
            status=_prediction_status(meta.get("status")),  # type: ignore[arg-type]
        )

    def _load(self, horizon: str) -> tuple[Any, Any, Any, list[str], dict[str, Any]] | None:
        key = horizon.upper()
        if key in self._loaded:
            return self._loaded[key]
        model_path = ML_DIR / f"model_{key.lower()}.joblib"
        feature_path = ML_DIR / "feature_list.json"
        meta_path = ML_DIR / "model_card.json"
        if not model_path.exists() or not feature_path.exists():
            return None
        try:
            artifact = joblib.load(model_path)
            if isinstance(artifact, dict) and "model" in artifact:
                model = artifact["model"]
                scaler = artifact.get("scaler")
                calibrator = artifact.get("calibrator")
            else:
                model = artifact
                scaler = None
                calibrator = None
            feature_names = json.loads(feature_path.read_text())
            meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        except Exception:
            return None
        self._loaded[key] = (model, scaler, calibrator, feature_names, meta)
        return self._loaded[key]


def _class_to_label(value: str) -> SignalLabel:
    try:
        return SignalLabel[value.replace(" ", "_")]
    except KeyError:
        return SignalLabel.HOLD


def _class_to_display(value: str) -> str:
    return value.replace("_", " ")


def _prediction_status(value: Any) -> str:
    raw = str(value or "").upper()
    if raw in {"VALIDATED", "PRODUCTION", "ML_VALIDATED"}:
        return "VALIDATED"
    if raw in {"UNAVAILABLE", "NOT_TRAINED", "SHADOW_NOT_TRAINED"}:
        return "UNAVAILABLE"
    return "SHADOW"


model_loader = SignalModelLoader()
