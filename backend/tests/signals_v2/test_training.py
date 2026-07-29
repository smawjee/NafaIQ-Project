from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np

from app.services.signals_v2.training import ProbabilityCalibrator, build_dataset, load_dataset, sample_weights, save_dataset


def _history(symbol: str, n: int = 130) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    price = 100.0
    for i in range(n):
        price *= 1.002 if i % 20 < 12 else 0.997
        rows.append(
            {
                "symbol": symbol,
                "date": (start + timedelta(days=i)).isoformat(),
                "open": price * 0.99,
                "high": price * 1.02,
                "low": price * 0.98,
                "close": price,
                "volume": 100_000 + i * 100,
            }
        )
    return rows


def test_build_dataset_creates_feature_matrix():
    dataset = build_dataset(
        histories={"HBL": _history("HBL")},
        fundamentals={"HBL": {"pe": 7, "pb": 1.2, "roe": 18, "div_yield": 6, "payout": 30}},
        profiles={"HBL": {"sector": "Finance"}},
        kse_rows=[{"date": r["date"], "close": 100 + i} for i, r in enumerate(_history("KSE"))],
        horizon="5D",
    )
    assert dataset.X.shape[0] > 0
    assert dataset.X.shape[1] == len(dataset.feature_names)
    assert len(dataset.y) == dataset.X.shape[0]
    assert len(dataset.technical_labels) == dataset.X.shape[0]
    assert len(dataset.benchmark_forward_returns) == dataset.X.shape[0]


def test_sample_weights_balance_classes():
    weights = sample_weights(np.asarray(["BUY", "BUY", "HOLD"], dtype=object))
    assert weights[-1] > weights[0]


def test_probability_calibrator_preserves_probability_shape():
    probs = np.asarray(
        [
            [0.1, 0.1, 0.7, 0.05, 0.05],
            [0.05, 0.1, 0.1, 0.7, 0.05],
        ],
        dtype=np.float64,
    )
    calibrator = ProbabilityCalibrator.fit(probs, np.asarray(["HOLD", "BUY"], dtype=object))
    calibrated = calibrator.transform(probs)
    assert calibrated.shape == probs.shape
    assert np.allclose(np.sum(calibrated, axis=1), 1)


def test_feature_store_roundtrip():
    dataset = build_dataset(
        histories={"HBL": _history("HBL")},
        fundamentals={"HBL": {"pe": 7}},
        profiles={"HBL": {"sector": "Finance"}},
        kse_rows=[{"date": r["date"], "close": 100 + i} for i, r in enumerate(_history("KSE"))],
        horizon="5D",
    )
    path = Path(__file__).resolve().parents[2] / "artifacts" / "test_signals_v2_5d.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        save_dataset(dataset, str(path))
        restored = load_dataset(str(path))
        assert restored.X.shape == dataset.X.shape
        assert restored.y.tolist() == dataset.y.tolist()
        assert restored.feature_names == dataset.feature_names
    finally:
        path.unlink(missing_ok=True)
