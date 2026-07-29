"""Optional LightGBM research candidate; never imported by the API."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from app.services.signals_v4.event_model import EVENT_FEATURES
from app.services.signals_v4.research import EventRecord


def fit_candidate(records: Sequence[EventRecord]) -> tuple[Any, Any]:
    try:
        from lightgbm import LGBMClassifier, LGBMRegressor
    except ImportError as exc:
        raise RuntimeError("install the signals-ml extra to run LightGBM research") from exc
    X = np.asarray([[float(record.features.get(name) or 0.0) for name in EVENT_FEATURES] for record in records], dtype=np.float64)
    y_direction = (np.asarray([record.excess_return_net for record in records]) > 0).astype(int)
    y_return = np.asarray([record.excess_return_net for record in records], dtype=np.float64)
    classifier = LGBMClassifier(n_estimators=100, learning_rate=0.03, num_leaves=15, reg_lambda=2.0, verbosity=-1)
    regressor = LGBMRegressor(n_estimators=100, learning_rate=0.03, num_leaves=15, reg_lambda=2.0, verbosity=-1)
    classifier.fit(X, y_direction)
    regressor.fit(X, y_return)
    return classifier, regressor
