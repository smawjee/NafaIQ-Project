"""Build the Tier 1 base-rate artifact and validate it out of sample.

Walks the full PSX panel, classifies every point-in-time observation into a
coarse conditioning cell, and counts what happened over the following 20
sessions. The result is `src/app/ml/signals/base_rates.json`, loaded at serving
like `rating_stats.json` and `trend_stats.json`.

The counting is trivially "calibrated" on the data it was counted from, so the
only question that matters is **stability**: do the 2016-2024 cells still hold
in 2025-2026? This script answers that explicitly and refuses to write an
artifact whose holdout calibration error is worse than the pre-registered bound.

Two probabilities are measured per cell:

* ``p_up``    — P(the stock rose at all over 20 sessions). What users mean by
  "will it go up", and the number the UI leads with.
* ``p_beat``  — P(it beat the universe median by more than its own round-trip
  cost). The decision-relevant one, and the basis for the BUY/SELL ladder.

Uses the same `classify_trend` and `assess_regime` the serving path uses, so a
cell computed here is the same cell looked up at request time.

    python scripts/signals/calibrate_base_rates.py [--horizon 20]
"""
from __future__ import annotations

import argparse
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

from app.services.signals.base_rates import (  # noqa: E402
    MIN_CELL_N,
    BaseRateTable,
    Sample,
    aggregate,
    reversal_bucket,
    volatility_band,
    write_artifact,
)
from app.services.signals.costs import CostParams  # noqa: E402
from app.services.signals.regime import assess_regime  # noqa: E402
from app.services.signals.trend_state import classify_trend  # noqa: E402

EXPLORE_END = pd.Timestamp("2025-01-01")
#: Pre-registered bound: a cell whose holdout hit-rate deviates by more than
#: this from its explore value is unstable. Matches promotion.py's MAX_ECE.
MAX_HOLDOUT_ECE = 0.05


def market_proxy(panel: Panel, investable: np.ndarray) -> np.ndarray:
    """Equal-weighted index of the investable universe.

    Used instead of psx_index_eod so the regime axis is consistent with the
    cross-sectional demeaning (which is also equal-weighted). A cap-weighted
    index would classify regimes by a handful of heavyweights — the exact
    mismatch that made the old 'beat KSE-100' label unwinnable.
    """
    rets = panel.returns()
    out = np.ones(panel.shape[0])
    level = 1.0
    for i in range(panel.shape[0]):
        m = investable[i] & np.isfinite(rets[i])
        if m.sum() >= 20:
            level *= (1.0 + float(np.mean(rets[i, m])))
        out[i] = level
    return out


