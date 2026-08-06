"""Arm C'' — confirmatory re-test of the insider purchase event study (2026-08-05).

Confirmatory re-test of Arm C' (AMBER, v2 artifact) per the pre-registration
in docs/superpowers/specs/2026-08-05-pilot-cpp-preregistration.md. The
event/mask/cost machinery is imported VERBATIM from `pilot_insider_purchases`
(build_cars, load_events) — no re-implementation — while inference is the
shared engine `pilot_lib`:

* Primary statistic: two-way (date x symbol) clustered t of holdout 63s net
  CAR (CGM V = V_date + V_symbol - V_intersection); date-only t reported for
  comparability with C'.
* Single primary horizon 63s (one quarterly earnings cycle after disclosure);
  126s is exploratory-only and cannot move the verdict.
* Engine-enforced power rule (events/dates/symbols/clusters/span) and verdict
  binding to the PRE_REG dict via sha256 (artifact pre_reg_sha256).

    python scripts/signals/pilot_insider_purchases_v3.py
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from panel import ARTIFACT_DIR, load_panel  # noqa: E402
from pilot_reversal import cost_matrix  # noqa: E402
import pilot_lib  # noqa: E402
from pilot_insider_purchases import (  # noqa: E402
    EXPLORE_END,
    HORIZONS,
    NET_HORIZONS,
    build_cars,
    load_events,
)

from app.services.signals.costs import CostParams  # noqa: E402

PRE_REG: dict[str, Any] = {
    "arm": "C''",
    "confirmatory_of": "C' (pilot_insider_purchases_v2.json, verdict AMBER)",
    "document": "docs/superpowers/specs/2026-08-05-pilot-cpp-preregistration.md",
    "primary_horizons": [63],           # one quarterly earnings cycle, theory
    "net_horizons": [63, 126],          # 126s exploratory-only
    "t_crit": 1.96,
    "max_ece": 0.05,
    "exclusion_top_n": 4,
    "min_events": 30,
    "min_dates": 10,
    "min_symbols": 8,
    "min_clusters": 15,
}
PRE_REG_SHA = pilot_lib.sha256_json(PRE_REG)


def cluster_rows(df: pd.DataFrame, horizons: tuple[int, ...],
                 key: str = "car_") -> dict[int, dict]:
    """Per-horizon inference rows on the event-level table.

    Two-way (date x symbol) clustered t on per-event net CAR is the primary
    statistic; date-only clustered t on per-date means is the C'-comparable
    one. Events quarantined at a horizon (NaN CAR) are dropped per horizon.
    """
    g1, g2 = pilot_lib.cluster_codes(df)
    rows: dict[int, dict] = {}
    for h in horizons:
        col = f"{key}{h}"
        sub = df[["event_date", "symbol", col, "cost"]].copy()
        sub = sub.dropna(subset=[col])
        if len(sub) < 2:
            continue
        sub["net"] = sub[col] - sub["cost"]
        y = sub["net"].to_numpy(dtype=np.float64)
        g1s, g2s = pilot_lib.cluster_codes(sub)
        net_mean, _, net_t, n_cl = pilot_lib.two_way_t(y, g1s, g2s)
        gross_mean, _, gross_t, _ = pilot_lib.two_way_t(
            sub[col].to_numpy(dtype=np.float64), g1s, g2s)
        # C'-comparable date-only rows (mean of per-date means).
        per_date = sub.groupby("event_date")["net"].mean()
        _, se_date, net_t_date = pilot_lib.date_only_t(
            per_date.to_numpy(dtype=np.float64),
            np.arange(len(per_date)))
        n = len(per_date)
        gross_per_date = sub.groupby("event_date")[col].mean()
        _, _, gross_t_date = pilot_lib.date_only_t(
            gross_per_date.to_numpy(dtype=np.float64),
            np.arange(n))
        eff = pilot_lib.effective_n(sub)
        rows[h] = {
            "horizon": h,
            "events": eff["events"],
            "dates": eff["dates"],
            "symbols": eff["symbols"],
            "clusters": eff["clusters"],
            "gross_car": round(float(gross_mean), 6),
            "gross_t_twoway": round(float(gross_t), 3),
            "gross_t_date": round(float(gross_t_date), 3),
            "net_car": round(net_mean, 6),
            "net_t": round(float(net_t), 3),          # primary statistic
            "net_t_date": round(float(net_t_date), 3),
            "mean_cost": round(float(sub["cost"].mean()), 6),
        }
    return rows


def exclusion_net(holdout: pd.DataFrame, h: int, top_n: int,
                  key: str = "car_") -> tuple[float, list[str]]:
    """Primary-horizon net CAR on holdout minus the top-N symbols by count."""
    col = f"{key}{h}"
    sub = holdout[["event_date", "symbol", col, "cost"]].copy()
    sub = sub.dropna(subset=[col])
    top = sub["symbol"].value_counts().head(top_n).index.tolist()
    rest = sub[~sub["symbol"].isin(top)]
    if len(rest) < 2:
        return float("nan"), top
    net = (rest[col] - rest["cost"]).to_numpy(dtype=np.float64)
    g1s, g2s = pilot_lib.cluster_codes(rest)
    mean, _, _, _ = pilot_lib.two_way_t(net, g1s, g2s)
    return float(mean), top


def main() -> None:
    print("=" * 78)
    print("Arm C'' — insider purchases, confirmatory re-test "
          "(pre-registered 2026-08-05)")
    print(f"pre-reg sha256: {PRE_REG_SHA}")
    print("=" * 78)

    panel = load_panel()
    cost = cost_matrix(panel, CostParams())
    events = asyncio.run(load_events())
    cars, gap_stats = build_cars(panel, events, cost)
    print(f"  {len(events):,} notices loaded; "
          + ", ".join(f"{d} {n}" for d, n in events["direction"].value_counts().items()))
    if gap_stats:
        print(f"  disclosure gap: n {gap_stats['n']}, median "
              f"{gap_stats['median_days']:.1f}d, p90 {gap_stats['p90_days']:.1f}d")

    buy = cars.get("buy")
    if buy is None or buy.empty:
        print("  no buy events — nothing to test")
        return
    ev_dates = pd.to_datetime(buy["event_date"])
    explore = buy[ev_dates < EXPLORE_END]
    holdout = buy[ev_dates >= EXPLORE_END]
    print(f"  buy: {len(buy)} events (explore {len(explore)} / "
          f"holdout {len(holdout)})")

    ex_rows = cluster_rows(explore, NET_HORIZONS)
    ho_rows = cluster_rows(holdout, NET_HORIZONS)
    ece = pilot_lib.ece_of(explore, holdout, (63,))

    # Span power input: last entry + primary horizon must fit the panel.
    dates = panel.dates.values.astype("datetime64[ns]")
    day0 = int(np.searchsorted(dates, np.datetime64(
        holdout["event_date"].max(), "ns"), side="left"))
    span_ok = bool(day0 + PRE_REG["primary_horizons"][0] < panel.shape[0])
    power = pilot_lib.effective_n(holdout)
    power["span_ok"] = span_ok

    e4, top4 = exclusion_net(holdout, 63, PRE_REG["exclusion_top_n"])

    v, reasons = pilot_lib.verdict(
        PRE_REG, power, ho_rows, ece,
        None if not np.isfinite(e4) else e4)

    for label, rows in (("EXPLORE", ex_rows), ("HOLDOUT", ho_rows)):
        print(f"\n  {label}: {sum(r['events'] for r in rows.values())} events")
        for h in sorted(rows):
            r = rows[h]
            print(f"    {h:>3}s  gross {r['gross_car']:+.3%} "
                  f"(tw {r['gross_t_twoway']:+.2f} / dt {r['gross_t_date']:+.2f}) | "
                  f"net {r['net_car']:+.3%} (tw {r['net_t']:+.2f} / "
                  f"dt {r['net_t_date']:+.2f}) | cost {r['mean_cost']:.3%} | "
                  f"n {r['events']} / {r['dates']} dates / {r['symbols']} syms / "
                  f"{r['clusters']} cl")
    print(f"\n  ECE(63s): {ece:.4f}")
    print(f"  ex-top-4 holdout 63s net: {e4:+.3%}  (excluded: "
          f"{', '.join(top4)})")
    print(f"  power: " + ", ".join(f"{k}={v}" for k, v in power.items()))
    print(f"  VERDICT: {v}" + (f" — {reasons}" if reasons else ""))

    payload = {
        "arm": "C''",
        "pre_reg": PRE_REG,
        "pre_reg_sha256": PRE_REG_SHA,
        "imported_design_sha256": hashlib.sha256(
            Path(__file__).resolve().with_name("pilot_insider_purchases.py")
            .read_bytes()).hexdigest(),
        "periods": {
            "explore": {"events": int(len(explore)),
                        "rows": [ex_rows[h] for h in sorted(ex_rows)]},
            "holdout": {"events": int(len(holdout)),
                        "rows": [ho_rows[h] for h in sorted(ho_rows)]},
        },
        "exclusion": {"top_symbols": top4, "net_63s": round(e4, 6)},
        "ece_63s": round(ece, 6),
        "power": power,
        "verdict": v,
        "reasons": reasons,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / "pilot_insider_purchases_v3.json"
    path.write_bytes(json.dumps(payload, indent=2, default=str).encode("utf-8"))
    print(f"\n  report -> {path}  (pre-reg {PRE_REG_SHA[:12]}...)")


if __name__ == "__main__":
    main()
