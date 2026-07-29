#!/usr/bin/env python
"""Smoke-test Signals V2 against Supabase and local ML artifacts."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test Signals V2")
    parser.add_argument("--symbol", default="HBL")
    parser.add_argument("--horizon", default="20D")
    parser.add_argument("--skip-generation", action="store_true")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    client = _client()
    counts = _table_counts(client)
    result: dict[str, object] = {"tables": counts}
    if not args.skip_generation:
        result["signal"] = asyncio.run(_signal(args.symbol, args.horizon))
    print(json.dumps(result, indent=2, default=str))
    return 0


def _client():
    url = os.getenv("PSX_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = (
        os.getenv("PSX_SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SECRET_KEY")
    )
    if not url or not key:
        raise RuntimeError("Missing Supabase env for Signals V2 smoke test")
    return create_client(url, key)


def _table_counts(client) -> dict[str, int | None]:
    tables = (
        "psx_ohlcv",
        "psx_market_snapshot",
        "psx_fundamentals",
        "psx_profile",
        "psx_index_eod",
        "psx_signals_v2",
    )
    out: dict[str, int | None] = {}
    for table in tables:
        res = client.table(table).select("*", count="exact").limit(1).execute()
        out[table] = res.count
    return out


async def _signal(symbol: str, horizon: str) -> dict[str, object]:
    import app.services.signals_v2.engine as engine

    engine._SIGNAL_TTL_SECONDS = 0
    signal = await engine.get_signal(symbol, horizon)
    keep = (
        "symbol",
        "horizon",
        "signal",
        "confidence",
        "technical_signal",
        "technical_score",
        "ml_signal",
        "ml_confidence",
        "risk_level",
        "regime",
        "freshness",
        "model_version",
        "engine_version",
        "predicted_at",
    )
    return {key: signal.get(key) for key in keep}


if __name__ == "__main__":
    raise SystemExit(main())
