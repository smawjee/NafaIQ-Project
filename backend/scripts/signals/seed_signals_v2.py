#!/usr/bin/env python
"""Refresh persisted Signals V2 rows for frontend use."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed persisted Signals V2 rows")
    parser.add_argument("--horizon", default="20D", choices=("5D", "20D", "60D"))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    result = asyncio.run(_run(args.horizon, args.limit, args.force_refresh))
    print(json.dumps(result, indent=2, default=str))
    return 0


async def _run(horizon: str, limit: int, force_refresh: bool) -> dict[str, object]:
    import app.services.signals_v2.engine as engine

    if force_refresh:
        engine._SIGNAL_TTL_SECONDS = 0
    batch = await engine.batch_signals(limit, horizon)
    board = await engine.leaderboard(horizon, min(limit, 10))
    return {
        "horizon": horizon,
        "requested_limit": limit,
        "batch_count": batch.get("count"),
        "leaderboard_count": board.get("count"),
        "top": [
            {
                "symbol": item.get("symbol"),
                "signal": item.get("signal"),
                "confidence": item.get("confidence"),
                "freshness": item.get("freshness"),
                "ml_signal": item.get("ml_signal"),
            }
            for item in (board.get("signals") or [])[:5]
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
