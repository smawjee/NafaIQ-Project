"""H2 — does a liquidity-tiered universe make reversal tradeable long-only?

H1 established that PSX reversal has a real, stable cross-sectional edge (rank
IC +0.041 at 5d / +0.034 at 20d, positive in 8/8 explore years and both holdout
years) but that the long-only top decile is negative after cost, because the
extreme-loser decile is populated by illiquid names whose round trip (p90 2.17%)
swamps the edge.

H2 tests the diagnosis: tighten the universe to more liquid tiers and see
whether cost falls faster than gross edge does.

Pre-registered in RESEARCH_LOG.md (2026-08-04, "H2") *after* the H1 verdict was
recorded. Everything except the liquidity threshold is identical to H1 — same
panel, labels, signal sign, quarantine rule and cost model — so any difference
is attributable to the universe alone.

    python scripts/signals/pilot_liquidity.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from panel import ARTIFACT_DIR, load_panel  # noqa: E402
from pilot_reversal import cost_matrix, run_horizon  # noqa: E402

from app.services.signals.costs import CostParams  # noqa: E402

# (label, quantile passed to investable_mask) — quantile q keeps the top (1-q).
TIERS = (
    ("top50", 0.50),   # H1 baseline
    ("top30", 0.70),
    ("top20", 0.80),
    ("top10", 0.90),
)
HORIZONS = (5, 20)

# Pre-registered GREEN thresholds for H2.
GATE_MIN_POSITIVE_YEARS = 6
GATE_TOTAL_EXPLORE_YEARS = 8


def evaluate(res: dict[str, Any]) -> tuple[str, list[str]]:
    """Apply the pre-registered H2 rule. Thresholds are not tunable here."""
    reasons: list[str] = []
    ex, ho = res["explore"], res["holdout"]

    ex_net = ex.get("top_decile_net")
    net_ok = ex_net is not None and ex_net > 0
    if not net_ok:
        reasons.append(f"explore top-decile net {ex_net} not positive")

    folds = ex.get("ic_by_year") or {}
    positive = sum(1 for v in folds.values() if v > 0)
    folds_ok = positive >= GATE_MIN_POSITIVE_YEARS
    if not folds_ok:
        reasons.append(
            f"only {positive}/{len(folds)} explore years positive "
            f"(need {GATE_MIN_POSITIVE_YEARS}/{GATE_TOTAL_EXPLORE_YEARS})"
        )

    ho_net = ho.get("top_decile_net")
    holdout_ok = ho_net is not None and ho_net > 0
    if not holdout_ok:
        reasons.append(f"holdout top-decile net {ho_net} not positive")

    if net_ok and folds_ok and holdout_ok:
        return "GREEN", []
    if net_ok:
        return "AMBER", reasons
    return "RED", reasons


def main() -> None:
    print("=" * 78)
    print("H2 — liquidity-tiered reversal")
    print("pre-registered 2026-08-04 (after the H1 verdict), see RESEARCH_LOG.md")
    print("=" * 78)

    panel = load_panel()
    params = CostParams()
    cost = cost_matrix(panel, params)

    report: dict[str, Any] = {
        "pre_registered": "RESEARCH_LOG.md#pre-registration--2026-08-04--h2-liquidity-tiered-reversal",
        "note": "quarantined sample only — the contaminated reading is not the honest one",
        "runs": [],
    }

    print(f"\n{'tier':>6} {'h':>3} {'names':>6} {'gross':>9} {'cost':>8} "
          f"{'NET':>9} {'IC':>8} {'yrs+':>5}  verdict")
    print("-" * 78)

    for label, quantile in TIERS:
        investable = panel.investable_mask(liquidity_quantile=quantile)
        for horizon in HORIZONS:
            res = run_horizon(panel, horizon, cost,
                              quarantine=True, investable=investable)
            v, reasons = evaluate(res)
            res["tier"] = label
            res["liquidity_quantile"] = quantile
            res["verdict"] = v
            res["verdict_reasons"] = reasons
            report["runs"].append(res)

            ex = res["explore"]
            folds = ex.get("ic_by_year") or {}
            positive = sum(1 for x in folds.values() if x > 0)
            gross = ex.get("decile_mean_gross", [float("nan")] * 10)[-1]
            print(
                f"{label:>6} {horizon:>3} {res['universe_median_names']:>6} "
                f"{gross:>8.3%} {res['top_decile_mean_cost']:>7.3%} "
                f"{ex['top_decile_net']:>8.3%} {ex['ic_mean']:>8.4f} "
                f"{positive:>3}/{len(folds):<2} {v}"
            )

    print("-" * 78)
    print("\nholdout check for any tier that passed explore:")
    any_green = False
    for res in report["runs"]:
        if res["explore"]["top_decile_net"] is not None and res["explore"]["top_decile_net"] > 0:
            ho = res["holdout"]
            print(f"  {res['tier']} {res['horizon']}d: holdout net "
                  f"{ho['top_decile_net']}, IC {ho['ic_mean']} -> {res['verdict']}")
            any_green = any_green or res["verdict"] == "GREEN"
    if not any_green:
        print("  (no tier produced a positive after-cost top decile on explore)")

    out = ARTIFACT_DIR / "pilot_liquidity.json"
    out.write_bytes(json.dumps(report, indent=2).encode("utf-8"))
    print(f"\n  report -> {out}")

    # --- sensitivity ------------------------------------------------------
    # The spread schedule is an assumption, not a measurement, so a verdict
    # that flips inside the plausible parameter range is not a verdict.
    print("\n" + "=" * 78)
    print("SENSITIVITY — top50 / 20d net, across plausible spread assumptions")
    print("  (spread_at_reference = full spread at PKR 10m/day turnover)")
    print("=" * 78)
    investable = panel.investable_mask(liquidity_quantile=0.5)
    sens: list[dict[str, Any]] = []
    print(f"  {'base':>7} {'elast':>7} {'cost':>8} {'explore net':>13} {'holdout net':>13}")
    for base in (0.0015, 0.0030, 0.0060):
        for elasticity in (0.20, 0.30, 0.40):
            p = CostParams(spread_at_reference=base, liquidity_elasticity=elasticity)
            c = cost_matrix(panel, p)
            r = run_horizon(panel, 20, c, quarantine=True, investable=investable)
            row = {
                "spread_at_reference": base,
                "liquidity_elasticity": elasticity,
                "top_decile_mean_cost": r["top_decile_mean_cost"],
                "explore_net": r["explore"]["top_decile_net"],
                "holdout_net": r["holdout"]["top_decile_net"],
            }
            sens.append(row)
            print(f"  {base:>7.2%} {elasticity:>7.2f} {r['top_decile_mean_cost']:>7.3%} "
                  f"{r['explore']['top_decile_net']:>12.3%} "
                  f"{r['holdout']['top_decile_net']:>12.3%}")
    report["sensitivity_top50_20d"] = sens

    explore_positive = sum(1 for s in sens if (s["explore_net"] or 0) > 0)
    holdout_positive = sum(1 for s in sens if (s["holdout_net"] or 0) > 0)
    print(f"\n  explore net positive in {explore_positive}/{len(sens)} settings; "
          f"holdout net positive in {holdout_positive}/{len(sens)}")

    out.write_bytes(json.dumps(report, indent=2).encode("utf-8"))

    verdicts = {r["verdict"] for r in report["runs"]}
    overall = "GREEN" if "GREEN" in verdicts else ("AMBER" if "AMBER" in verdicts else "RED")
    print("\n" + "=" * 78)
    print(f"  H2 OVERALL: {overall}")
    print("=" * 78)


if __name__ == "__main__":
    main()
