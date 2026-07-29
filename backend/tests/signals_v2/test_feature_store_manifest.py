import numpy as np
import pytest

from app.services.signals_v2.feature_store import (
    FEATURE_VERSION, dataset_hash, load_verified_store, write_manifest,
)
from app.services.signals_v2.training import Dataset, save_dataset


def _tiny_dataset():
    from datetime import date
    return Dataset(
        X=np.array([[0.1, 0.2], [0.3, 0.4]]), y=np.asarray(["1", "0"], dtype=object),
        dates=[date(2024, 1, 1), date(2024, 1, 1)], symbols=["A", "B"],
        forward_returns=np.array([0.01, -0.01]), benchmark_forward_returns=np.array([0.0, 0.0]),
        technical_labels=np.asarray(["HOLD", "HOLD"], dtype=object), feature_names=["f0", "f1"],
    )


def test_manifest_roundtrip_and_hash_stable(tmp_path):
    ds = _tiny_dataset()
    p = tmp_path / "store.npz"
    save_dataset(ds, str(p))
    m = write_manifest(str(p), feature_names=ds.feature_names, X=ds.X, pit_safe=True,
                       min_history=260, corp_action_audit_version="2026-07-22")
    assert m["feature_version"] == FEATURE_VERSION
    assert m["dataset_hash"] == dataset_hash(ds.X, ds.feature_names)
    loaded, manifest = load_verified_store(str(p))
    assert manifest["pit_safe"] is True and loaded.X.shape == (2, 2)


def test_legacy_store_without_manifest_is_refused(tmp_path):
    ds = _tiny_dataset()
    p = tmp_path / "legacy.npz"
    save_dataset(ds, str(p))                      # no manifest written
    with pytest.raises(ValueError):
        load_verified_store(str(p))


def test_build_dataset_v3_mode_excludes_fundamentals_preserves_nan():
    from datetime import date, timedelta

    from app.services.signals_v2.training import SIGNAL_FEATURES_V3, build_dataset

    start = date(2023, 1, 2)
    rows = []
    d = start
    for i in range(150):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        c = 100.0 * (1.002 ** i)
        rows.append({"symbol": "TST", "date": d.isoformat(), "open": c, "high": c * 1.01,
                     "low": c * 0.99, "close": c, "volume": 10_000})
        d += timedelta(days=1)
    kse_rows = [{"date": r["date"], "close": 1000.0} for r in rows]
    ds = build_dataset(histories={"TST": rows}, fundamentals={}, profiles={}, kse_rows=kse_rows,
                       horizon="20D", min_history=80, sample_stride=10,
                       feature_names=SIGNAL_FEATURES_V3, preserve_nan=True)
    assert len(ds.y) > 0
    assert ds.feature_names == SIGNAL_FEATURES_V3
    assert ds.X.shape[1] == 36
    # 150 bars < 240 lookback -> ret_240d missing, preserved as NaN (not zero-filled)
    col = SIGNAL_FEATURES_V3.index("ret_240d")
    assert np.isnan(ds.X[:, col]).all()
