#!/usr/bin/env python
"""T20 — insert-only outcome maturity evaluation + monitoring report.

For each psx_signals_v3_daily row whose horizon has elapsed and that lacks an
outcome row, computes realized/benchmark/excess returns with the SAME execution
convention as training (entry = first valid close after as_of within the entry
delay window, exit = horizon sessions after entry) and INSERTS a
psx_signal_outcomes row. Signal rows are never touched. Emits rolling metrics
to artifacts/signals/monitoring_report.json.
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.signals_v2.constants import (
    MAX_ENTRY_DELAY_TRADING_DAYS,
    ROUND_TRIP_COST,
)
from app.services.signals_v2.training import HORIZON_DAYS, _parse_date

EVALUATION_VERSION = "v3.1-outcome-1"
LARGE_LOSS_NET = -0.02


def mature_outcome(bars: list[dict], kse_by_date: dict[str, float], *,
                   as_of: date, horizon_days: int, max_entry_delay: int) -> dict | None:
    """Realized outcome for one signal, or None if the horizon has not elapsed.

    bars: ordered [{date, close}] for the symbol from as_of onward (may include earlier).
    kse_by_date: iso date -> KSE100 close.
    """
    ordered = sorted(bars, key=lambda r: str(r.get("date")))
    dates = [_parse_date(r.get("date")) for r in ordered]
    closes = [float(r.get("close") or 0) for r in ordered]

    # entry: first valid close strictly after as_of, within the delay window
    entry_i = None
    seen_after = 0
    for i, d in enumerate(dates):
        if d <= as_of:
            continue
        seen_after += 1
        if closes[i] > 0:
            entry_i = i
            break
        if seen_after > max_entry_delay:
            break
    if entry_i is None:
        return None
    exit_i = entry_i + horizon_days
    if exit_i >= len(ordered) or closes[exit_i] <= 0:
        return None                              # not matured yet

    entry_d, exit_d = dates[entry_i], dates[exit_i]
    realized = closes[exit_i] / closes[entry_i] - 1
    k0 = kse_by_date.get(entry_d.isoformat())
    k1 = kse_by_date.get(exit_d.isoformat())
    benchmark = (k1 / k0 - 1) if k0 and k1 and k0 > 0 else 0.0
    net = realized - ROUND_TRIP_COST
    return {
        "maturity_status": "MATURED",
        "realized_return": round(float(realized), 6),
        "benchmark_return": round(float(benchmark), 6),
        "excess_return": round(float(realized - benchmark), 6),
        "large_loss": bool(net < LARGE_LOSS_NET),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_version": EVALUATION_VERSION,
    }


async def _run() -> dict:
    from app.repositories import signals_v3_repo
    from train_signals_v2 import _client, _select_where

    client = _client()
    pending = await signals_v3_repo.signals_missing_outcomes(limit=1000)
    kse_rows = _select_where(client, "psx_index_eod", "date,close", order_by="date",
                             filters=[("code", "eq", "KSE100")])
    kse_by_date = {str(r.get("date"))[:10]: float(r.get("close") or 0) for r in kse_rows}

    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for row in pending:
        by_symbol[str(row["symbol"]).upper()].append(row)

    inserted, immature = 0, 0
    matured_rows: list[tuple[dict, dict]] = []
    for sym, signal_rows in by_symbol.items():
        res = (client.table("psx_ohlcv").select("date,close").eq("symbol", sym)
               .order("date", desc=True).limit(400).execute())
        bars = list(reversed(res.data or []))
        for row in signal_rows:
            horizon_days = HORIZON_DAYS.get(str(row["horizon"]), 20)
            out = mature_outcome(bars, kse_by_date, as_of=_parse_date(row["as_of"]),
                                 horizon_days=horizon_days,
                                 max_entry_delay=MAX_ENTRY_DELAY_TRADING_DAYS)
            if out is None:
                immature += 1
                continue
            await signals_v3_repo.insert_outcome(row["id"], **out)
            inserted += 1
            matured_rows.append((row, out))

    # rolling monitoring metrics over freshly matured outcomes
    buys = [(r, o) for r, o in matured_rows if r.get("signal") in ("BUY", "STRONG_BUY")]
    buy_net = np.asarray([o["realized_return"] - ROUND_TRIP_COST for _, o in buys])
    signal_dist = Counter(r.get("signal") for r, _ in matured_rows)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_version": EVALUATION_VERSION,
        "outcomes_inserted": inserted,
        "still_pending": immature,
        "matured_signal_distribution": dict(signal_dist),
        "buy_metrics": {
            "n": int(len(buys)),
            "hit_rate": round(float(np.mean(buy_net > 0)), 4) if len(buy_net) else None,
            "avg_excess": round(float(np.mean([o["excess_return"] for _, o in buys])), 4) if buys else None,
            "large_loss_rate": round(float(np.mean([o["large_loss"] for _, o in buys])), 4) if buys else None,
        },
    }
    out_path = ROOT / "artifacts" / "signals" / "monitoring_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    return report


def main() -> int:
    load_dotenv(ROOT / ".env")
    report = asyncio.run(_run())
    print(json.dumps({"outcomes_inserted": report["outcomes_inserted"],
                      "still_pending": report["still_pending"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
