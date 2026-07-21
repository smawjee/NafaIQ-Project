#!/usr/bin/env python
"""Build reusable Signals V2 feature-store datasets."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(SCRIPT_DIR))

from app.services.signals_v2.training import HORIZON_DAYS, build_dataset, group_rows, map_rows, save_dataset
from train_signals_v2 import _client, _dataset_kwargs, _select_all, _select_ohlcv, _select_where


def main() -> int:
    load_dotenv(ROOT / ".env")
    client = _client()
    dataset_kwargs = _dataset_kwargs()
    out_dir = Path(os.getenv("SIGNALS_V2_FEATURE_STORE_DIR", str(ROOT / "artifacts" / "signals" / "feature_store")))
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading Supabase data for feature store...", file=sys.stderr, flush=True)
    ohlcv = _select_ohlcv(client, max_rows_per_symbol=dataset_kwargs["max_rows_per_symbol"])
    fundamentals = _select_all(client, "psx_fundamentals", "*", order_by="symbol")
    profiles = _select_all(client, "psx_profile", "*", order_by="symbol")
    kse_rows = _select_where(
        client,
        "psx_index_eod",
        "date,close",
        order_by="date",
        filters=[("code", "eq", "KSE100")],
    )

    histories = group_rows(ohlcv)
    fundamentals_map = map_rows(fundamentals)
    profiles_map = map_rows(profiles)
    manifest: dict[str, object] = {
        "feature_store_version": "signals-v2.1",
        "dataset_kwargs": dataset_kwargs,
        "horizons": {},
    }
    for horizon in HORIZON_DAYS:
        print(f"Building {horizon} feature store...", file=sys.stderr, flush=True)
        dataset = build_dataset(
            histories=histories,
            fundamentals=fundamentals_map,
            profiles=profiles_map,
            kse_rows=kse_rows,
            horizon=horizon,
            **dataset_kwargs,
        )
        path = out_dir / f"signals_v2_{horizon.lower()}.npz"
        save_dataset(dataset, str(path))
        manifest["horizons"][horizon] = {  # type: ignore[index]
            "path": str(path),
            "samples": int(len(dataset.y)),
            "features": int(dataset.X.shape[1]) if dataset.X.ndim == 2 else 0,
        }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest_path": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
