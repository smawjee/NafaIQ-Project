"""Go/No-Go pilot for the cross-sectional reversal hypothesis (H1).

Tests, on data already in the database, whether a reversal-ranked portfolio
produces a positive top-minus-bottom decile spread **after per-symbol cost**.
The hypothesis, method and decision rule were pre-registered in RESEARCH_LOG.md
before this script was written; nothing here may be tuned to improve the answer.

What this fixes relative to the closed experiments:

* **Benchmark.** Labels are forward returns *demeaned by date across the
  investable universe*, not excess over the cap-weighted KSE-100. The old label
  gave the median stock a ~35-40% base rate during a heavyweight-driven rally,
  so a well-calibrated model was still forced into a losing bet.
* **Cost.** Per-symbol round trip from ``signals/costs.py`` (Corwin-Schultz
  spread + square-root impact), not one flat number for a universe whose
  effective spreads differ by an order of magnitude.
* **Contamination.** psx_dividends holds no bonus/rights history at all, so
  roughly eight of ten years are unadjusted. Observations near a limit-breaking
  move are quarantined rather than repaired. The run reports both ways: a fake
  corporate-action crash has an ordinary forward return whereas a true loser
  (per H1) has a positive one, so contamination *dilutes* the measured effect.
  A GREEN that survives it is therefore conservative.

Writes a JSON report to artifacts/signals/ and prints the verdict. No DB writes.

    python scripts/signals/pilot_reversal.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from panel import ARTIFACT_DIR, Panel, load_panel  # noqa: E402

from app.services.signals.costs import CostParams  # noqa: E402

HORIZONS = (5, 20)
N_DECILES = 10
EXPLORE_END = pd.Timestamp("2025-01-01")   # explore < this; holdout >= this
MIN_NAMES_PER_DATE = 40                    # need enough names to form deciles

# Pre-registered GREEN thresholds (RESEARCH_LOG.md, 2026-08-04).
GATE_MONOTONICITY = 0.8
GATE_MIN_POSITIVE_FOLD_FRAC = 0.75


# --- cost -----------------------------------------------------------------


def rolling_cs_spread(panel: Panel, window: int = 60) -> np.ndarray:
    """Vectorised rolling Corwin-Schultz spread over the whole panel.

    **Reference only — not on the cost path.** Kept so
    ``scripts/signals/diagnose_cost.py`` can keep demonstrating why: on PSX this
    estimator is flat in liquidity and tracks volatility instead of spread.
    ``test_pilot_reversal.py`` asserts it still matches the scalar reference.
    """
    k = 3.0 - 2.0 * np.sqrt(2.0)
    h, l = panel.high, panel.low
    ok = np.isfinite(h) & np.isfinite(l) & (h > 0) & (l > 0) & (h >= l)

    h0, h1 = h[:-1], h[1:]
    l0, l1 = l[:-1], l[1:]
    pair_ok = ok[:-1] & ok[1:]

    with np.errstate(invalid="ignore", divide="ignore"):
        beta = np.log(h0 / l0) ** 2 + np.log(h1 / l1) ** 2
        gamma = np.log(np.maximum(h0, h1) / np.minimum(l0, l1)) ** 2
        alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
        spread = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))

    spread = np.where(pair_ok & np.isfinite(spread), spread, np.nan)
    spread = np.maximum(spread, 0.0)
    # Pair (t-1,t) is attributed to t; row 0 has no pair.
    padded = np.vstack([np.full((1, spread.shape[1]), np.nan), spread])
    return pd.DataFrame(padded).rolling(window, min_periods=window // 3).mean().to_numpy()


def cost_matrix(panel: Panel, params: CostParams) -> np.ndarray:
    """Per-symbol, per-date round-trip cost as a fraction of notional.

    Vectorised form of ``costs.round_trip_cost``; the two are asserted equal in
    ``test_pilot_reversal.py``. Spread comes from the transparent
    price/turnover schedule, never from the bar range — see the note in
    ``app/services/signals/costs.py`` for the measured reason.
    """
    price = panel.close
    turnover = pd.DataFrame(panel.turnover()).rolling(
        60, min_periods=20).median().to_numpy()
    daily_vol = pd.DataFrame(panel.returns()).rolling(
        60, min_periods=20).std().to_numpy()

    with np.errstate(invalid="ignore", divide="ignore"):
        tick_floor = np.where(price > 0, params.tick_size_pkr / price, params.max_spread)
        ratio = np.where(turnover > 0,
                         params.reference_turnover_pkr / turnover,
                         np.inf)
        scheduled = params.spread_at_reference * np.power(ratio, params.liquidity_elasticity)

    scheduled = np.where(np.isfinite(scheduled), scheduled, params.max_spread)
    scheduled = np.clip(scheduled, params.min_spread, params.max_spread)
    spread = np.minimum(np.maximum(scheduled, tick_floor), params.max_spread)

    impact = 2.0 * params.impact_coefficient * np.nan_to_num(daily_vol) * np.sqrt(
        params.participation)

    total = params.explicit_round_trip + spread + impact
    total = np.clip(total, params.min_round_trip, params.max_round_trip)
    # No turnover history at all -> treat as untradeable, not as free.
    total[~np.isfinite(total)] = params.max_round_trip
    return total


# --- metrics ---------------------------------------------------------------


def _rankdata_rows(x: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Row-wise average ranks in [0,1] over valid entries; NaN elsewhere."""
    out = np.full(x.shape, np.nan)
    for i in range(x.shape[0]):
        m = valid[i]
        n = int(m.sum())
        if n < 2:
            continue
        vals = x[i, m]
        order = np.argsort(vals, kind="mergesort")
        ranks = np.empty(n, dtype=np.float64)
        sorted_vals = vals[order]
        j = 0
        while j < n:                       # average ranks for ties
            k = j
            while k + 1 < n and sorted_vals[k + 1] == sorted_vals[j]:
                k += 1
            ranks[order[j:k + 1]] = (j + k) / 2.0
            j = k + 1
        out[i, m] = ranks / max(n - 1, 1)
    return out


