from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.signals_v2.schemas import MlPrediction

ML_DIR = Path(__file__).resolve().parents[2] / "ml" / "signals_v2"


class SignalModelLoader:
    """Serves ML predictions to the signal engine.

    The V2 absolute classifier was retired after its shadow evaluation was blocked
    (negative excess return, all promotion gates failed). Until the V3.1
    cross-sectional ranker artifacts land (see
    docs/superpowers/plans/2026-07-22-signals-v3.1-ranker.md, T18), every
    prediction is UNAVAILABLE and the engine falls back to the technical rating.
    """

    def predict(self, horizon: str, features: dict[str, Any]) -> MlPrediction:
        return MlPrediction(status="UNAVAILABLE")


model_loader = SignalModelLoader()
