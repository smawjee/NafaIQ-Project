"""Signals V3.1 — cross-sectional labeling, splits, dataset, models, calibration, policy."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
from scipy.stats import rankdata

from app.services.signals_v2.constants import ONE_WAY_COST, ROUND_TRIP_COST
from app.services.signals_v2.labels import SignalLabel

PHASE0_THRESHOLDS: dict[str, tuple[float, float]] = {
    "5D": (0.01, 0.03), "20D": (0.02, 0.06), "60D": (0.04, 0.12),
}


def excess_to_label(excess: float, horizon: str) -> SignalLabel:
    band, strong = PHASE0_THRESHOLDS[horizon]
    if excess >= strong:
        return SignalLabel.STRONG_BUY
    if excess >= band:
        return SignalLabel.BUY
    if excess <= -strong:
        return SignalLabel.STRONG_SELL
    if excess <= -band:
        return SignalLabel.SELL
    return SignalLabel.HOLD


def relative_deciles(dates: list[date], excess: np.ndarray, *, n_bins: int = 10, min_names: int = 30) -> np.ndarray:
    out = np.full(len(dates), -1, dtype=np.int64)
    by_date: dict[date, list[int]] = defaultdict(list)
    for i, d in enumerate(dates):
        by_date[d].append(i)
    for idxs in by_date.values():
        if len(idxs) < min_names:
            continue
        arr = np.asarray(idxs)
        vals = excess[arr]
        ranks = rankdata(vals, method="average") - 1  # 0..n-1, ties averaged
        out[arr] = np.clip((ranks * n_bins) // len(idxs), 0, n_bins - 1).astype(np.int64)
    return out


def purged_date_splits(feature_dates: list[date], label_end_dates: list[date], *,
                       folds: int = 4, min_train_dates: int = 20) -> list[tuple[np.ndarray, np.ndarray]]:
    ford = np.asarray([d.toordinal() for d in feature_dates])
    lord = np.asarray([d.toordinal() for d in label_end_dates])
    unique = np.unique(ford)
    fold_size = len(unique) // (folds + 1)
    splits: list[tuple[np.ndarray, np.ndarray]] = []
    for fold in range(1, folds + 1):
        train_dates = unique[: fold_size * fold]
        if len(train_dates) < min_train_dates:
            continue
        test_dates = unique[fold_size * fold: fold_size * (fold + 1)]
        if len(test_dates) == 0:
            continue
        test_start = int(test_dates.min())
        # purge: training sample kept only if its label window closes before the test window opens
        train_mask = np.isin(ford, train_dates) & (lord < test_start)
        test_mask = np.isin(ford, test_dates)
        train_idx = np.flatnonzero(train_mask)
        test_idx = np.flatnonzero(test_mask)
        if len(train_idx) and len(test_idx):
            splits.append((train_idx, test_idx))
    if not splits:
        raise ValueError("not enough dated cross-sections for purged walk-forward")
    return splits


def three_layer_split(feature_dates: list[date], *, calibration_frac: float = 0.2,
                      holdout_frac: float = 0.2, min_support: dict | None = None) -> dict:
    ford = np.asarray([d.toordinal() for d in feature_dates])
    unique = np.unique(ford)
    n = len(unique)
    n_hold = int(n * holdout_frac)
    n_cal = int(n * calibration_frac)
    n_dev = n - n_cal - n_hold
    dev_dates, cal_dates, hold_dates = unique[:n_dev], unique[n_dev:n_dev + n_cal], unique[n_dev + n_cal:]
    support = min_support or {"dev": 30, "calibration": 10, "holdout": 10}
    if len(dev_dates) < support["dev"] or len(cal_dates) < support["calibration"] or len(hold_dates) < support["holdout"]:
        return {"status": "INCONCLUSIVE",
                "reason": f"insufficient dated support dev={len(dev_dates)} cal={len(cal_dates)} hold={len(hold_dates)}"}
    return {
        "dev": np.flatnonzero(np.isin(ford, dev_dates)),
        "calibration": np.flatnonzero(np.isin(ford, cal_dates)),
        "holdout": np.flatnonzero(np.isin(ford, hold_dates)),
    }
