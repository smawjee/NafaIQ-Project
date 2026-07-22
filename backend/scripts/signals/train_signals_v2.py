#!/usr/bin/env python
"""Supabase data-access helpers shared by the Signals pipeline scripts.

The V2 absolute-classifier training that used to live here was retired after its
shadow evaluation was blocked (negative excess return, all promotion gates failed).
Signals V3.1 (see docs/superpowers/plans/2026-07-22-signals-v3.1-ranker.md) trains
via scripts/signals/train_ranker_v3.py and imports these helpers.
"""
from __future__ import annotations

import os
import sys

from supabase import create_client


def _client():
    url = os.getenv("PSX_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = (
        os.getenv("PSX_SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SECRET_KEY")
    )
    if not url or not key:
        raise RuntimeError("Missing Supabase env for Signals scripts")
    return create_client(url, key)


def _dataset_kwargs() -> dict[str, int]:
    return {
        "max_rows_per_symbol": int(os.getenv("SIGNALS_V2_MAX_ROWS_PER_SYMBOL", "420")),
        "sample_stride": int(os.getenv("SIGNALS_V2_SAMPLE_STRIDE", "20")),
    }


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
