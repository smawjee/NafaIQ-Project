#!/usr/bin/env python
"""Backtest Signals V2 ML candidates with walk-forward validation."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from app.services.signals_v2.training import (
    HORIZON_DAYS,
    build_dataset,
    group_rows,
    load_dataset,
    map_rows,
    save_dataset,
    train_and_select,
)


def main() -> int:
    load_dotenv(ROOT / ".env")
    client = _client()
    dataset_kwargs = _dataset_kwargs()
    print("Loading Supabase backtest data...", file=sys.stderr, flush=True)
    ohlcv = _select_ohlcv(client, max_rows_per_symbol=dataset_kwargs["max_rows_per_symbol"])
    print(f"Loaded psx_ohlcv rows: {len(ohlcv)}", file=sys.stderr, flush=True)
    fundamentals = _select_all(client, "psx_fundamentals", "*", order_by="symbol")
    print(f"Loaded fundamentals rows: {len(fundamentals)}", file=sys.stderr, flush=True)
    profiles = _select_all(client, "psx_profile", "*", order_by="symbol")
    print(f"Loaded profile rows: {len(profiles)}", file=sys.stderr, flush=True)
    kse_rows = _select_where(client, "psx_index_eod", "date,close", order_by="date", filters=[("code", "eq", "KSE100")])
    print(f"Loaded KSE-100 benchmark rows: {len(kse_rows)}", file=sys.stderr, flush=True)

    histories = group_rows(ohlcv)
    fundamentals_map = map_rows(fundamentals)
    profiles_map = map_rows(profiles)
    summary: dict[str, object] = {"status": "completed", "horizons": {}}
    feature_store_dir = _feature_store_dir()
    for horizon in HORIZON_DAYS:
        print(f"Building {horizon} backtest dataset...", file=sys.stderr, flush=True)
        dataset_path = feature_store_dir / f"signals_v2_{horizon.lower()}.npz" if feature_store_dir else None
        if dataset_path and dataset_path.exists():
            dataset = load_dataset(str(dataset_path))
            print(f"Loaded cached {horizon} feature store: {dataset_path}", file=sys.stderr, flush=True)
        else:
            dataset = build_dataset(
                histories=histories,
                fundamentals=fundamentals_map,
                profiles=profiles_map,
                kse_rows=kse_rows,
                horizon=horizon,
                **dataset_kwargs,
            )
            if dataset_path:
                dataset_path.parent.mkdir(parents=True, exist_ok=True)
                save_dataset(dataset, str(dataset_path))
                print(f"Saved {horizon} feature store: {dataset_path}", file=sys.stderr, flush=True)
        print(f"{horizon} samples: {len(dataset.y)}", file=sys.stderr, flush=True)
        if len(dataset.y) < 200:
            summary["horizons"][horizon] = {"status": "skipped", "samples": int(len(dataset.y))}  # type: ignore[index]
            continue
        print(f"Training/evaluating {horizon} candidates...", file=sys.stderr, flush=True)
        result = train_and_select(dataset)
        summary["horizons"][horizon] = {"selected_model": result.name, **result.metrics}  # type: ignore[index]
        print(f"Selected {horizon}: {result.name}", file=sys.stderr, flush=True)

    out_dir = ROOT / "artifacts" / "signals" / "backtests" / datetime.now(timezone.utc).date().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary_path": str(out_dir / "summary.json")}, indent=2))
    return 0


def _client():
    url = os.getenv("PSX_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = (
        os.getenv("PSX_SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SECRET_KEY")
    )
    if not url or not key:
        raise RuntimeError("Missing Supabase env for Signals V2 backtest")
    return create_client(url, key)


def _dataset_kwargs() -> dict[str, int]:
    return {
        "max_rows_per_symbol": int(os.getenv("SIGNALS_V2_MAX_ROWS_PER_SYMBOL", "420")),
        "sample_stride": int(os.getenv("SIGNALS_V2_SAMPLE_STRIDE", "20")),
    }


def _feature_store_dir() -> Path | None:
    value = os.getenv("SIGNALS_V2_FEATURE_STORE_DIR")
    if not value:
        return None
    return Path(value)


def _select_ohlcv(client, *, max_rows_per_symbol: int) -> list[dict]:
    symbols = _select_symbols(client)
    rows: list[dict] = []
    for idx, symbol in enumerate(symbols, start=1):
        res = (
            client.table("psx_ohlcv")
            .select("symbol,date,open,high,low,close,volume")
            .eq("symbol", symbol)
            .order("date", desc=True)
            .limit(max_rows_per_symbol)
            .execute()
        )
        rows.extend(reversed(res.data or []))
        if idx % 50 == 0:
            print(f"Loaded OHLCV for {idx}/{len(symbols)} symbols", file=sys.stderr, flush=True)
    return rows


def _select_symbols(client) -> list[str]:
    rows = _select_all(client, "psx_market_snapshot", "symbol", order_by="symbol")
    symbols = sorted({str(row.get("symbol")).upper() for row in rows if row.get("symbol")})
    if symbols:
        return symbols
    rows = _select_all(client, "psx_profile", "symbol", order_by="symbol")
    return sorted({str(row.get("symbol")).upper() for row in rows if row.get("symbol")})


def _select_all(client, table: str, columns: str, *, order_by: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    page_size = 1000
    while True:
        res = client.table(table).select(columns).order(order_by).range(offset, offset + page_size - 1).execute()
        page = res.data or []
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size


def _select_where(client, table: str, columns: str, *, order_by: str, filters: list[tuple[str, str, str]]) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    page_size = 1000
    while True:
        query = client.table(table).select(columns)
        for column, op, value in filters:
            query = getattr(query, op)(column, value)
        res = query.order(order_by).range(offset, offset + page_size - 1).execute()
        page = res.data or []
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size


if __name__ == "__main__":
    raise SystemExit(main())
