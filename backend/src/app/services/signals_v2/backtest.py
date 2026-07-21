from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from app.services.signals_v2.labels import SignalLabel


@dataclass(frozen=True)
class BarrierLabel:
    index: int
    label: SignalLabel
    forward_return: float
    exit_index: int


def triple_barrier_labels(
    close: Iterable[float],
    atr_pct: Iterable[float],
    *,
    horizon: int,
    profit_mult: float = 2.0,
    loss_mult: float = 1.5,
) -> list[BarrierLabel]:
    prices = np.asarray(list(close), dtype=np.float64)
    atr = np.asarray(list(atr_pct), dtype=np.float64)
    labels: list[BarrierLabel] = []
    for i in range(len(prices) - horizon):
        if prices[i] <= 0:
            continue
        width = max(float(atr[i]) if i < len(atr) and np.isfinite(atr[i]) else 0.03, 0.02)
        up = prices[i] * (1 + width * profit_mult)
        down = prices[i] * (1 - width * loss_mult)
        exit_i = i + horizon
        label = SignalLabel.HOLD
        for j in range(i + 1, min(len(prices), i + horizon + 1)):
            if prices[j] >= up:
                label = SignalLabel.BUY if width < 0.05 else SignalLabel.STRONG_BUY
                exit_i = j
                break
            if prices[j] <= down:
                label = SignalLabel.SELL if width < 0.05 else SignalLabel.STRONG_SELL
                exit_i = j
                break
        ret = float(prices[exit_i] / prices[i] - 1) if prices[i] else 0.0
        labels.append(BarrierLabel(index=i, label=label, forward_return=ret, exit_index=exit_i))
    return labels


def precision_by_class(predicted: list[SignalLabel], actual: list[SignalLabel]) -> dict[str, float]:
    out: dict[str, float] = {}
    for label in SignalLabel:
        if label == SignalLabel.NO_SIGNAL:
            continue
        idx = [i for i, p in enumerate(predicted) if p == label]
        if not idx:
            out[label.value] = 0.0
            continue
        out[label.value] = sum(1 for i in idx if actual[i] == label) / len(idx)
    return out
