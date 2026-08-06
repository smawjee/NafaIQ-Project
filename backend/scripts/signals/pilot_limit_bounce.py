"""Arm B' — limit-day bounce event study (corrected re-run, 2026-08-05).

The original Arm B verdict (AMBER) was invalidated: its "ex-date strip" keyed
on `psx_corporate_actions.ann_date`, but price gaps sit at the ex-date — the
strip removed 0 events while 36 events on real ex-dates survived (see
MEASUREMENT INVALIDATION in RESEARCH_LOG.md, finding D1). This is the
pre-registered corrected re-run (PRE-REGISTRATION — A'/B'/C' section).

Tests whether a limit-down session (close ≤ −7.5% B75 / ≤ −9.5% B95) that is
*not* a corporate-action ex-date is followed by positive next-session-
executable forward returns net of true cost.

Fixes vs the invalidated run:

* **Ex-date strip on the REAL ex-date** (D1): an event is stripped when the
  symbol has an attributed ex_date within ±2 SESSIONS of the event date. The
  attributed set merges `psx_corporate_actions.ex_date` (notice-PDF-parsed,
  2016+) and `psx_dividends.ex_date` (payout page, 2025+); the measured gap
  band sits at stored_ex_date −2/−1 sessions, so ±2 sessions covers it.
  Events with no attributed ex_date near them are kept, and their label
  windows are quarantined by `clean_labels_mask` instead. Strip coverage is
  reported per band.
* **Total-return labels** (D3): outcomes and the benchmark use
  `forward_return_total`, so attributed dividends do not depress labels.
* **Label guard** (D2): label cells must satisfy `clean_labels_mask(h)`.
* **Power rule** (D4): a band with < 30 holdout events or < 10 holdout dates
  is recorded CANNOT CONCLUDE, never RED.

Everything else unchanged: next-session-close entry, non-overlap within 10
sessions, date-clustered t, explore 2022-2024 / holdout 2025-2026, true
round-trip cost.

Writes a JSON report to artifacts/signals/pilot_limit_bounce_v2.json.
No DB writes.

    python scripts/signals/pilot_limit_bounce.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from panel import ARTIFACT_DIR, Panel, load_panel  # noqa: E402
from pilot_reversal import cost_matrix  # noqa: E402

from app.services.signals.costs import CostParams  # noqa: E402

BAND_75 = -0.075
BAND_95 = -0.095
HORIZONS = (5, 11, 21, 41)
PRIMARY_HORIZONS = (21, 41)
NO_OVERLAP_SESSIONS = 10
EXPLORE_END = pd.Timestamp("2025-01-01")
STRIP_WINDOW_SESSIONS = 2
MIN_HOLDOUT_EVENTS = 30
MIN_HOLDOUT_DATES = 10


async def load_ex_dates() -> dict[str, list[np.datetime64]]:
    """symbol -> sorted attributed ex_dates, merging both audited sources."""
    from sqlalchemy import text

    from app.repositories.base import connect

    async with connect() as conn:
        ca = (await conn.execute(text(
            "SELECT symbol, ex_date FROM psx_corporate_actions "
            "WHERE ex_date IS NOT NULL"
        ))).mappings().all()
        div = (await conn.execute(text(
            "SELECT symbol, ex_date FROM psx_dividends "
            "WHERE payout_type = 'cash' AND ex_date IS NOT NULL"
        ))).mappings().all()
    merged: dict[str, set[np.datetime64]] = {}
    for r in list(ca) + list(div):
        sym = str(r["symbol"]).upper()
        merged.setdefault(sym, set()).add(np.datetime64(r["ex_date"]))
    return {sym: sorted(dates) for sym, dates in merged.items()}


def find_events(panel: Panel, cost: np.ndarray,
                ex_dates: dict[str, list[np.datetime64]]) -> tuple[dict[str, pd.DataFrame], dict[str, dict]]:
    """Per-band event tables plus strip-coverage stats.

    Returns (tables, coverage) where coverage[band] = {"candidates": n,
    "stripped": n, "kept": n, "stripped_frac": f}.
    """
    returns = panel.returns()
    investable = panel.investable_mask()
    n_dates = panel.shape[0]
    dates = panel.dates.values.astype("datetime64[ns]")
    # Session-index lookup per symbol: ex_date -> nearest session index.
    ex_index: dict[str, np.ndarray] = {}
    for sym, day_list in ex_dates.items():
        idx = [int(panel.dates.get_indexer([pd.Timestamp(d)])[0]) for d in day_list]
        idx = sorted(i for i in idx if 0 <= i < n_dates)
        ex_index[sym] = np.asarray(idx, dtype=np.int64)

    def near_ex_date(sym: str, i: int) -> bool:
        idx = ex_index.get(sym)
        if idx is None or len(idx) == 0:
            return False
        # nearest attributed ex-date within ±STRIP_WINDOW sessions of i
        pos = np.searchsorted(idx, i)
        for cand in (pos - 1, pos):
            if 0 <= cand < len(idx) and abs(int(idx[cand]) - i) <= STRIP_WINDOW_SESSIONS:
                return True
        return False

    out: dict[str, list[dict[str, Any]]] = {"B75": [], "B95": []}
    coverage: dict[str, dict[str, Any]] = {}
    for band, thresh in (("B75", BAND_75), ("B95", BAND_95)):
        rows = out[band]
        stats = {"candidates": 0, "stripped": 0, "kept": 0}
        for col in range(panel.shape[1]):
            sym = str(panel.symbols[col])
            last_kept = -NO_OVERLAP_SESSIONS
            for i in range(1, n_dates - 1):
                r = returns[i, col]
                if not np.isfinite(r) or r > thresh:
                    continue
                if not investable[i, col]:
                    continue
                stats["candidates"] += 1
                if near_ex_date(sym, i):
                    stats["stripped"] += 1
                    continue
                # Primary entry: next-session close (executable).
                entry = i + 1
                if not np.isfinite(panel.close[entry, col]):
                    continue
                if i - last_kept < NO_OVERLAP_SESSIONS:
                    continue
                last_kept = i
                stats["kept"] += 1
                rows.append({
                    "symbol": sym,
                    "event_date": dates[i],
                    "event_index": i,
                    "entry_index": entry,
                    "cost": float(cost[entry, col]),
                })
        stats["stripped_frac"] = round(stats["stripped"] / stats["candidates"], 4) \
            if stats["candidates"] else 0.0
        coverage[band] = stats
    return {k: pd.DataFrame(v) for k, v in out.items()}, coverage


def cluster_by_date(df: pd.DataFrame, panel: Panel,
                    market_fwd: dict[int, np.ndarray],
                    clean: dict[int, np.ndarray],
                    fwd_total: dict[int, np.ndarray]) -> dict[str, Any]:
    """One observation per event date; t-test across dates.

    ``market_fwd[h]`` holds the date-demeaned same-universe TOTAL forward
    return for horizon h (computed once, vectorised, in main);
    ``clean[h]`` is ``clean_labels_mask(h)`` — label cells with a >12% move
    in the window are dropped (D2); ``fwd_total[h]`` is the precomputed
    per-symbol total forward return matrix (computed once, NOT per event).
    """
    events = []
    for _, row in df.iterrows():
        e = int(row["entry_index"])
        sym = str(row["symbol"])
        col = int(row["col"])
        for h in HORIZONS:
            if e + h >= panel.shape[0]:
                continue
            if not clean[h][e, col]:
                continue
            stock = fwd_total[h][e, col]
            if not np.isfinite(stock):
                continue
            mkt = market_fwd[h][e]
            if not np.isfinite(mkt):
                continue
            events.append({
                "date": row["event_date"],
                "horizon": h,
                "gross_excess": float(stock - mkt),
                "cost": float(row["cost"]),
            })
    ev = pd.DataFrame(events)
    if ev.empty:
        return {"events": 0}

    out_rows = []
    for h in HORIZONS:
        sub = ev[ev["horizon"] == h]
        if sub.empty:
            continue
        per_date = sub.groupby("date")["gross_excess"].mean()
        n_dates = len(per_date)
        if n_dates < 2:
            continue
        gross = float(per_date.mean())
        se = float(per_date.std(ddof=1) / np.sqrt(n_dates))
        t_gross = gross / se if se > 0 else 0.0
        # Net: subtract each event's true cost once (round trip per trade).
        net_per_date = sub.groupby("date").apply(
            lambda g: float(np.mean(g["gross_excess"] - g["cost"])), include_groups=False)
        net = float(net_per_date.mean())
        se_net = float(net_per_date.std(ddof=1) / np.sqrt(n_dates))
        t_net = net / se_net if se_net > 0 else 0.0
        out_rows.append({
            "horizon": h,
            "events": int(len(sub)),
            "dates": n_dates,
            "gross_excess": round(gross, 6),
            "gross_clustered_t": round(t_gross, 3),
            "net_excess": round(net, 6),
            "net_clustered_t": round(t_net, 3),
            "mean_cost": round(float(sub["cost"].mean()), 6),
        })
    return {"events": int(len(ev)), "rows": out_rows}


def verdict(explore: dict, holdout: dict, band: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    ho_rows = {r["horizon"]: r for r in holdout.get("rows", [])}

    # Power rule (D4): with < MIN_HOLDOUT_EVENTS events or < MIN_HOLDOUT_DATES
    # dates, a null is not evidence of "no effect".
    if holdout.get("events", 0) < MIN_HOLDOUT_EVENTS or \
            max((r.get("dates", 0) for r in ho_rows.values()), default=0) < MIN_HOLDOUT_DATES:
        return "CANNOT CONCLUDE", [f"{band}: holdout sample too small "
                                   f"({holdout.get('events', 0)} events) to power the test"]

    best_net, best_h, best_t = None, None, None
    for h in PRIMARY_HORIZONS:
        r = ho_rows.get(h)
        if r is None:
            continue
        if best_net is None or r["net_excess"] > best_net:
            best_net, best_h, best_t = r["net_excess"], h, r["net_clustered_t"]

    if best_net is None:
        return "RED", [f"{band}: no holdout rows at primary horizons"]

    cost = ho_rows.get(best_h, {}).get("mean_cost", 0.0)
    exceeds = best_net > cost           # > one true round trip over benchmark
    if not exceeds:
        reasons.append(f"{band} {best_h}s net excess {best_net:.4f} not > one "
                       f"round trip ({cost:.4f})")
    if best_t is None or best_t <= 1.96:
        reasons.append(f"{band} {best_h}s clustered t {best_t} <= 1.96")

    gross_ok = any(r.get("gross_excess", 0) > 0 for r in ho_rows.values())
    if reasons and gross_ok:
        return "AMBER", reasons
    return ("GREEN", []) if not reasons else ("RED", reasons)


def main() -> None:
    print("=" * 78)
    print("Arm B' — limit-day bounce (corrected re-run, pre-registered 2026-08-05)")
    print("=" * 78)

    panel = load_panel()
    cost = cost_matrix(panel, CostParams())
    investable = panel.investable_mask()
    ex_dates = asyncio.run(load_ex_dates())
    print(f"  attributed ex-date strip set: "
          f"{sum(len(v) for v in ex_dates.values()):,} entries "
          f"({len(ex_dates)} symbols)")

    # Date-demeaned same-universe TOTAL forward return per horizon (benchmark).
    market_fwd: dict[int, np.ndarray] = {}
    for h in HORIZONS:
        fwd = panel.forward_return_total(h)
        mkt = np.full(panel.shape[0], np.nan)
        for i in range(panel.shape[0]):
            m = investable[i] & np.isfinite(fwd[i])
            if m.sum() >= 20:
                mkt[i] = float(np.mean(fwd[i, m]))
        market_fwd[h] = mkt

    # Label guard per horizon (D2).
    clean = {h: panel.clean_labels_mask(h) for h in HORIZONS}
    # Precomputed total forward return per horizon (per-symbol labels).
    fwd_total = {h: panel.forward_return_total(h) for h in HORIZONS}

    events, coverage = find_events(panel, cost, ex_dates)
    report: dict[str, Any] = {"strip_coverage": coverage}
    for band, df in events.items():
        cov = coverage[band]
        print(f"\n  {band}: {cov['candidates']:,} candidate events, "
              f"{cov['stripped']:,} stripped on real ex-dates "
              f"({cov['stripped_frac']:.1%}), {cov['kept']:,} kept")
        if df.empty:
            print(f"  {band}: no events")
            report[band] = {"events": 0, "strip_coverage": cov}
            continue
        df = df.copy()
        df["col"] = [int(np.where(panel.symbols == s)[0][0]) for s in df["symbol"]]
        ev_dates = pd.to_datetime(df["event_date"])
        explore = df[ev_dates < EXPLORE_END]
        holdout = df[ev_dates >= EXPLORE_END]
        print(f"  --- {band}: {len(df)} events "
              f"(explore {len(explore)} / holdout {len(holdout)}) ---")

        ex = cluster_by_date(explore, panel, market_fwd, clean, fwd_total)
        ho = cluster_by_date(holdout, panel, market_fwd, clean, fwd_total)
        v, reasons = verdict(ex, ho, band)
        report[band] = {"events": int(len(df)), "strip_coverage": cov,
                        "explore": ex, "holdout": ho,
                        "verdict": v, "reasons": reasons}
        for label, res in (("EXPLORE", ex), ("HOLDOUT", ho)):
            print(f"  {label}: {res.get('events', 0)} events")
            for r in res.get("rows", []):
                print(f"    {r['horizon']:>2}s  gross {r['gross_excess']:+.3%} "
                      f"(t {r['gross_clustered_t']:+.2f}) | "
                      f"net {r['net_excess']:+.3%} (t {r['net_clustered_t']:+.2f}) "
                      f"| cost {r['mean_cost']:.3%} | n {r['events']} / {r['dates']} dates")
        print(f"  VERDICT: {v}" + (f" — {reasons}" if reasons else ""))

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / "pilot_limit_bounce_v2.json"
    path.write_bytes(json.dumps(report, indent=2, default=str).encode("utf-8"))
    print(f"\n  report -> {path}")


if __name__ == "__main__":
    main()
