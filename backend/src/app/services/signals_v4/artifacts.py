"""Fail-closed model artifact loading for Signals V4."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.services.signals_v4.event_model import EVENT_FEATURES
from app.services.signals_v4.events import validate_live_features
from app.services.signals_v4.promotion import evaluate_promotion

HORIZON_SESSIONS = 20


class ArtifactRejected(ValueError):
    """Raised when a model artifact cannot be trusted by a scoring job."""


def validate_artifact_manifest(manifest: dict[str, Any], *, actual_sha256: str) -> None:
    """Validate promotion metadata without touching the model payload."""
    if manifest.get("horizon_sessions") != HORIZON_SESSIONS:
        raise ArtifactRejected("WRONG_HORIZON")
    feature_names = tuple(manifest.get("feature_names", ()))
    if not feature_names or not set(feature_names).issubset(EVENT_FEATURES):
        raise ArtifactRejected("UNAPPROVED_FEATURES")
    try:
        validate_live_features(dict.fromkeys(feature_names))
    except ValueError as exc:
        raise ArtifactRejected("REALIZED_FIELD_IN_FEATURES") from exc
    decision = evaluate_promotion(manifest.get("promotion", manifest))
    if not decision.allowed or manifest.get("status") != "PROMOTED":
        raise ArtifactRejected("MODEL_NOT_PROMOTED")
    expected_hash = str(manifest.get("artifact_sha256", ""))
    if not expected_hash or actual_sha256 != expected_hash:
        raise ArtifactRejected("ARTIFACT_HASH_MISMATCH")


def load_promoted_artifact(path: str | Path) -> tuple[Any, dict[str, Any]]:
    """Load an artifact only after validating its immutable promotion manifest."""
    artifact = Path(path)
    manifest_path = artifact.with_suffix(artifact.suffix + ".manifest.json")
    if not artifact.is_file() or not manifest_path.is_file():
        raise ArtifactRejected("MODEL_NOT_PROMOTED")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactRejected("INVALID_MODEL_MANIFEST") from exc
    validate_artifact_manifest(manifest, actual_sha256=_sha256(artifact))
    import joblib
    try:
        model = joblib.load(artifact)
    except Exception as exc:
        raise ArtifactRejected("INVALID_MODEL_ARTIFACT") from exc
    return model, manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()