#!/usr/bin/env python
"""Build V3.1 feature-store datasets with PIT-safe features and verifiable manifests.

Stores exclude fundamentals entirely (psx_fundamentals has no publication date —
using it historically leaks future information; see the T0 audit) and preserve
missing values as NaN for GBDT-native handling.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(SCRIPT_DIR))

from app.services.signals_v2.constants import MIN_REQUIRED_BARS
from app.services.signals_v2.feature_store import FEATURE_VERSION, write_manifest
from app.services.signals_v2.training import (
    HORIZON_DAYS,
    SIGNAL_FEATURES_V3,
    build_dataset,
    group_rows,
    map_rows,
    save_dataset,
)
from train_signals_v2 import _client, _dataset_kwargs, _select_all, _select_ohlcv_adjusted, _select_where


def _corp_action_audit_version() -> str:
    report = ROOT / "artifacts" / "signals" / "data_integrity_report.json"
    if report.exists():
        return datetime.fromtimestamp(report.stat().st_mtime, tz=timezone.utc).date().isoformat()
    return "unaudited"


def main() -> int:
    load_dotenv(ROOT / ".env")
    client = _client()
    dataset_kwargs = _dataset_kwargs()
    out_dir = Path(os.getenv("SIGNALS_V2_FEATURE_STORE_DIR", str(ROOT / "artifacts" / "signals" / "feature_store")))
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading Supabase data for feature store...", file=sys.stderr, flush=True)
    adjustment_mode = os.getenv("SIGNALS_V2_ADJUSTMENT_MODE", "price")
    ohlcv = _select_ohlcv_adjusted(
        client, max_rows_per_symbol=dataset_kwargs["max_rows_per_symbol"], mode=adjustment_mode
    )
    profiles = _select_all(client, "psx_profile", "*", order_by="symbol")
    kse_rows = _select_where(
        client,
        "psx_index_eod",
        "date,close",
        order_by="date",
        filters=[("code", "eq", "KSE100")],
    )

    histories = group_rows(ohlcv)
    profiles_map = map_rows(profiles)
    audit_version = _corp_action_audit_version()
    store_manifest: dict[str, object] = {
        "feature_store_version": FEATURE_VERSION,
        "dataset_kwargs": dataset_kwargs,
        "price_adjustment_mode": adjustment_mode,
        "horizons": {},
    }
    for horizon in HORIZON_DAYS:
        print(f"Building {horizon} V3 feature store...", file=sys.stderr, flush=True)
        dataset = build_dataset(
            histories=histories,
            fundamentals={},  # PIT-unsafe: excluded from V3 stores by construction
            profiles=profiles_map,
            kse_rows=kse_rows,
            horizon=horizon,
            min_history=MIN_REQUIRED_BARS,
            feature_names=SIGNAL_FEATURES_V3,
            preserve_nan=True,
            max_rows_per_symbol=dataset_kwargs["max_rows_per_symbol"],
            sample_stride=dataset_kwargs["sample_stride"],
        )
        path = out_dir / f"signals_v2_{horizon.lower()}.npz"
        save_dataset(dataset, str(path))
        write_manifest(
            str(path),
            feature_names=dataset.feature_names,
            X=dataset.X,
            pit_safe=True,
            min_history=MIN_REQUIRED_BARS,
            corp_action_audit_version=audit_version,
        )
        store_manifest["horizons"][horizon] = {  # type: ignore[index]
            "path": str(path),
            "samples": int(len(dataset.y)),
            "features": int(dataset.X.shape[1]) if dataset.X.ndim == 2 else 0,
        }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(store_manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest_path": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
