import numpy as np
from datetime import date, timedelta

from app.services.signals.features import build_feature_frame, compute_feature_snapshot


def _rows(closes):
    start = date(2024, 1, 1)
    return [{"date": (start + timedelta(days=i)).isoformat(), "open": c, "high": c * 1.01,
             "low": c * 0.99, "close": c, "volume": 1000} for i, c in enumerate(closes)]


def test_reversal_features_computed():
    closes = [100.0] * 100 + list(np.linspace(100, 50, 180)) + [50.0] * 20
    feats = compute_feature_snapshot(build_feature_frame(symbol="TST", ohlcv_rows=_rows(closes)))
    assert feats["ret_120d"] is not None and feats["ret_120d"] < 0
    assert feats["ret_240d"] is not None and feats["ret_240d"] < 0
    expected = closes[-21] / closes[-241] - 1
    assert abs(feats["ret_240d_ex20"] - expected) < 1e-9


def test_reversal_features_none_on_short_history():
    feats = compute_feature_snapshot(build_feature_frame(symbol="TST", ohlcv_rows=_rows([100.0] * 60)))
    assert feats["ret_120d"] is None
    assert feats["ret_240d_ex20"] is None