def build_samples(panel: Panel, horizon: int) -> tuple[list[Sample], np.ndarray]:
    """One Sample per investable, uncontaminated observation."""
    investable = panel.investable_mask()
    contaminated = panel.contamination_mask(back=horizon, forward=horizon)
    usable = investable & ~contaminated

    fwd = panel.forward_return(horizon)
    trail = panel.trailing_return(horizon)
    cost = cost_matrix(panel, CostParams())

    close_df = pd.DataFrame(panel.close)
    sma50 = close_df.rolling(50, min_periods=50).mean().to_numpy()
    sma200 = close_df.rolling(200, min_periods=200).mean().to_numpy()
    ret20 = panel.trailing_return(20)
    ret60 = panel.trailing_return(60)
    low_252 = close_df.rolling(252, min_periods=100).min().to_numpy()
    logret = pd.DataFrame(panel.returns())
    ann_vol = (logret.rolling(20, min_periods=15).std() * np.sqrt(252)).to_numpy()

    index = market_proxy(panel, investable)

    # Regime is a market-level property: compute once per date, not per cell.
    regimes: list[str] = []
    for i in range(panel.shape[0]):
        window = index[max(0, i - 250):i + 1]
        regimes.append(assess_regime(window).regime if len(window) >= 60 else "NEUTRAL")

    samples: list[Sample] = []
    sample_dates: list[Any] = []
    dates = panel.dates

    for i in range(panel.shape[0]):
        m = usable[i] & np.isfinite(fwd[i]) & np.isfinite(trail[i])
        n = int(m.sum())
        if n < 40:
            continue
        cols = np.flatnonzero(m)

        trail_row = trail[i, cols]
        # Cross-sectional percentile of the trailing move (0 = biggest loser).
        order = np.argsort(np.argsort(trail_row))
        pct = 100.0 * order / max(n - 1, 1)

        fwd_row = fwd[i, cols]
        demeaned = fwd_row - np.mean(fwd_row)
        regime = regimes[i]
        sample_dates.extend([dates[i]] * n)

        for j, col in enumerate(cols):
            trend = classify_trend({
                "price_sma50_ratio": _ratio(panel.close[i, col], sma50[i, col]),
                "price_sma200_ratio": _ratio(panel.close[i, col], sma200[i, col]),
                "sma50": _f(sma50[i, col]),
                "sma200": _f(sma200[i, col]),
                "ret_20d": _f(ret20[i, col]),
                "ret_60d": _f(ret60[i, col]),
                "dist_52w_low": _ratio(panel.close[i, col], low_252[i, col]),
            }).state

            samples.append(Sample(
                reversal=reversal_bucket(float(pct[j])),
                trend=trend,
                volatility=volatility_band(_f(ann_vol[i, col])),
                regime=regime,
                # p_up is measured on the raw forward return; p_beat below is a
                # separate table so the two are never conflated.
                outcome=bool(fwd_row[j] > 0),
                forward_return=float(demeaned[j]),
            ))

    assert len(samples) == len(sample_dates), "date tagging desynced from samples"
    return samples, np.asarray(sample_dates)


def build_beat_samples(panel: Panel, horizon: int) -> list[Sample]:
    """Same cells, but the outcome is 'beat the universe median after cost'."""
    investable = panel.investable_mask()
    contaminated = panel.contamination_mask(back=horizon, forward=horizon)
    usable = investable & ~contaminated
    fwd = panel.forward_return(horizon)
    trail = panel.trailing_return(horizon)
    cost = cost_matrix(panel, CostParams())

    out: list[Sample] = []
    for i in range(panel.shape[0]):
        m = usable[i] & np.isfinite(fwd[i]) & np.isfinite(trail[i])
        n = int(m.sum())
        if n < 40:
            continue
        cols = np.flatnonzero(m)
        fwd_row = fwd[i, cols]
        demeaned = fwd_row - np.median(fwd_row)
        cost_row = cost[i, cols]
        trail_row = trail[i, cols]
        order = np.argsort(np.argsort(trail_row))
        pct = 100.0 * order / max(n - 1, 1)
        for j in range(len(cols)):
            out.append(Sample(
                reversal=reversal_bucket(float(pct[j])),
                trend=None, volatility=None, regime=None,
                outcome=bool(demeaned[j] > cost_row[j]),
                forward_return=float(demeaned[j]),
            ))
    return out


def _f(x: Any) -> float | None:
    try:
        v = float(x)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _ratio(a: Any, b: Any) -> float | None:
    av, bv = _f(a), _f(b)
    if av is None or bv is None or bv == 0:
        return None
    return av / bv - 1.0


