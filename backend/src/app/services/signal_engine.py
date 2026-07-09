from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import joblib
import structlog

from app.db.supabase import get_supabase
from app.ml.features import compute_features, features_array, FEATURE_NAMES

log = structlog.get_logger()

ML_DIR = Path(__file__).resolve().parent.parent / "ml"

LABELS_REV = {2: "STRONG BUY", 1: "BUY", 0: "HOLD", -1: "SELL", -2: "STRONG SELL"}


class SignalEngine:
    def __init__(self):
        self._model = None
        self._scaler = None
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        try:
            model_path = ML_DIR / "signal_model.joblib"
            scaler_path = ML_DIR / "scaler.joblib"
            if model_path.exists() and scaler_path.exists():
                self._model = joblib.load(model_path)
                self._scaler = joblib.load(scaler_path)
                log.info("signal_engine_loaded")
        except Exception:
            log.warning("signal_engine_load_failed", exc_info=True)
        self._loaded = True

    @property
    def is_ready(self) -> bool:
        self._load()
        return self._model is not None

    def predict(self, symbol: str) -> dict:
        self._load()
        if not self._model:
            return _fallback(symbol)

        db = get_supabase()

        try:
            result = (
                db.table("psx_ohlcv")
                .select("*")
                .eq("symbol", symbol.upper())
                .order("date", desc=True)
                .limit(300)
                .execute()
            )
            rows = result.data or []
            if len(rows) < 60:
                return _fallback(symbol)
            rows = list(reversed(rows))
            closes = [float(r["close"] or 0) for r in rows]
            highs = [float(r["high"] or 0) for r in rows]
            lows = [float(r["low"] or 0) for r in rows]
            volumes = [float(r["volume"] or 0) for r in rows]
        except Exception:
            log.exception("signal_ohlcv_fetch_failed", symbol=symbol)
            return _fallback(symbol)

        try:
            result = db.table("psx_fundamentals").select("*").eq("symbol", symbol.upper()).execute()
            f_rows = result.data or []
        except Exception:
            f_rows = []

        fundamentals = f_rows[0] if f_rows else {}
        pe = fundamentals.get("pe")
        pe_zscore = _compute_pe_zscore(pe, db) if pe else 0.0
        fundamentals["pe_zscore"] = pe_zscore

        feats = compute_features(
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            fundamentals=fundamentals,
        )
        if not feats:
            return _fallback(symbol)

        X = np.array(features_array(feats), dtype=np.float64).reshape(1, -1)
        X = self._scaler.transform(X)

        probs = self._model.predict_proba(X)[0]
        pred_class = int(self._model.predict(X)[0])
        confidence = float(probs[pred_class] * 100)

        probs_map = {}
        for cls_idx in range(len(probs)):
            probs_map[LABELS_REV.get(cls_idx, str(cls_idx))] = round(float(probs[cls_idx]) * 100, 1)

        # Feature contributions for top 3 features
        importances = self._model.feature_importances_
        top_idx = np.argsort(importances)[-3:][::-1]
        top_features = [FEATURE_NAMES[i] for i in top_idx]

        return {
            "symbol": symbol.upper(),
            "signal": LABELS_REV.get(pred_class, "HOLD"),
            "confidence": round(confidence, 1),
            "probabilities": probs_map,
            "features_used": top_features,
            "model_version": "1.0.0",
        }


def _compute_pe_zscore(pe: float, db) -> float:
    try:
        result = db.table("psx_fundamentals").select("pe").execute()
        pe_values = [r["pe"] for r in (result.data or []) if r.get("pe") and r["pe"] > 0]
        if len(pe_values) < 5:
            return 0.0
        mean_pe = np.mean(pe_values)
        std_pe = np.std(pe_values)
        if std_pe == 0:
            return 0.0
        return float((pe - mean_pe) / std_pe)
    except Exception:
        return 0.0


def _fallback(symbol: str) -> dict:
    return {
        "symbol": symbol.upper(),
        "signal": "HOLD",
        "confidence": 0,
        "probabilities": {"BUY": 20, "HOLD": 60, "SELL": 20},
        "features_used": [],
        "model_version": "fallback",
    }


_engine: Optional[SignalEngine] = None


def get_signal_engine() -> SignalEngine:
    global _engine
    if _engine is None:
        _engine = SignalEngine()
    return _engine
