#!/usr/bin/env python
"""Gated experiment — is PSX loser-reversal tradeable after costs and liquidity filters?

The momentum experiment (2026-07-23) found monotonicity -0.9: past 12-1 LOSERS
beat past winners. But that raw spread may live in untradeable illiquid names
and legacy-store execution assumptions. This experiment re-tests it honestly:
liquid universe only (top-200 by turnover, floor Rs 5M), execution-aligned
dataset (T+1 close entries via build_ranking_dataset), corp-action exclusions,
and a simulated top-10 loser portfolio after ROUND_TRIP_COST.
Report only — a GREEN justifies a V3.4 shadow-ranker plan, not a ship.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment_long_momentum import momentum_quintile_report
from train_signals_v2 import _client, _select_all, _select_ohlcv_adjusted, _select_where

from app.services.signals_v2.constants import PORTFOLIO_REBALANCE_DAYS
from app.services.signals_v2.portfolio_sim import simulate_topk
from app.services.signals_v2.ranking import build_ranking_dataset
from app.services.signals_v2.training import SIGNAL_FEATURES_V3, group_rows, map_rows

TOP_N = 200
TURNOVER_FLOOR = 5_000_000       # Rs 5M median 20-bar turnover
MIN_DATES = 30
PORTFOLIO_K = 10


def liquid_universe(histories: dict[str, list[dict]], *, top_n: int = TOP_N,
                    turnover_floor: float = TURNOVER_FLOOR) -> list[str]:
    turnover: dict[str, float] = {}
    for sym, rows in histories.items():
        recent = sorted(rows, key=lambda r: str(r.get("date")))[-20:]
        if len(recent) < 20:
            continue
        med = float(np.median([float(r.get("close") or 0) * float(r.get("volume") or 0)
                               for r in recent]))
        if med >= turnover_floor:
            turnover[sym] = med
    return sorted(turnover, key=turnover.get, reverse=True)[:top_n]


def daily_top_picks(entry_dates: list[date], symbols: list[str],
                    signal: np.ndarray, *, k: int = PORTFOLIO_K) -> dict[date, list[str]]:
    by_date: dict[date, list[int]] = defaultdict(list)
    for i, d in enumerate(entry_dates):
        by_date[d].append(i)
    out: dict[date, list[str]] = {}
    for d, idxs in by_date.items():
        order = sorted(idxs, key=lambda i: -float(signal[i]))[:k]
        out[d] = [symbols[i] for i in order]
    return out


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    audit = ROOT / "artifacts" / "signals" / "data_integrity_report.json"
    events = {}
    if audit.exists():
        events = json.loads(audit.read_text(encoding="utf-8"))["corp_action_events"]["by_symbol"]

    client = _client()
    ohlcv = _select_ohlcv_adjusted(client, max_rows_per_symbol=1300, mode="price")
    profiles = map_rows(_select_all(client, "psx_profile", "*", order_by="symbol"))
    kse_rows = _select_where(client, "psx_index_eod", "date,close", order_by="date",
                             filters=[("code", "eq", "KSE100")])
    histories = group_rows(ohlcv)
    universe = liquid_universe(histories)
    histories = {s: histories[s] for s in universe}
    print(json.dumps({"universe": len(universe)}), file=sys.stderr, flush=True)

    results: dict = {}
    for horizon in ("20D", "60D"):
        ds = build_ranking_dataset(histories=histories, fundamentals={}, profiles=profiles,
                                   kse_rows=kse_rows, horizon=horizon,
                                   corp_action_events=events)
        if len(ds.y) == 0:
            results[horizon] = {"status": "empty_dataset"}
            continue
        col = SIGNAL_FEATURES_V3.index("ret_240d_ex20")
        signal = -ds.X[:, col]                       # LOSERS ranked highest
        report = momentum_quintile_report(ds.feature_dates, ds.symbols, signal,
                                          ds.forward_returns, ds.benchmark_forward_returns)
        if report["n_dates"] < MIN_DATES:
            report["status"] = "insufficient_dates"

        # simulate a top-K biggest-losers portfolio on execution-aligned entries
        finite = np.isfinite(signal)
        picks = daily_top_picks([ds.entry_dates[i] for i in np.flatnonzero(finite)],
                                [ds.symbols[i] for i in np.flatnonzero(finite)],
                                signal[finite])
        prices = {}
        for sym, rows in histories.items():
            series = {}
            for r in sorted(rows, key=lambda x: str(x.get("date"))):
                series[date.fromisoformat(str(r.get("date"))[:10])] = float(r.get("close") or 0)
            prices[sym.upper()] = series
        kse = {date.fromisoformat(str(r.get("date"))[:10]): float(r.get("close") or 0)
               for r in kse_rows}
        if picks:
            start, end = min(picks), max(ds.exit_dates)
            kse = {d: v for d, v in kse.items() if start <= d <= end}
        sim = simulate_topk({d: [s.upper() for s in v] for d, v in picks.items()},
                            prices, kse, k=PORTFOLIO_K,
                            rebalance_days=PORTFOLIO_REBALANCE_DAYS[horizon])
        report["sim_net_return"] = sim["net_return"]
        report["sim_excess_return"] = sim["excess_return"]
        report["sim_max_drawdown"] = sim["max_drawdown"]
        report["sim_sharpe"] = sim["sharpe"]
        results[horizon] = report

    primary = results.get("60D") or {}
    if primary.get("status") in ("empty_dataset", "insufficient_dates"):
        verdict = "INCONCLUSIVE"
    elif (primary.get("q5_excess_after_cost", 0) > 0
          and primary.get("monotonicity", 0) > 0.5
          and primary.get("sim_excess_return", 0) > 0):
        verdict = "GREEN"
    else:
        verdict = "RED"

    out = ROOT / "artifacts" / "signals" / "reversal_experiment.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"results": results, "verdict": verdict,
                               "signal": "-ret_240d_ex20 (12-1 losers)",
                               "universe": len(universe)},
                              indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict,
                      "60D_losers_q5_after_cost": primary.get("q5_excess_after_cost"),
                      "60D_sim_excess": primary.get("sim_excess_return"),
                      "report": str(out)}, indent=2))
    return {"GREEN": 0, "RED": 2, "INCONCLUSIVE": 3}[verdict]


if __name__ == "__main__":
    raise SystemExit(main())