def validate_holdout(explore: dict, holdout_samples: list[Sample]) -> dict[str, Any]:
    """Do the explore cells predict the holdout period? The only real test."""
    table = BaseRateTable(explore)
    buckets: dict[str, list[tuple[float, bool]]] = {}
    for s in holdout_samples:
        br = table.lookup(reversal=s.reversal, trend=s.trend,
                          volatility=s.volatility, regime=s.regime)
        if br is None:
            continue
        key = f"{round(br.p * 10) / 10:.1f}"
        buckets.setdefault(key, []).append((br.p, s.outcome))

    rows, total, weighted_error = [], 0, 0.0
    for key in sorted(buckets):
        pairs = buckets[key]
        n = len(pairs)
        predicted = sum(p for p, _ in pairs) / n
        actual = sum(1 for _, o in pairs if o) / n
        rows.append({"bucket": key, "n": n,
                     "predicted": round(predicted, 4),
                     "actual": round(actual, 4),
                     "gap": round(actual - predicted, 4)})
        total += n
        weighted_error += n * abs(actual - predicted)

    ece = weighted_error / total if total else 1.0
    return {"reliability": rows, "n": total, "ece": round(ece, 4),
            "passes": ece <= MAX_HOLDOUT_ECE}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=20)
    ap.add_argument("--force", action="store_true",
                    help="write the artifact even if holdout calibration fails")
    args = ap.parse_args()

    print("=" * 74)
    print(f"TIER 1 BASE-RATE CALIBRATION (horizon {args.horizon}d)")
    print("=" * 74)

    panel = load_panel()
    print(f"  panel {panel.shape[0]} dates x {panel.shape[1]} symbols")

    print("  building samples...")
    samples, sample_dates = build_samples(panel, args.horizon)
    print(f"  {len(samples):,} point-in-time observations")

    explore_mask = sample_dates < EXPLORE_END
    explore_samples = [s for s, keep in zip(samples, explore_mask) if keep]
    holdout_samples = [s for s, keep in zip(samples, explore_mask) if not keep]
    print(f"  explore {len(explore_samples):,} / holdout {len(holdout_samples):,}")

    explore_table = aggregate(explore_samples, horizon=args.horizon)
    full_table = aggregate(samples, horizon=args.horizon)

    print("\n  --- out-of-sample stability (explore cells vs holdout outcomes) ---")
    validation = validate_holdout(explore_table, holdout_samples)
    print(f"  {'predicted':>10} {'actual':>8} {'gap':>8} {'n':>8}")
    for row in validation["reliability"]:
        print(f"  {row['predicted']:>10.3f} {row['actual']:>8.3f} "
              f"{row['gap']:>+8.3f} {row['n']:>8,}")
    print(f"\n  holdout ECE = {validation['ece']:.4f} "
          f"(bound {MAX_HOLDOUT_ECE}) -> {'PASS' if validation['passes'] else 'FAIL'}")

    finest = full_table["levels"][0]
    populated = sum(1 for c in finest.values() if c.get("n", 0) >= MIN_CELL_N)
    print(f"\n  finest level: {len(finest)} cells, {populated} with n >= {MIN_CELL_N}")

    print("\n  --- p_up by reversal bucket (marginal) ---")
    for key, cell in sorted(full_table["levels"][3].items()):
        if cell.get("n", 0) >= MIN_CELL_N:
            print(f"  {key:28s} p={cell['p']:.3f} "
                  f"[{cell['p_lower']:.3f}, {cell['p_upper']:.3f}]  "
                  f"median {cell['median_return']:+.3%}  n={cell['n']:,}")

    beat = aggregate(build_beat_samples(panel, args.horizon), horizon=args.horizon)
    print("\n  --- p_beat (beat universe median after own cost) by reversal bucket ---")
    for key, cell in sorted(beat["levels"][3].items()):
        if cell.get("n", 0) >= MIN_CELL_N:
            print(f"  {key:28s} p={cell['p']:.3f} "
                  f"[{cell['p_lower']:.3f}, {cell['p_upper']:.3f}]  n={cell['n']:,}")

    payload = {
        **full_table,
        "generated_for": "p_up",
        "explore_end": str(EXPLORE_END.date()),
        "holdout_validation": validation,
        "p_beat": beat,
    }

    if not validation["passes"] and not args.force:
        report = ARTIFACT_DIR / "base_rates_rejected.json"
        report.write_bytes(json.dumps(payload, indent=2).encode("utf-8"))
        print(f"\n  ARTIFACT NOT WRITTEN — holdout calibration failed.")
        print(f"  diagnostic -> {report}")
        raise SystemExit(1)

    path = write_artifact(payload)
    print(f"\n  artifact -> {path}")


if __name__ == "__main__":
    main()
