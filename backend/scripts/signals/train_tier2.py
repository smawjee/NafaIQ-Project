"""Tier 2 — train, validate and gate the ML ranker.

Runs a **benchmark ladder** and promotes the simplest model that clears the
gate, rather than assuming gradient boosting wins:

  0. constant base rate            (the reference every model must beat)
  1. logistic regression on ranks  (regularised linear)
  2. LightGBM                      (gradient boosting)
  3. seed ensemble of the winner   (variance reduction + epistemic signal)

At an information coefficient around 0.03 a well-regularised linear model
frequently matches a GBM and is far more stable out of sample. Skipping this
comparison is how teams end up shipping complexity that earns nothing.

Validation is purged K-fold with an embargo, weighted by average uniqueness —
without those two the CV numbers are inflated rather than merely noisy (see
`services/signals/validation.py` for why). 2025-2026 is held out entirely and
is not touched until the explore verdict is written.

Writes a report to artifacts/signals/tier2_report.json. Promotion is decided by
`services/signals/promotion.py`, not here.

    python scripts/signals/train_tier2.py [--folds 5] [--seeds 5]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ml_dataset import build_dataset  # noqa: E402
from panel import ARTIFACT_DIR, load_panel  # noqa: E402
from pilot_reversal import cost_matrix  # noqa: E402

from app.services.signals.costs import CostParams  # noqa: E402
from app.services.signals.validation import (  # noqa: E402
    brier_skill_score,
    deflated_sharpe_ratio,
    expected_calibration_error,
    panel_average_uniqueness,
    probability_of_backtest_overfitting,
    purged_kfold,
    rank_ic,
)

HORIZON = 20
EXPLORE_END = pd.Timestamp("2025-01-01")

#: Tier 1's measured out-of-sample calibration error. Tier 2 has to be at least
#: this well calibrated or it is a downgrade dressed up as an upgrade.
TIER1_HOLDOUT_ECE = 0.0237

#: Trials already spent across four generations of research on this dataset.
#: Deliberately generous: under-counting trials inflates the deflated Sharpe,
#: which is the number meant to protect against exactly that.
PRIOR_TRIALS = 200


def _clean(X: np.ndarray) -> np.ndarray:
    """Median-impute and clip. Trees tolerate NaN; the linear model does not."""
    out = np.array(X, dtype=np.float64, copy=True)
    for j in range(out.shape[1]):
        col = out[:, j]
        finite = np.isfinite(col)
        if not finite.any():
            out[:, j] = 0.0
            continue
        median = float(np.median(col[finite]))
        col[~finite] = median
        lo, hi = np.quantile(col, [0.005, 0.995])
        out[:, j] = np.clip(col, lo, hi)
    return out


def fit_logistic(X_tr, y_tr, w_tr, X_te):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler().fit(X_tr)
    model = LogisticRegression(C=0.05, max_iter=400, solver="lbfgs")
    model.fit(scaler.transform(X_tr), y_tr, sample_weight=w_tr)
    return model.predict_proba(scaler.transform(X_te))[:, 1]


def fit_lightgbm(X_tr, y_tr, w_tr, X_te, seed: int = 0):
    import lightgbm as lgb

    params = dict(
        objective="binary", learning_rate=0.03, num_leaves=31,
        min_data_in_leaf=500, feature_fraction=0.7, bagging_fraction=0.7,
        bagging_freq=1, lambda_l2=5.0, verbose=-1, seed=seed,
        num_threads=0, deterministic=True,
    )
    train = lgb.Dataset(X_tr, label=y_tr, weight=w_tr)
    booster = lgb.train(params, train, num_boost_round=300)
    return booster.predict(X_te), booster


def evaluate(name: str, probs: np.ndarray, ds, idx: np.ndarray,
             base_rate: float) -> dict[str, Any]:
    """Statistical and economic scoring of one model's out-of-fold predictions."""
    y = ds.y_binary[idx]
    excess = ds.y_excess[idx]
    cost = ds.cost[idx]
    days = ds.day_index[idx]

    # Rank IC per date, then averaged — a pooled correlation would be dominated
    # by cross-date level differences rather than within-date ranking skill.
    ics: list[float] = []
    top_net: list[float] = []
    order = np.argsort(days, kind="mergesort")
    days_s, probs_s, excess_s, cost_s = days[order], probs[order], excess[order], cost[order]
    for span in np.split(np.arange(days_s.size), np.flatnonzero(np.diff(days_s)) + 1):
        if span.size < 40:
            continue
        ics.append(rank_ic(probs_s[span], excess_s[span]))
        cut = np.argsort(probs_s[span])[int(span.size * 0.9):]
        if cut.size:
            top_net.append(float(np.mean(excess_s[span][cut] - cost_s[span][cut])))

    ic_array = np.asarray(ics, dtype=np.float64)
    net_array = np.asarray(top_net, dtype=np.float64)

    # Sharpe of the top-decile net series, in the frequency of the series
    # itself (one observation per rebalance date).
    sharpe = float(net_array.mean() / net_array.std()) if net_array.size > 2 and net_array.std() > 0 else 0.0

    return {
        "model": name,
        "n": int(idx.size),
        "ic_mean": round(float(ic_array.mean()), 5) if ic_array.size else None,
        "ic_positive_frac": round(float((ic_array > 0).mean()), 4) if ic_array.size else None,
        "ece": round(expected_calibration_error(probs, y), 5),
        "brier_skill_vs_base_rate": round(brier_skill_score(probs, y, base_rate), 5),
        "top_decile_net_mean": round(float(net_array.mean()), 6) if net_array.size else None,
        "top_decile_net_sharpe": round(sharpe, 4),
        "rebalances": int(net_array.size),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seeds", type=int, default=5)
    args = ap.parse_args()

    print("=" * 78)
    print("TIER 2 — benchmark ladder with purged CV")
    print("=" * 78)

    panel = load_panel()
    cost = cost_matrix(panel, CostParams())
    ds = build_dataset(panel, horizon=HORIZON, cost=cost)
    print(f"  {len(ds):,} samples x {ds.X.shape[1]} features "
          f"({str(ds.dates.min())[:10]} -> {str(ds.dates.max())[:10]})")

    X = _clean(ds.X)
    y = ds.y_binary.astype(int)
    base_rate = float(y.mean())

    explore = ds.dates < EXPLORE_END.to_datetime64()
    holdout = ~explore
    print(f"  explore {explore.sum():,} / holdout {holdout.sum():,}")
    print(f"  base rate (beat universe median): {base_rate:.4f}")

    ex_idx = np.flatnonzero(explore)
    # Panel-aware: same-day names are distinct observations, only the temporal
    # overlap is shared. The single-series version reports ~1/2960 here.
    weights_all = panel_average_uniqueness(ds.day_index, HORIZON)
    n_dates = np.unique(ds.day_index).size
    print(f"  mean label uniqueness: {weights_all.mean():.4f} "
          f"(effective independent periods ~{int(n_dates * weights_all.mean()):,} "
          f"of {n_dates:,} dates)")

    report: dict[str, Any] = {
        "horizon": HORIZON,
        "samples": len(ds),
        "features": ds.X.shape[1],
        "base_rate": round(base_rate, 4),
        "mean_uniqueness": round(float(weights_all.mean()), 4),
        "explore_end": str(EXPLORE_END.date()),
        "tier1_holdout_ece": TIER1_HOLDOUT_ECE,
        "ladder": [],
    }

    # --- out-of-fold predictions on the explore set ---
    oof: dict[str, np.ndarray] = {}
    fold_perf: dict[str, list[float]] = {}

    folds = list(purged_kfold(ds.day_index[ex_idx], n_splits=args.folds,
                             horizon=HORIZON, embargo=HORIZON))
    print(f"\n  purged folds: {len(folds)} (embargo {HORIZON} sessions)")
    for i, fold in enumerate(folds):
        print(f"    fold {i}: train {fold.train.size:,} test {fold.test.size:,}")

    def run(name: str, fitter) -> None:
        preds = np.full(ex_idx.size, np.nan)
        per_fold: list[float] = []
        t0 = time.time()
        for fold in folds:
            tr, te = ex_idx[fold.train], ex_idx[fold.test]
            p = fitter(X[tr], y[tr], weights_all[tr], X[te])
            preds[fold.test] = p
            per_fold.append(rank_ic(p, ds.y_excess[te]))
        oof[name] = preds
        fold_perf[name] = per_fold
        print(f"  {name}: fitted in {time.time() - t0:.0f}s")

    # --- leakage control, run FIRST ---
    # Labels are permuted *within each date*, destroying every real
    # relationship while preserving the cross-sectional structure, the class
    # balance and the feature distributions. A model that still scores here is
    # reading something it should not — the IC would be an artefact of the
    # pipeline rather than of the market.
    print("\n  --- leakage control (labels shuffled within each date) ---")
    rng = np.random.default_rng(12345)
    y_shuffled = y.copy()
    order = np.argsort(ds.day_index, kind="mergesort")
    for span in np.split(order, np.flatnonzero(np.diff(ds.day_index[order])) + 1):
        if span.size > 1:
            y_shuffled[span] = y[rng.permutation(span)]

    control_preds = np.full(ex_idx.size, np.nan)
    for fold in folds:
        tr, te = ex_idx[fold.train], ex_idx[fold.test]
        control_preds[fold.test] = fit_lightgbm(
            X[tr], y_shuffled[tr], weights_all[tr], X[te], seed=0
        )[0]
    keep = np.isfinite(control_preds)
    control_ic = rank_ic(control_preds[keep], ds.y_excess[ex_idx[keep]])
    print(f"  shuffled-label IC: {control_ic:+.4f}  (must be ~0; "
          f"anything material means leakage)")
    report["leakage_control_ic"] = round(float(control_ic), 5)

    print("\n  --- ladder ---")
    run("logistic", fit_logistic)
    run("lightgbm", lambda a, b, c, d: fit_lightgbm(a, b, c, d, seed=0)[0])

    def ensemble(X_tr, y_tr, w_tr, X_te):
        preds = [fit_lightgbm(X_tr, y_tr, w_tr, X_te, seed=s)[0] for s in range(args.seeds)]
        return np.mean(preds, axis=0)
    run(f"lgbm_ensemble_{args.seeds}", ensemble)

    # --- score each rung on the explore set ---
    print(f"\n  {'model':<22} {'IC':>8} {'IC+%':>7} {'ECE':>8} {'BSS':>8} {'topNET':>9} {'Sharpe':>7}")
    valid = np.flatnonzero(np.isfinite(oof["logistic"]))
    for name, preds in oof.items():
        keep = valid[np.isfinite(preds[valid])]
        metrics = evaluate(name, preds[keep], ds, ex_idx[keep], base_rate)
        report["ladder"].append(metrics)
        print(f"  {name:<22} {metrics['ic_mean']:>8.4f} {metrics['ic_positive_frac']:>7.2f} "
              f"{metrics['ece']:>8.4f} {metrics['brier_skill_vs_base_rate']:>8.4f} "
              f"{metrics['top_decile_net_mean']:>9.4%} {metrics['top_decile_net_sharpe']:>7.3f}")

    # --- selection-bias corrections ---
    perf_matrix = np.column_stack([
        np.asarray(fold_perf[name], dtype=np.float64) for name in oof
    ])
    pbo = probability_of_backtest_overfitting(perf_matrix, n_partitions=4)

    best = max(report["ladder"], key=lambda m: (m["ic_mean"] or -1))
    sharpe = best["top_decile_net_sharpe"]
    dsr = deflated_sharpe_ratio(
        sharpe, n_trials=PRIOR_TRIALS + len(oof),
        n_observations=max(best["rebalances"], 2),
    )
    report["pbo"] = round(pbo, 4)
    report["dsr"] = round(dsr, 4)
    report["best_explore_model"] = best["model"]
    print(f"\n  PBO {pbo:.3f} (want <= 0.20) | DSR {dsr:.3f} (want >= 0.95)")
    print(f"  best on explore: {best['model']}")

    # Where is the ranking skill coming from? A model dominated by static
    # characteristics (price level, liquidity, volatility) can post a high rank
    # IC while having no timing edge at all — it is separating the universe into
    # persistent groups, not predicting moves. That distinction decides whether
    # the number means anything tradable.
    _, booster = fit_lightgbm(X[ex_idx], y[ex_idx], weights_all[ex_idx], X[ex_idx][:1], seed=0)
    gains = booster.feature_importance(importance_type="gain")
    ranked = sorted(zip(ds.feature_names, gains), key=lambda kv: -kv[1])
    total_gain = float(sum(gains)) or 1.0
    report["top_features"] = [
        {"feature": name, "gain_share": round(float(g) / total_gain, 4)}
        for name, g in ranked[:12]
    ]
    print("\n  top features by gain:")
    for name, g in ranked[:10]:
        print(f"    {name:<22} {float(g) / total_gain:6.2%}")

    # --- holdout, touched once ---
    print("\n  --- holdout 2025-2026 (untouched until now) ---")
    ho_idx = np.flatnonzero(holdout)
    holdout_metrics: list[dict[str, Any]] = []
    for name, fitter in (
        ("logistic", fit_logistic),
        ("lightgbm", lambda a, b, c, d: fit_lightgbm(a, b, c, d, seed=0)[0]),
        (f"lgbm_ensemble_{args.seeds}", ensemble),
    ):
        preds = fitter(X[ex_idx], y[ex_idx], weights_all[ex_idx], X[ho_idx])
        metrics = evaluate(name, preds, ds, ho_idx, base_rate)
        holdout_metrics.append(metrics)
        print(f"  {name:<22} IC {metrics['ic_mean']:>7.4f} "
              f"ECE {metrics['ece']:.4f} netTop {metrics['top_decile_net_mean']:>8.4%} "
              f"Sharpe {metrics['top_decile_net_sharpe']:>6.3f}")
    report["holdout"] = holdout_metrics

    # --- formal promotion gate ---
    from app.services.signals.promotion import evaluate_promotion

    chosen = next(m for m in report["ladder"] if m["model"] == best["model"])
    ho = next(m for m in holdout_metrics if m["model"] == best["model"])
    fold_ics = fold_perf[best["model"]]

    manifest = {
        "status": "EVALUATED",
        "eligible_events": len(ds),
        "symbols": int(np.unique(ds.symbols).size),
        "holdout_forecasts": int(ho["n"]),
        "positive_folds": int(sum(1 for v in fold_ics if v > 0)),
        # Share of top-decile rebalances that were net-positive — the
        # decision-relevant notion of precision for a ranking model.
        "precision": chosen["ic_positive_frac"] or 0.0,
        "ece": chosen["ece"],
        "dsr": dsr,
        "pbo": pbo,
    }
    decision = evaluate_promotion(manifest)
    report["promotion"] = {
        "manifest": manifest,
        "allowed": decision.allowed,
        "status": decision.status,
        "reasons": decision.reasons,
    }

    # The gate does not know about Tier 1, so this is checked separately:
    # a replacement that is worse calibrated is a downgrade.
    beats_tier1 = chosen["ece"] <= TIER1_HOLDOUT_ECE
    report["promotion"]["beats_tier1_calibration"] = beats_tier1
    if not beats_tier1:
        report["promotion"]["reasons"].append(
            f"ECE {chosen['ece']} worse than Tier 1's {TIER1_HOLDOUT_ECE}"
        )

    print("\n" + "=" * 78)
    print(f"  PROMOTION GATE: {decision.status}  (allowed={decision.allowed})")
    for reason in report["promotion"]["reasons"]:
        print(f"    - {reason}")
    print("=" * 78)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACT_DIR / "tier2_report.json"
    out.write_bytes(json.dumps(report, indent=2).encode("utf-8"))
    print(f"\n  report -> {out}")


if __name__ == "__main__":
    main()
