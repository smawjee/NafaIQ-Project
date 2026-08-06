"""Arm C' — director/insider purchase event study (corrected re-run, 2026-08-05).

The original Arm C verdict (RED) was invalidated: entry was at the *transaction*
date, but the trade is only public at the disclosure (notice) date — a median
1 day / p90 7 days executable-price gap (MEASUREMENT INVALIDATION, D6). This
is the pre-registered corrected re-run (PRE-REGISTRATION — A'/B'/C' section).

Tests whether a disclosed insider **purchase** (PSX 5.6.1(d)/5.6.4, from the
additive `psx_insider_transactions` table) is followed by positive date-
clustered CAR vs the universe benchmark, net of true cost.

Fixes vs the invalidated run:

* **Entry at first session on/after NOTICE (disclosure) date** (D6) — the
  executable price. The txn->notice gap is reported (median, p90, same-day %).
* **Total-return labels** (D3): abnormal returns and the benchmark use
  `total_return`, so attributed dividends do not depress CARs.
* **Label guard** (D2): CAR windows must satisfy `clean_labels_mask(h)`.
* **Power rule** (D4): a direction with < 30 holdout events or < 10 holdout
  dates is recorded CANNOT CONCLUDE, never RED.

Everything else unchanged: one entry per notice, directions buy (primary) /
sell (symmetry), horizons 21/63/126, date-clustered t, explore 2016-2023 /
holdout 2024-2026, true round-trip cost.

Writes a JSON report to artifacts/signals/pilot_insider_purchases_v2.json.
No DB writes.

    python scripts/signals/pilot_insider_purchases.py
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

HORIZONS = (21, 63, 126)
NET_HORIZONS = (63, 126)
EXPLORE_END = pd.Timestamp("2024-01-01")
SAMPLE_LO = pd.Timestamp("2016-01-01")
SAMPLE_HI = pd.Timestamp("2026-08-05")
MIN_HOLDOUT_EVENTS = 30
MIN_HOLDOUT_DATES = 10


async def load_events() -> pd.DataFrame:
    from sqlalchemy import text

    from app.repositories.base import connect

    async with connect() as conn:
        rows = (await conn.execute(text("""
            SELECT notice_id, row_no, symbol, notice_date, txn_date, direction,
                   shares, price, source_row_hash
            FROM psx_insider_transactions
            ORDER BY notice_id, row_no
        """))).mappings().all()
    df = pd.DataFrame(rows)
    df["symbol"] = df["symbol"].str.upper()
    for c in ("notice_date", "txn_date"):
        df[c] = pd.to_datetime(df[c])
    # One entry per notice: duplicate notices collapse to the first row.
    df = df.drop_duplicates(subset=["notice_id"], keep="first")
    return df


def build_cars(panel: Panel, events: pd.DataFrame,
               cost: np.ndarray) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Per-direction tables plus entry-gap disclosure stats.

    Entry is the first session on/after the NOTICE (disclosure) date (D6);
    total-return abnormal returns (D3); CAR windows must be contamination-
    clean per horizon (D2).
    """
    symbol_ix = {s: i for i, s in enumerate(panel.symbols)}
    dates = panel.dates.values.astype("datetime64[ns]")
    investable = panel.investable_mask()
    returns = panel.total_return()
    clean = {h: panel.clean_labels_mask(h) for h in HORIZONS}

    # Equal-weighted investable-universe TOTAL return per day (benchmark).
    market = np.full(panel.shape[0], np.nan)
    for i in range(panel.shape[0]):
        m = investable[i] & np.isfinite(returns[i])
        if m.sum() >= 20:
            market[i] = float(np.mean(returns[i, m]))
    abnormal = returns - market.reshape(-1, 1)

    out: dict[str, list[dict[str, Any]]] = {"buy": [], "sell": []}
    gaps: list[int] = []
    for _, row in events.iterrows():
        direction = str(row["direction"])
        if direction not in out:
            continue
        symbol = str(row["symbol"])
        col = symbol_ix.get(symbol)
        if col is None:
            continue
        notice = row["notice_date"]
        txn = row["txn_date"]
        if pd.isna(notice):
            continue
        if not (SAMPLE_LO <= notice < SAMPLE_HI):
            continue
        # Disclosure gap: how long after the trade the public notice landed.
        if not pd.isna(txn):
            gaps.append(int((notice - txn).days))
        # Entry: first session on/after NOTICE date (executable).
        day0 = int(np.searchsorted(dates, np.datetime64(notice, "ns"), side="left"))
        if day0 < 60 or day0 + max(HORIZONS) >= panel.shape[0]:
            continue
        if not investable[day0, col]:
            continue

        car: dict[int, float] = {}
        for h in HORIZONS:
            if not clean[h][day0, col]:
                continue          # quarantine THIS horizon only (D2)
            window = abnormal[day0:day0 + h, col]
            if not np.isfinite(window).all():
                continue
            car[h] = float(np.sum(window))
        if not car:
            continue

        record = {
            "symbol": symbol,
            "event_date": notice,
            "cost": float(cost[day0, col]),
        }
        for h in HORIZONS:
            record[f"car_{h}"] = car.get(h, np.nan)   # missing horizon = NaN
        out[direction].append(record)

    gap_stats: dict[str, Any] = {}
    if gaps:
        g = np.asarray(gaps, dtype=np.float64)
        gap_stats = {
            "n": int(len(g)),
            "median_days": float(np.median(g)),
            "p90_days": float(np.percentile(g, 90)),
            "same_day_frac": float(np.mean(g <= 0)),
        }
    return {k: pd.DataFrame(v) for k, v in out.items() if v}, gap_stats