def spearman_ic(signal: np.ndarray, label: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Per-date Spearman rank correlation between signal and label."""
    sr = _rankdata_rows(signal, valid)
    lr = _rankdata_rows(label, valid)
    n_dates = signal.shape[0]
    ic = np.full(n_dates, np.nan)
    for i in range(n_dates):
        m = valid[i] & np.isfinite(sr[i]) & np.isfinite(lr[i])
        if m.sum() < MIN_NAMES_PER_DATE:
            continue
        a, b = sr[i, m], lr[i, m]
        sa, sb = a.std(), b.std()
        if sa == 0 or sb == 0:
            continue
        ic[i] = float(((a - a.mean()) * (b - b.mean())).mean() / (sa * sb))
    return ic


def decile_profile(signal: np.ndarray, label: np.ndarray, cost: np.ndarray,
                   valid: np.ndarray, rebalance_rows: np.ndarray) -> dict[str, Any]:
    """Mean demeaned forward return per signal decile, gross and net of cost.

    Only ``rebalance_rows`` are used, spaced one horizon apart, so the sampled
    holding periods do not overlap and each contributes independent information.
    """
    bucket_gross: list[list[float]] = [[] for _ in range(N_DECILES)]
    bucket_net: list[list[float]] = [[] for _ in range(N_DECILES)]

    for i in rebalance_rows:
        m = valid[i] & np.isfinite(signal[i]) & np.isfinite(label[i])
        n = int(m.sum())
        if n < MIN_NAMES_PER_DATE:
            continue
        s, y, c = signal[i, m], label[i, m], cost[i, m]
        order = np.argsort(s, kind="mergesort")
        edges = np.linspace(0, n, N_DECILES + 1).astype(int)
        for d in range(N_DECILES):
            idx = order[edges[d]:edges[d + 1]]
            if idx.size == 0:
                continue
            bucket_gross[d].append(float(np.mean(y[idx])))
            # A long-only decile portfolio pays its own round trip.
            bucket_net[d].append(float(np.mean(y[idx] - c[idx])))

    gross = [float(np.mean(b)) if b else float("nan") for b in bucket_gross]
    net = [float(np.mean(b)) if b else float("nan") for b in bucket_net]
    counts = [len(b) for b in bucket_gross]

    finite = [g for g in gross if np.isfinite(g)]
    monotonicity = float("nan")
    if len(finite) == N_DECILES:
        idx = np.arange(N_DECILES, dtype=np.float64)
        monotonicity = float(np.corrcoef(idx, np.asarray(gross))[0, 1])

    return {
        "decile_mean_gross": [round(g, 6) for g in gross],
        "decile_mean_net": [round(x, 6) for x in net],
        "periods_per_decile": counts,
        "monotonicity": round(monotonicity, 4) if np.isfinite(monotonicity) else None,
        "top_minus_bottom_gross": (
            round(gross[-1] - gross[0], 6)
            if np.isfinite(gross[-1]) and np.isfinite(gross[0]) else None
        ),
        # Long the top decile, short the bottom: each leg pays its own cost, so
        # the spread carries both. Reported for a long-only reading too.
        "top_minus_bottom_net": (
            round(net[-1] - net[0], 6)
            if np.isfinite(net[-1]) and np.isfinite(net[0]) else None
        ),
        "top_decile_net": round(net[-1], 6) if np.isfinite(net[-1]) else None,
    }


def yearly_ic(ic: np.ndarray, dates: pd.DatetimeIndex) -> dict[str, float]:
    out: dict[str, float] = {}
    years = dates.year.to_numpy()
    for y in np.unique(years):
        vals = ic[(years == y) & np.isfinite(ic)]
        if vals.size >= 20:
            out[str(int(y))] = round(float(vals.mean()), 5)
    return out


# --- the experiment --------------------------------------------------------


def run_horizon(panel: Panel, horizon: int, cost: np.ndarray, *,
                quarantine: bool,
                investable: np.ndarray | None = None) -> dict[str, Any]:
    """One horizon, one contamination setting.

    ``investable`` lets a caller substitute a different universe (H2 varies the
    liquidity threshold) while keeping labelling, quarantine and cost identical.
    """
    if investable is None:
        investable = panel.investable_mask()

    fwd = panel.forward_return(horizon)
    trailing = panel.trailing_return(horizon)

    valid = investable & np.isfinite(fwd) & np.isfinite(trailing) & np.isfinite(cost)
    if quarantine:
        contaminated = panel.contamination_mask(back=horizon, forward=horizon)
        valid = valid & ~contaminated

    # Label: forward return demeaned by date across that day's universe.
    label = np.full_like(fwd, np.nan)
    for i in range(fwd.shape[0]):
        m = valid[i]
        if m.sum() >= MIN_NAMES_PER_DATE:
            label[i, m] = fwd[i, m] - np.mean(fwd[i, m])

    # Signal, sign fixed in advance by H1: reversal, so *negated* trailing return.
    # High signal value = biggest recent loser = predicted outperformer.
    signal = -trailing

    ic = spearman_ic(signal, label, valid)
    dates = panel.dates

    explore = dates < EXPLORE_END
    holdout = ~explore

    # Non-overlapping rebalance dates, one horizon apart.
    rebalance = np.arange(0, len(dates), horizon)

    def subset(mask: np.ndarray) -> np.ndarray:
        return np.asarray([i for i in rebalance if mask[i]], dtype=int)

    # Mean cost actually borne by the traded (top) decile, reported so a
    # negative net result can be attributed to cost rather than to the signal.
    top_costs: list[float] = []
    for i in rebalance:
        m = valid[i] & np.isfinite(signal[i])
        n = int(m.sum())
        if n < MIN_NAMES_PER_DATE:
            continue
        s, c = signal[i, m], cost[i, m]
        idx = np.argsort(s, kind="mergesort")[int(n * 0.9):]
        if idx.size:
            top_costs.append(float(np.mean(c[idx])))

    result = {
        "horizon": horizon,
        "quarantined": quarantine,
        "universe_median_names": int(np.median(valid.sum(axis=1))),
        "observations": int(valid.sum()),
        "top_decile_mean_cost": round(float(np.mean(top_costs)), 6) if top_costs else None,
        "explore": {
            "ic_mean": _safe_mean(ic[explore]),
            "ic_by_year": yearly_ic(ic[explore], dates[explore]),
            **decile_profile(signal, label, cost, valid, subset(explore)),
        },
        "holdout": {
            "ic_mean": _safe_mean(ic[holdout]),
            "ic_by_year": yearly_ic(ic[holdout], dates[holdout]),
            **decile_profile(signal, label, cost, valid, subset(holdout)),
        },
    }
    return result


def _safe_mean(x: np.ndarray) -> float | None:
    vals = x[np.isfinite(x)]
    return round(float(vals.mean()), 5) if vals.size else None


def verdict(result: dict[str, Any]) -> tuple[str, list[str]]:
    """Apply the pre-registered decision rule. No post-hoc thresholds."""
    reasons: list[str] = []
    ex, ho = result["explore"], result["holdout"]

    mono = ex.get("monotonicity")
    mono_ok = mono is not None and abs(mono) >= GATE_MONOTONICITY
    if not mono_ok:
        reasons.append(f"explore monotonicity {mono} below {GATE_MONOTONICITY}")

    tmb_net = ex.get("top_minus_bottom_net")
    spread_ok = tmb_net is not None and tmb_net > 0
    if not spread_ok:
        reasons.append(f"explore top-minus-bottom after cost {tmb_net} not positive")

    folds = ex.get("ic_by_year") or {}
    pos_frac = (sum(1 for v in folds.values() if v > 0) / len(folds)) if folds else 0.0
    folds_ok = pos_frac >= GATE_MIN_POSITIVE_FOLD_FRAC
    if not folds_ok:
        reasons.append(
            f"only {pos_frac:.0%} of explore years have positive IC "
            f"(need {GATE_MIN_POSITIVE_FOLD_FRAC:.0%})"
        )

    ho_ic, ex_ic = ho.get("ic_mean"), ex.get("ic_mean")
    holdout_ok = (
        ho_ic is not None and ex_ic is not None
        and np.sign(ho_ic) == np.sign(ex_ic) and ho_ic != 0
    )
    if not holdout_ok:
        reasons.append(f"holdout IC {ho_ic} does not preserve the explore sign {ex_ic}")

    if mono_ok and spread_ok and folds_ok and holdout_ok:
        return "GREEN", []
    if spread_ok:
        return "AMBER", reasons
    return "RED", reasons


def main() -> None:
    print("=" * 78)
    print("GO/NO-GO PILOT — cross-sectional reversal (H1)")
    print("pre-registered 2026-08-04, see scripts/signals/RESEARCH_LOG.md")
    print("=" * 78)

    panel = load_panel()
    print(f"  panel: {panel.shape[0]} dates x {panel.shape[1]} symbols "
          f"({panel.dates[0].date()} -> {panel.dates[-1].date()})")

    params = CostParams()
    cost = cost_matrix(panel, params)
    # Summarise over the INVESTABLE cells only. Averaging over the full panel
    # includes ~80% non-existent bars, all pinned at the untradeable cap, and
    # reports a median that describes nothing anyone would trade.
    investable = panel.investable_mask()
    finite_cost = cost[investable & np.isfinite(cost)]
    print(f"  round-trip cost (investable universe): median {np.median(finite_cost):.3%}, "
          f"p10 {np.quantile(finite_cost, 0.1):.3%}, "
          f"p90 {np.quantile(finite_cost, 0.9):.3%}")

    report: dict[str, Any] = {
        "pre_registered": "RESEARCH_LOG.md#pre-registration--2026-08-04",
        "panel": {
            "dates": [str(panel.dates[0].date()), str(panel.dates[-1].date())],
            "n_dates": int(panel.shape[0]),
            "n_symbols": int(panel.shape[1]),
        },
        "cost_params": params.__dict__,
        "cost_summary": {
            "median": round(float(np.median(finite_cost)), 6),
            "p10": round(float(np.quantile(finite_cost, 0.1)), 6),
            "p90": round(float(np.quantile(finite_cost, 0.9)), 6),
        },
        "runs": [],
    }

    for horizon in HORIZONS:
        for quarantine in (True, False):
            tag = "quarantined" if quarantine else "contaminated"
            print(f"\n--- horizon {horizon}d, {tag} " + "-" * 40)
            res = run_horizon(panel, horizon, cost, quarantine=quarantine)
            v, reasons = verdict(res)
            res["verdict"] = v
            res["verdict_reasons"] = reasons
            report["runs"].append(res)

            ex, ho = res["explore"], res["holdout"]
            print(f"  universe/day     : {res['universe_median_names']}")
            print(f"  explore IC       : {ex['ic_mean']}   by year: {ex['ic_by_year']}")
            print(f"  holdout IC       : {ho['ic_mean']}   by year: {ho['ic_by_year']}")
            print(f"  monotonicity     : {ex['monotonicity']}")
            print("  decile gross (explore, low->high signal):")
            print("    " + "  ".join(f"{g:+.3%}" if np.isfinite(g) else "  n/a"
                                     for g in ex["decile_mean_gross"]))
            print(f"  top-bottom gross : {ex['top_minus_bottom_gross']}")
            print(f"  top-bottom NET   : {ex['top_minus_bottom_net']}")
            print(f"  top decile NET   : {ex['top_decile_net']}")
            print(f"  VERDICT          : {v}")
            for r in reasons:
                print(f"    - {r}")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACT_DIR / "pilot_reversal.json"
    out.write_bytes(json.dumps(report, indent=2).encode("utf-8"))
    print(f"\n  report -> {out}")

    # Headline verdict = the quarantined runs (the clean-data reading).
    clean = [r for r in report["runs"] if r["quarantined"]]
    print("\n" + "=" * 78)
    for r in clean:
        print(f"  {r['horizon']:>3}d  {r['verdict']}")
    print("=" * 78)


if __name__ == "__main__":
    main()
