#!/usr/bin/env python
"""Gated experiment — do foreign equity flows (SCRA) predict KSE-100 forward returns?

The emerging-market literature's classic edge: sustained foreign buying/selling
leads index moves. We now hold 19 years of official daily SCRA equity flows;
KSE-100 EOD history in our DB starts 2021-07 -> ~5y overlap. Walk-forward
evaluation: rolling flow features vs forward index returns, expanding-window
IC + tercile spreads. Report-only; GREEN justifies a flow-regime feature plan.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

FWD = 20                 # sessions ahead
MIN_TRAIN = 252          # expanding-window minimum before scoring OOS
FEATURES = {"flow_5d": 5, "flow_20d": 20, "flow_60d": 60}


def build_panel(flow_by_date: dict[str, float], kse: list[tuple[str, float]]) -> dict:
    """Align flows onto KSE trading days; rolling sums; forward returns."""
    days = [(d, c) for d, c in kse if c > 0]
    dates = [d for d, _ in days]
    close = np.asarray([c for _, c in days], dtype=np.float64)
    flow = np.asarray([flow_by_date.get(d, 0.0) for d in dates], dtype=np.float64)

    feats = {}
    for name, w in FEATURES.items():
        s = np.convolve(flow, np.ones(w), mode="full")[: len(flow)]
        s[:w - 1] = np.nan
        feats[name] = s
    fwd = np.full(len(close), np.nan)
    fwd[:-FWD] = close[FWD:] / close[:-FWD] - 1
    return {"dates": dates, "close": close, "flow": flow, "features": feats, "fwd": fwd}


def walk_forward_ic(feature: np.ndarray, fwd: np.ndarray, *, min_train: int = MIN_TRAIN,
                    step: int = 20) -> dict:
    """Expanding-window OOS rank-IC: at each step, score the NEXT block only."""
    n = len(feature)
    oos_f, oos_y = [], []
    blocks = []
    for start in range(min_train, n - FWD, step):
        end = min(start + step, n - FWD)
        f = feature[start:end]
        y = fwd[start:end]
        m = np.isfinite(f) & np.isfinite(y)
        if m.sum() == 0:
            continue
        oos_f.extend(f[m]); oos_y.extend(y[m])
        if m.sum() >= 5:
            ic = spearmanr(f[m], y[m]).statistic
            if np.isfinite(ic):
                blocks.append(float(ic))
    if len(oos_f) < 100:
        return {"status": "insufficient_oos", "n": len(oos_f)}
    oos_f, oos_y = np.asarray(oos_f), np.asarray(oos_y)
    ic = float(spearmanr(oos_f, oos_y).statistic)
    # tercile spread on OOS points
    terc = np.quantile(oos_f, [1 / 3, 2 / 3])
    lo = oos_y[oos_f <= terc[0]]
    hi = oos_y[oos_f >= terc[1]]
    return {
        "oos_rank_ic": round(ic, 4),
        "blocks_positive_frac": round(float(np.mean(np.asarray(blocks) > 0)), 4) if blocks else 0.0,
        "n_blocks": len(blocks),
        "tercile_high_mean_fwd20": round(float(np.mean(hi)), 4),
        "tercile_low_mean_fwd20": round(float(np.mean(lo)), 4),
        "tercile_spread": round(float(np.mean(hi) - np.mean(lo)), 4),
        "n_oos": int(len(oos_f)),
    }


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from train_signals_v2 import _client, _select_where

    client = _client()
    kse_rows = _select_where(client, "psx_index_eod", "date,close", order_by="date",
                             filters=[("code", "eq", "KSE100")])
    kse = [(str(r["date"])[:10], float(r.get("close") or 0)) for r in kse_rows]

    flows = _select_where(client, "psx_fipi_daily", "trade_date,net_value_usd",
                          order_by="trade_date",
                          filters=[("scope", "eq", "MARKET"), ("client_type", "eq", "SCRA")])
    flow_by_date = {str(r["trade_date"])[:10]: float(r.get("net_value_usd") or 0) for r in flows}

    panel = build_panel(flow_by_date, kse)
    results = {name: walk_forward_ic(panel["features"][name], panel["fwd"])
               for name in FEATURES}

    primary = results.get("flow_20d") or {}
    if primary.get("status") == "insufficient_oos":
        verdict = "INCONCLUSIVE"
    elif (primary.get("oos_rank_ic", 0) > 0.05
          and primary.get("blocks_positive_frac", 0) > 0.5
          and primary.get("tercile_spread", 0) > 0):
        verdict = "GREEN"
    else:
        verdict = "RED"

    report = {"results": results, "verdict": verdict,
              "overlap_days": int(np.isfinite(panel["fwd"]).sum()),
              "flow_days_total": len(flow_by_date),
              "kse_range": [kse[0][0] if kse else None, kse[-1][0] if kse else None],
              "signal": "SCRA foreign equity flow (rolling sums) vs KSE-100 fwd 20d"}
    out = ROOT / "artifacts" / "signals" / "flow_timing_experiment.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "flow_20d": primary,
                      "report": str(out)}, indent=2))
    return {"GREEN": 0, "RED": 2, "INCONCLUSIVE": 3}[verdict]


if __name__ == "__main__":
    raise SystemExit(main())