def cluster_by_date(df: pd.DataFrame, horizons: tuple[int, ...]) -> dict[str, Any]:
    """One observation per event date per horizon; t-test across dates.

    Events quarantined at a horizon (NaN CAR) are dropped for that horizon
    only — never for the whole event (per-horizon D2 guard).
    """
    rows = []
    for h in horizons:
        key = f"car_{h}"
        sub = df[["event_date", key, "cost"]].copy()
        sub = sub.dropna(subset=[key])
        if sub.empty:
            continue
        sub["gross"] = sub[key]
        sub["net"] = sub[key] - sub["cost"]
        per_date = sub.groupby("event_date")["gross"].mean()
        net_per_date = sub.groupby("event_date")["net"].mean()
        n = len(per_date)
        if n < 2:
            continue
        gross = float(per_date.mean())
        se = float(per_date.std(ddof=1) / np.sqrt(n))
        net = float(net_per_date.mean())
        se_net = float(net_per_date.std(ddof=1) / np.sqrt(n))
        rows.append({
            "horizon": h,
            "events": int(len(sub)),
            "dates": n,
            "gross_car": round(gross, 6),
            "gross_clustered_t": round(gross / se, 3) if se > 0 else 0.0,
            "net_car": round(net, 6),
            "net_clustered_t": round(net / se_net, 3) if se_net > 0 else 0.0,
            "mean_cost": round(float(sub["cost"].mean()), 6),
        })
    return {"events": int(len(df)), "rows": rows}


def _positive_net_freq(df: pd.DataFrame, h: int) -> float:
    """Frequency of positive net CAR at horizon h (probability estimand)."""
    key = f"car_{h}"
    net = df[key] - df["cost"]
    net = net[np.isfinite(net)]
    return float(np.mean(net > 0)) if len(net) else float("nan")


def ece_of(explore: pd.DataFrame, holdout: pd.DataFrame) -> float:
    """ECE: mean |explore positive-net frequency - holdout frequency|.

    The probability estimand is P(net CAR > 0); predicted probabilities come
    from the explore set, realised frequencies from the holdout.
    """
    diffs = []
    for h in NET_HORIZONS:
        p, r = _positive_net_freq(explore, h), _positive_net_freq(holdout, h)
        if np.isfinite(p) and np.isfinite(r):
            diffs.append(abs(p - r))
    return float(np.mean(diffs)) if diffs else float("nan")


