"""Versioned feature-store manifests: refuse legacy/leaky caches by construction."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.services.signals_v2.training import Dataset, load_dataset

# v3.2: features/labels computed on corporate-action-adjusted closes
# (adjustments.py); v3.1 stores built on raw closes are refused by version gate.
FEATURE_VERSION = "v3.2"


def dataset_hash(X: np.ndarray, feature_names: list[str]) -> str:
    h = hashlib.sha256()
    h.update(str(X.shape).encode())
    h.update("|".join(feature_names).encode())
    checksum = float(np.nansum(np.round(np.nan_to_num(X, nan=0.0), 6)))
    h.update(f"{checksum:.6f}".encode())
    return h.hexdigest()[:16]


def _manifest_path(npz_path: str) -> Path:
    return Path(str(npz_path) + ".manifest.json")


def _now_iso() -> str:
    # scripts pass real time; tests tolerate a fixed stamp
    try:
        return datetime.now(timezone.utc).isoformat()
    except Exception:
        return "1970-01-01T00:00:00+00:00"


def write_manifest(npz_path: str, *, feature_names: list[str], X: np.ndarray,
                   pit_safe: bool, min_history: int, corp_action_audit_version: str) -> dict:
    manifest = {
        "feature_version": FEATURE_VERSION,
        "feature_names": list(feature_names),
        "dataset_hash": dataset_hash(X, feature_names),
        "created_at": _now_iso(),
        "pit_safe": bool(pit_safe),
        "min_history": int(min_history),
        "corporate_action_audit_version": corp_action_audit_version,
    }
    _manifest_path(npz_path).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_verified_store(npz_path: str, *, require_feature_version: str = FEATURE_VERSION) -> tuple[Dataset, dict]:
    mpath = _manifest_path(npz_path)
    if not mpath.exists():
        raise ValueError(f"feature store {npz_path} has no manifest — refusing (possibly legacy/leaky)")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    if manifest.get("feature_version") != require_feature_version:
        raise ValueError(f"feature store {npz_path} version {manifest.get('feature_version')} "
                         f"!= required {require_feature_version}")
    if not manifest.get("pit_safe", False):
        raise ValueError(f"feature store {npz_path} is not marked pit_safe — refusing")
    ds = load_dataset(npz_path)
    if dataset_hash(ds.X, ds.feature_names) != manifest.get("dataset_hash"):
        raise ValueError(f"feature store {npz_path} hash mismatch — store/manifest inconsistent")
    return ds, manifest
