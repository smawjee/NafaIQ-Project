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