def verdict(direction: str, explore_df: pd.DataFrame,
            holdout_df: pd.DataFrame, explore: dict, holdout: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    ho_rows = {r["horizon"]: r for r in holdout.get("rows", [])}

    # Power rule (D4): with < MIN_HOLDOUT_EVENTS events or < MIN_HOLDOUT_DATES
    # dates, a null is not evidence of "no effect".
    if holdout.get("events", 0) < MIN_HOLDOUT_EVENTS or \
            max((r.get("dates", 0) for r in ho_rows.values()), default=0) < MIN_HOLDOUT_DATES:
        return "CANNOT CONCLUDE", [f"{direction}: holdout sample too small "
                                   f"({holdout.get('events', 0)} events) to power the test"]

    best_net, best_h, best_t = None, None, None
    for h in NET_HORIZONS:
        r = ho_rows.get(h)
        if r is None:
            continue
        if best_net is None or r["net_car"] > best_net:
            best_net, best_h, best_t = r["net_car"], h, r["net_clustered_t"]

    if best_net is None:
        return "RED", [f"{direction}: no holdout rows at 63/126"]

    cost = ho_rows.get(best_h, {}).get("mean_cost", 0.0)
    exceeds = best_net > cost
    if not exceeds:
        reasons.append(f"holdout {best_h}s net CAR {best_net:.4f} not > one "
                       f"round trip ({cost:.4f})")
    if best_t is None or best_t <= 1.96:
        reasons.append(f"holdout {best_h}s clustered t {best_t} <= 1.96")

    ece = ece_of(explore_df, holdout_df)
    if ece > 0.05:
        reasons.append(f"ECE {ece:.3f} > 0.05")
    if reasons:
        gross_ok = any(r.get("gross_car", 0) > 0 for r in ho_rows.values())
        return ("AMBER", reasons) if gross_ok else ("RED", reasons)
    return "GREEN", []


def main() -> None:
    print("=" * 78)
    print("Arm C' — director/insider purchases (pre-registered 2026-08-05, v2)")
    print("=" * 78)

    panel = load_panel()
    cost = cost_matrix(panel, CostParams())
    events = asyncio.run(load_events())
    print(f"  {len(events):,} notices loaded")
    print(f"  directions: " + ", ".join(
        f"{d} {n}" for d, n in events["direction"].value_counts().items()))

    cars, gap_stats = build_cars(panel, events, cost)
    report: dict[str, Any] = {}
    if gap_stats:
        print(f"\n  disclosure gap (txn -> notice): n {gap_stats['n']}, "
              f"median {gap_stats['median_days']:.1f}d, "
              f"p90 {gap_stats['p90_days']:.1f}d, "
              f"same-day {gap_stats['same_day_frac']:.1%}")
    for direction, df in cars.items():
        ev_dates = pd.to_datetime(df["event_date"])
        explore = df[ev_dates < EXPLORE_END]
        holdout = df[ev_dates >= EXPLORE_END]
        print(f"\n  --- {direction}: {len(df)} events "
              f"(explore {len(explore)} / holdout {len(holdout)}) ---")

        ex = cluster_by_date(explore, HORIZONS)
        ho = cluster_by_date(holdout, HORIZONS)
        v, reasons = verdict(direction, explore, holdout, ex, ho)
        report[direction] = {"events": int(len(df)), "explore": ex, "holdout": ho,
                             "verdict": v, "reasons": reasons,
                             "ece": ece_of(explore, holdout)}
        for label, res in (("EXPLORE", ex), ("HOLDOUT", ho)):
            print(f"  {label}: {res.get('events', 0)} events")
            for r in res.get("rows", []):
                print(f"    {r['horizon']:>3}s  gross {r['gross_car']:+.3%} "
                      f"(t {r['gross_clustered_t']:+.2f}) | "
                      f"net {r['net_car']:+.3%} (t {r['net_clustered_t']:+.2f}) "
                      f"| cost {r['mean_cost']:.3%} | n {r['events']} / {r['dates']} dates")
        print(f"  VERDICT: {v}" + (f" — {reasons}" if reasons else ""))

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / "pilot_insider_purchases_v2.json"
    path.write_bytes(json.dumps(report, indent=2, default=str).encode("utf-8"))
    print(f"\n  report -> {path}")


if __name__ == "__main__":
    main()
