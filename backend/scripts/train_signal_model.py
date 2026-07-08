#!/usr/bin/env python
"""Train the PSX signal ML model.

Runs walk-forward validation across 3 time folds, trains final model,
saves artifacts to app/ml/.

Usage:
  python scripts/train_signal_model.py

Requirements:
  - psx_ohlcv table populated with at least 1 year of data
  - psx_fundamentals table populated
  - service_role supabase key in PSX_SUPABASE_URL / PSX_SUPABASE_SERVICE_ROLE_KEY env

Output:
  app/ml/signal_model.joblib    - trained GradientBoostingClassifier
  app/ml/scaler.joblib          - StandardScaler for feature normalization
  app/ml/feature_list.json      - ordered feature names
  app/ml/metrics.json           - walk-forward validation metrics
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import joblib
import structlog
from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from app.ml.features import compute_features, features_array, FEATURE_NAMES

load_dotenv()

log = structlog.get_logger()

ML_DIR = Path(__file__).resolve().parent.parent / "src" / "app" / "ml"
ML_DIR.mkdir(parents=True, exist_ok=True)

LABELS = {"STRONG SELL": -2, "SELL": -1, "HOLD": 0, "BUY": 1, "STRONG BUY": 2}
LABELS_REV = {v: k for k, v in LABELS.items()}


def forward_return(closes, i, horizon=20):
    """Forward 20-trading-day total return from index i."""
    if i + horizon >= len(closes) or closes[i] == 0:
        return 0.0
    return (closes[i + horizon] - closes[i]) / closes[i]


def ret_to_label(ret):
    if ret >= 0.05:
        return 2  # STRONG BUY
    if ret >= 0.0:
        return 1  # BUY
    if ret >= -0.03:
        return 0  # HOLD
    if ret >= -0.08:
        return -1  # SELL
    return -2  # STRONG SELL


def load_ohlcv(supabase, symbol):
    try:
        result = supabase.table("psx_ohlcv") \
            .select("*") \
            .eq("symbol", symbol.upper()) \
            .order("date", desc=False) \
            .execute()
        return result.data or []
    except Exception:
        log.warning("load_ohlcv_failed", symbol=symbol)
        return []


def load_fundamentals(supabase, symbol):
    try:
        result = supabase.table("psx_fundamentals") \
            .select("*") \
            .eq("symbol", symbol.upper()) \
            .execute()
        rows = result.data or []
        if rows:
            return rows[0]
    except Exception:
        pass
    return {}


def compute_pe_zscores(fundamentals_map):
    pe_values = [
        v.get("pe")
        for v in fundamentals_map.values()
        if v.get("pe") and v["pe"] > 0
    ]
    if len(pe_values) < 5:
        return {}
    mean_pe = np.mean(pe_values)
    std_pe = np.std(pe_values)
    zscores = {}
    for sym, f in fundamentals_map.items():
        pe = f.get("pe")
        if pe and pe > 0 and std_pe > 0:
            zscores[sym] = (pe - mean_pe) / std_pe
        else:
            zscores[sym] = 0.0
    return zscores


def build_dataset(supabase):
    symbols_result = supabase.table("psx_profile").select("symbol").execute()
    symbols = [r["symbol"] for r in (symbols_result.data or [])]
    if not symbols:
        log.error("no_symbols")
        return [], [], [], {}

    log.info("building_dataset", symbols=len(symbols))

    fundamentals_map = {}
    for sym in symbols:
        fundamentals_map[sym] = load_fundamentals(supabase, sym)

    pe_zscores = compute_pe_zscores(fundamentals_map)

    X_list = []
    y_list = []
    symbol_list = []
    meta_list = []

    total_rows = 0
    for sym in symbols:
        rows = load_ohlcv(supabase, sym)
        if len(rows) < 80:
            continue

        dates = [r["date"] for r in rows]
        closes = [float(r["close"] or 0) for r in rows]
        highs = [float(r["high"] or 0) for r in rows]
        lows = [float(r["low"] or 0) for r in rows]
        volumes = [float(r["volume"] or 0) for r in rows]

        f = fundamentals_map.get(sym, {})
        f["pe_zscore"] = pe_zscores.get(sym, 0.0)

        for i in range(60, len(closes) - 20):
            feat = compute_features(
                closes[i - 60: i + 1],
                highs[i - 60: i + 1],
                lows[i - 60: i + 1],
                volumes[i - 60: i + 1],
                f,
            )
            if not feat:
                continue
            ret = forward_return(closes, i, 20)
            label = ret_to_label(ret)
            X_list.append(features_array(feat))
            y_list.append(label)
            symbol_list.append(sym)
            meta_list.append({
                "symbol": sym,
                "date": dates[i],
                "label": LABELS_REV[label],
                "fwd_return": ret,
            })
        total_rows += len(closes)

    log.info("dataset_built", samples=len(X_list), ohlcv_rows=total_rows)
    return X_list, y_list, symbol_list, meta_list


def main():
    url = os.getenv("PSX_SUPABASE_URL", os.getenv("SUPABASE_URL"))
    key = os.getenv("PSX_SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    if not url or not key:
        log.error("missing_supabase_env")
        return 1

    supabase = create_client(url, key)

    X_list, y_list, symbol_list, meta_list = build_dataset(supabase)
    if len(X_list) < 100:
        log.error("not_enough_data", samples=len(X_list))
        return 1

    X = np.array(X_list, dtype=np.float64)
    y = np.array(y_list, dtype=np.int64)

    mask = np.isfinite(X).all(axis=1)
    X = X[mask]
    y = y[mask]

    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    log.info("features_standardized", mean=np.mean(X), std=np.std(X))

    fold_size = len(X) // 3
    folds = [
        (0, fold_size),
        (0, fold_size * 2),
        (0, fold_size * 3),
    ]
    test_sizes = [fold_size, fold_size, min(fold_size, len(X) - fold_size * 2)]

    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import accuracy_score, classification_report

    counts = np.bincount(y, minlength=5)
    log.info("class_distribution", **{LABELS_REV.get(i, str(i)): int(c) for i, c in enumerate(counts) if c > 0})

    all_metrics = []
    for fold_idx, (train_start, train_end) in enumerate(folds):
        test_start = train_end
        test_end = test_start + test_sizes[fold_idx]
        if test_end > len(X):
            test_end = len(X)

        X_train = X[train_start:test_start]
        y_train = y[train_start:test_start]
        X_test = X[test_start:test_end]
        y_test = y[test_start:test_end]

        model = GradientBoostingClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_leaf=10,
            random_state=42 + fold_idx,
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        all_metrics.append({"fold": fold_idx + 1, "accuracy": acc, "train_samples": len(X_train), "test_samples": len(X_test)})
        log.info("fold_done", **all_metrics[-1])

    final_model = GradientBoostingClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_leaf=10,
        random_state=42,
    )
    final_model.fit(X, y)

    joblib.dump(final_model, ML_DIR / "signal_model.joblib")
    joblib.dump(scaler, ML_DIR / "scaler.joblib")
    with open(ML_DIR / "feature_list.json", "w") as f:
        json.dump(FEATURE_NAMES, f)
    with open(ML_DIR / "metrics.json", "w") as f:
        json.dump({"folds": all_metrics, "total_samples": len(X), "features": len(FEATURE_NAMES)}, f, indent=2)

    log.info("model_saved", path=str(ML_DIR / "signal_model.joblib"))

    importances = sorted(
        zip(FEATURE_NAMES, final_model.feature_importances_),
        key=lambda x: x[1],
        reverse=True,
    )
    for name, imp in importances[:10]:
        log.info("feature_importance", feature=name, importance=round(float(imp), 4))

    return 0


if __name__ == "__main__":
    sys.exit(main())
