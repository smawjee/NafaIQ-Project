"""Leakage-resistant research primitives for the V4 event model.

These helpers are intentionally research-only. They consume realized outcomes
to fit and evaluate a candidate, but never return those outcomes in a live
feature or prediction object.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Iterator, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import log_loss
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

from app.services.signals_v4.event_model import EVENT_FEATURES
from app.services.signals_v4.events import validate_live_features

HORIZON_SESSIONS = 20


@dataclass(frozen=True)
class EventRecord:
    event_id: str
    symbol: str
    event_date: date
    features: dict[str, Any]
    excess_return_net: float


def records_from_rows(rows: Iterable[dict[str, Any]]) -> list[EventRecord]:
    """Build a point-in-time research set with an explicit outcome boundary."""
    records: list[EventRecord] = []
    for row in rows:
        # The target is allowed only at this research boundary. Every other
        # realized field is rejected before feature selection can hide it.
        validate_live_features({key: value for key, value in row.items() if key != 'excess_return_net'})
        features = {name: row.get(name) for name in EVENT_FEATURES}
        validate_live_features(features)
        try:
            outcome = float(row["excess_return_net"])
            event_date = date.fromisoformat(str(row["event_date"])[:10])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("research rows require event_date and excess_return_net") from exc
        if not np.isfinite(outcome):
            raise ValueError("non-finite realized outcome")
        records.append(EventRecord(
            event_id=str(row["event_id"]),
            symbol=str(row["symbol"]).upper(),
            event_date=event_date,
            features=features,
            excess_return_net=outcome,
        ))
    return sorted(records, key=lambda record: (record.event_date, record.event_id))


def anchored_purged_walk_forward(
    records: Sequence[EventRecord], *, min_train: int = 500, validation_size: int = 100,
    embargo: int = HORIZON_SESSIONS,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Yield expanding train/validation indices with a horizon embargo."""
    if min_train <= 0 or validation_size <= 0 or embargo < HORIZON_SESSIONS:
        raise ValueError("invalid walk-forward parameters")
    start = min_train
    while start < len(records):
        validation_end = min(start + validation_size, len(records))
        # Purge the final horizon-sized block before validation. This is
        # conservative for irregular event timing and cannot leak outcomes.
        train_end = start - embargo
        if train_end < min_train:
            start = validation_end
            continue
        yield np.arange(train_end), np.arange(start, validation_end)
        start = validation_end


def fit_logistic_candidate(records: Sequence[EventRecord]) -> tuple[Any, Any]:
    """Fit regularized direction and excess-return candidates for research."""
    X = _matrix(records)
    y_direction = (np.asarray([record.excess_return_net for record in records]) > 0).astype(int)
    y_return = np.asarray([record.excess_return_net for record in records], dtype=np.float64)
    classifier = make_pipeline(StandardScaler(), LogisticRegression(C=0.25, max_iter=2000, class_weight="balanced"))
    regressor = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    classifier.fit(X, y_direction)
    regressor.fit(X, y_return)
    return classifier, regressor


def conformal_interval(residuals: Sequence[float], *, coverage: float = 0.80) -> tuple[float, float]:
    """Return a symmetric finite-sample residual radius for an 80% interval."""
    if not 0 < coverage < 1:
        raise ValueError("coverage must be between zero and one")
    values = np.abs(np.asarray(list(residuals), dtype=np.float64))
    values = values[np.isfinite(values)]
    if not len(values):
        raise ValueError("conformal calibration requires residuals")
    radius = float(np.quantile(values, min(1.0, np.ceil((len(values) + 1) * coverage) / len(values)), method="higher"))
    return -radius, radius


def evaluate_probability(y_true: Sequence[int], p_outperform: Sequence[float]) -> float:
    """Research metric helper; live scoring never receives y_true."""
    return float(log_loss(np.asarray(y_true), np.clip(np.asarray(p_outperform), 1e-6, 1 - 1e-6)))


def _matrix(records: Sequence[EventRecord]) -> np.ndarray:
    return np.asarray([[float(record.features.get(name) or 0.0) for name in EVENT_FEATURES] for record in records], dtype=np.float64)
