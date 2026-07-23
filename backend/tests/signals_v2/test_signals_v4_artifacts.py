from datetime import date, timedelta

import pytest

from app.services.signals_v4.artifacts import ArtifactRejected, validate_artifact_manifest
from app.services.signals_v4.research import anchored_purged_walk_forward, records_from_rows


def _manifest(**overrides):
    values = {
        "status": "PROMOTED",
        "horizon_sessions": 20,
        "feature_names": ["earnings_surprise"],
        "promotion": {
            "status": "VALIDATED", "eligible_events": 1500, "symbols": 120,
            "holdout_forecasts": 200, "positive_folds": 3, "precision": 0.60,
            "ece": 0.05, "dsr": 0.95, "pbo": 0.20,
        },
        "artifact_sha256": "abc123",
    }
    values.update(overrides)
    return values


def test_red_artifact_is_not_loadable():
    with pytest.raises(ArtifactRejected, match="MODEL_NOT_PROMOTED"):
        validate_artifact_manifest(_manifest(status="RED"), actual_sha256="abc123")


def test_artifact_hash_and_manifest_are_required():
    with pytest.raises(ArtifactRejected, match="ARTIFACT_HASH_MISMATCH"):
        validate_artifact_manifest(_manifest(), actual_sha256="different")


def test_research_rows_reject_non_target_realized_fields():
    with pytest.raises(ValueError, match="realized outcome"):
        records_from_rows([{
            "event_id": "e1", "symbol": "TEST", "event_date": "2026-01-01",
            "earnings_surprise": 0.2, "excess_return_net": 0.1, "realized_return": 0.2,
        }])


def test_walk_forward_has_horizon_embargo():
    start = date(2020, 1, 1)
    rows = [{
        "event_id": str(i), "symbol": "TEST", "event_date": (start + timedelta(days=i)).isoformat(),
        "earnings_surprise": 0.1, "excess_return_net": 0.01,
    } for i in range(40)]
    records = records_from_rows(rows)
    train, validation = next(anchored_purged_walk_forward(records, min_train=10, validation_size=5))
    assert records[train[-1]].event_date <= records[validation[0]].event_date - timedelta(days=20)