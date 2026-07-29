"""Signals V3.1 — cross-sectional labeling, splits, dataset, models, calibration, policy."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
from scipy.stats import rankdata

from app.services.signals_v2.constants import ONE_WAY_COST, ROUND_TRIP_COST
from app.services.signals_v2.labels import SignalLabel

PHASE0_THRESHOLDS: dict[str, tuple[float, float]] = {
    "5D": (0.01, 0.03), "20D": (0.02, 0.06), "60D": (0.04, 0.12),
}


def excess_to_label(excess: float, horizon: str) -> SignalLabel:
    band, strong = PHASE0_THRESHOLDS[horizon]
    if excess >= strong:
        return SignalLabel.STRONG_BUY
    if excess >= band:
        return SignalLabel.BUY
    if excess <= -strong:
        return SignalLabel.STRONG_SELL
    if excess <= -band:
        return SignalLabel.SELL
    return SignalLabel.HOLD


def relative_deciles(dates: list[date], excess: np.ndarray, *, n_bins: int = 10, min_names: int = 30) -> np.ndarray:
    out = np.full(len(dates), -1, dtype=np.int64)
    by_date: dict[date, list[int]] = defaultdict(list)
    for i, d in enumerate(dates):
        by_date[d].append(i)
    for idxs in by_date.values():
        if len(idxs) < min_names:
            continue
        arr = np.asarray(idxs)
        vals = excess[arr]
        ranks = rankdata(vals, method="average") - 1  # 0..n-1, ties averaged
        out[arr] = np.clip((ranks * n_bins) // len(idxs), 0, n_bins - 1).astype(np.int64)
    return out


def purged_date_splits(feature_dates: list[date], label_end_dates: list[date], *,
                       folds: int = 4, min_train_dates: int = 20) -> list[tuple[np.ndarray, np.ndarray]]:
    ford = np.asarray([d.toordinal() for d in feature_dates])
    lord = np.asarray([d.toordinal() for d in label_end_dates])
    unique = np.unique(ford)
    fold_size = len(unique) // (folds + 1)
    splits: list[tuple[np.ndarray, np.ndarray]] = []
    for fold in range(1, folds + 1):
        train_dates = unique[: fold_size * fold]
        if len(train_dates) < min_train_dates:
            continue
        test_dates = unique[fold_size * fold: fold_size * (fold + 1)]
        if len(test_dates) == 0:
            continue
        test_start = int(test_dates.min())
        # purge: training sample kept only if its label window closes before the test window opens
        train_mask = np.isin(ford, train_dates) & (lord < test_start)
        test_mask = np.isin(ford, test_dates)
        train_idx = np.flatnonzero(train_mask)
        test_idx = np.flatnonzero(test_mask)
        if len(train_idx) and len(test_idx):
            splits.append((train_idx, test_idx))
    if not splits:
        raise ValueError("not enough dated cross-sections for purged walk-forward")
    return splits


def three_layer_split(feature_dates: list[date], *, calibration_frac: float = 0.2,
                      holdout_frac: float = 0.2, min_support: dict | None = None) -> dict:
    ford = np.asarray([d.toordinal() for d in feature_dates])
    unique = np.unique(ford)
    n = len(unique)
    n_hold = int(n * holdout_frac)
    n_cal = int(n * calibration_frac)
    n_dev = n - n_cal - n_hold
    dev_dates, cal_dates, hold_dates = unique[:n_dev], unique[n_dev:n_dev + n_cal], unique[n_dev + n_cal:]
    support = min_support or {"dev": 30, "calibration": 10, "holdout": 10}
    if len(dev_dates) < support["dev"] or len(cal_dates) < support["calibration"] or len(hold_dates) < support["holdout"]:
        return {"status": "INCONCLUSIVE",
                "reason": f"insufficient dated support dev={len(dev_dates)} cal={len(cal_dates)} hold={len(hold_dates)}"}
    return {
        "dev": np.flatnonzero(np.isin(ford, dev_dates)),
        "calibration": np.flatnonzero(np.isin(ford, cal_dates)),
        "holdout": np.flatnonzero(np.isin(ford, hold_dates)),
    }


from app.services.signals_v2.constants import (
    MAX_ENTRY_DELAY_TRADING_DAYS, MAX_FEATURE_LOOKBACK, MIN_REQUIRED_BARS, TRAINING_GRID_STRIDE,
)
from app.services.signals_v2.features import build_feature_frame, compute_feature_snapshot
from app.services.signals_v2.technical_rating import compute_technical_rating
from app.services.signals_v2.training import (
    HORIZON_DAYS, SIGNAL_FEATURES_V3, Dataset, _kse_until, _parse_date, _prepare_kse_lookup,
    has_core_features, vectorize_v3,
)


@dataclass(frozen=True)
class RankingDataset:
    X: np.ndarray
    y: np.ndarray
    dates: list[date]              # = feature_dates (kept as `dates` for Dataset compatibility)
    symbols: list[str]
    forward_returns: np.ndarray
    benchmark_forward_returns: np.ndarray
    technical_labels: np.ndarray
    feature_names: list[str]
    feature_dates: list[date]
    entry_dates: list[date]
    exit_dates: list[date]
    sectors: list[str]

    def as_dataset(self) -> Dataset:
        return Dataset(self.X, self.y, self.dates, self.symbols, self.forward_returns,
                       self.benchmark_forward_returns, self.technical_labels, self.feature_names)


def eligible_universe(rows_by_symbol: dict[str, list[dict[str, Any]]], as_of: date, *,
                      min_bars: int = MIN_REQUIRED_BARS, turnover_floor: float = 1_000_000) -> set[str]:
    out: set[str] = set()
    for sym, rows in rows_by_symbol.items():
        upto = [r for r in rows if _parse_date(r.get("date")) <= as_of]
        if len(upto) < min_bars:
            continue
        recent = upto[-20:]
        if any(float(r.get("close") or 0) <= 0 for r in recent):
            continue
        turnover = np.median([float(r.get("close") or 0) * float(r.get("volume") or 0) for r in recent])
        if turnover_floor and turnover < turnover_floor:
            continue
        out.add(sym.upper())
    return out


def _valid_entry_index(close: np.ndarray, volume: np.ndarray, t: int, max_delay: int) -> int | None:
    for j in range(t + 1, min(len(close), t + 1 + max_delay + 1)):
        if close[j] > 0 and volume[j] > 0:
            return j
    return None


def build_ranking_dataset(*, histories: dict[str, list[dict[str, Any]]],
                          fundamentals: dict[str, dict[str, Any]], profiles: dict[str, dict[str, Any]],
                          kse_rows: list[dict[str, Any]], horizon: str,
                          corp_action_events: dict[str, list[str]] | None = None,
                          min_names_per_date: int = 30,
                          grid_stride: int | None = None) -> RankingDataset:
    horizon_days = HORIZON_DAYS[horizon]
    stride = grid_stride if grid_stride is not None else TRAINING_GRID_STRIDE[horizon]
    kse_sorted, kse_ordinals = _prepare_kse_lookup(kse_rows)
    kse_close = np.asarray([float(r.get("close") or 0) for r in kse_sorted], dtype=np.float64)
    kse_date_to_idx = {_parse_date(r.get("date")): i for i, r in enumerate(kse_sorted)}
    grid = [_parse_date(kse_sorted[i].get("date")) for i in range(0, len(kse_sorted), stride)]
    events = {s.upper(): {date.fromisoformat(d) for d in ds} for s, ds in (corp_action_events or {}).items()}

    xs, fdates, edates, xdates, syms, sectors = [], [], [], [], [], []
    fwd, bench, tech = [], [], []

    for sym, raw in histories.items():
        rows = sorted(raw, key=lambda r: str(r.get("date")))
        if len(rows) < MIN_REQUIRED_BARS + horizon_days + MAX_ENTRY_DELAY_TRADING_DAYS:
            continue
        close = np.asarray([float(r.get("close") or 0) for r in rows], dtype=np.float64)
        volume = np.asarray([float(r.get("volume") or 0) for r in rows], dtype=np.float64)
        rdates = [_parse_date(r.get("date")) for r in rows]
        idx_by_date = {d: i for i, d in enumerate(rdates)}
        sym_events = events.get(sym.upper(), set())
        sector = str((profiles.get(sym) or {}).get("sector") or "UNKNOWN")
        for d in grid:
            t = idx_by_date.get(d)
            if t is None or t < MIN_REQUIRED_BARS - 1:
                continue
            entry_i = _valid_entry_index(close, volume, t, MAX_ENTRY_DELAY_TRADING_DAYS)
            if entry_i is None or entry_i + horizon_days >= len(rows):
                continue
            exit_i = entry_i + horizon_days
            if close[entry_i] <= 0 or close[exit_i] <= 0:
                continue
            feature_start = rdates[max(0, t - MAX_FEATURE_LOOKBACK)]
            # contamination: any flagged event within [feature_start, exit_date]
            if sym_events and any(feature_start <= ev <= rdates[exit_i] for ev in sym_events):
                continue
            frame = build_feature_frame(symbol=sym, ohlcv_rows=rows[: t + 1],
                                        fundamentals={}, profile=profiles.get(sym, {}),
                                        kse_rows=_kse_until(kse_sorted, kse_ordinals, rows[t].get("date")))
            features = compute_feature_snapshot(frame)
            if not has_core_features(features):
                continue
            vector = vectorize_v3(features, SIGNAL_FEATURES_V3)
            # benchmark on identical entry/exit dates
            bi = kse_date_to_idx.get(rdates[entry_i])
            xi = kse_date_to_idx.get(rdates[exit_i])
            if bi is None or xi is None or kse_close[bi] <= 0:
                continue
            xs.append(vector.tolist())
            fdates.append(d); edates.append(rdates[entry_i]); xdates.append(rdates[exit_i])
            syms.append(sym); sectors.append(sector)
            fwd.append(float(close[exit_i] / close[entry_i] - 1))
            bench.append(float(kse_close[xi] / kse_close[bi] - 1))
            tech.append(compute_technical_rating(features).signal.value)

    if not xs:
        empty = np.empty((0, len(SIGNAL_FEATURES_V3)))
        return RankingDataset(empty, np.asarray([], dtype=object), [], [], np.asarray([]),
                              np.asarray([]), np.asarray([], dtype=object), SIGNAL_FEATURES_V3, [], [], [], [])

    fwd_a = np.asarray(fwd); bench_a = np.asarray(bench)
    dec = relative_deciles(fdates, fwd_a - bench_a, min_names=min_names_per_date)
    keep = np.flatnonzero(dec >= 0)
    k = keep
    return RankingDataset(
        X=np.asarray(xs, dtype=np.float64)[k],
        y=np.asarray([str(int(dec[i])) for i in k], dtype=object),
        dates=[fdates[i] for i in k], symbols=[syms[i] for i in k],
        forward_returns=fwd_a[k], benchmark_forward_returns=bench_a[k],
        technical_labels=np.asarray(tech, dtype=object)[k], feature_names=SIGNAL_FEATURES_V3,
        feature_dates=[fdates[i] for i in k], entry_dates=[edates[i] for i in k],
        exit_dates=[xdates[i] for i in k], sectors=[sectors[i] for i in k],
    )


DEFAULT_RANKER_CONFIGS: list[dict] = [
    {"name": "lr05_d6", "learning_rate": 0.05, "max_depth": 6, "n_estimators": 400},
    {"name": "lr03_d4", "learning_rate": 0.03, "max_depth": 4, "n_estimators": 600},
    {"name": "lr05_d3", "learning_rate": 0.05, "max_depth": 3, "n_estimators": 500},
]

BUY_PCT = 0.90
STRONG_BUY_PCT = 0.97
SELL_PCT = 0.10
STRONG_SELL_PCT = 0.03


@dataclass(frozen=True)
class RankerOOSPrediction:
    sample_index: int
    symbol: str
    sector: str
    feature_date: date
    entry_date: date
    exit_date: date
    horizon: str
    rank_score: float
    percentile: float
    forward_return: float
    benchmark_return: float
    excess_return: float
    technical_label: str


def _ndcg_at_k(excess_sorted_by_score_desc: np.ndarray, k: int) -> float:
    # relevance = positive excess; simple gain = max(excess,0)
    gains = np.maximum(excess_sorted_by_score_desc, 0.0)
    k = min(k, len(gains))
    if k == 0:
        return 0.0
    discounts = 1.0 / np.log2(np.arange(2, k + 2))
    dcg = float(np.sum(gains[:k] * discounts))
    ideal = np.sort(np.maximum(excess_sorted_by_score_desc, 0.0))[::-1]
    idcg = float(np.sum(ideal[:k] * discounts))
    return dcg / idcg if idcg > 0 else 0.0


def train_ranker(ds: "RankingDataset", *, horizon: str, split_indices: np.ndarray | None = None,
                 configs: list[dict] | None = None, folds: int = 4, random_state: int = 42) -> dict:
    import xgboost
    from scipy.stats import spearmanr

    configs = configs or DEFAULT_RANKER_CONFIGS
    sel = np.asarray(split_indices if split_indices is not None else np.arange(len(ds.y)), dtype=np.int64)
    order = np.lexsort((np.asarray([ds.symbols[i] for i in sel], dtype=object),
                        np.asarray([ds.feature_dates[i].toordinal() for i in sel])))
    orig = sel[order]                       # stable original-dataset indices, date-sorted
    X = ds.X[orig]
    y = np.asarray([int(v) for v in ds.y[orig]], dtype=np.int64)
    fdates = [ds.feature_dates[i] for i in orig]
    edates = [ds.entry_dates[i] for i in orig]
    xdates = [ds.exit_dates[i] for i in orig]
    syms = [ds.symbols[i] for i in orig]
    secs = [ds.sectors[i] for i in orig]
    tech = ds.technical_labels[orig]
    fwd = ds.forward_returns[orig]
    bench = ds.benchmark_forward_returns[orig]
    excess = fwd - bench
    qid = np.asarray([d.toordinal() for d in fdates], dtype=np.int64)
    splits = purged_date_splits(fdates, xdates, folds=folds)

    def _make(cfg):
        return xgboost.XGBRanker(objective="rank:ndcg", learning_rate=cfg["learning_rate"],
                                 max_depth=cfg["max_depth"], n_estimators=cfg["n_estimators"],
                                 subsample=0.85, colsample_bytree=0.85, random_state=random_state)

    best = None
    daily_by_config: dict[str, dict[date, float]] = {}
    for cfg in configs:
        oos: list[RankerOOSPrediction] = []
        daily_top: dict[date, float] = {}
        ics, ndcg5, ndcg10, p5, p10, fold_positive = [], [], [], [], [], []
        for train_idx, test_idx in splits:
            model = _make(cfg)
            model.fit(X[train_idx], y[train_idx], qid=qid[train_idx])
            scores = model.predict(X[test_idx])
            fold_daily: list[float] = []
            for od in np.unique(qid[test_idx]):
                mask = qid[test_idx] == od
                s = scores[mask]
                if len(s) < 3:
                    continue
                pct = (rankdata(s, method="average") - 1) / (len(s) - 1)
                day_idx = test_idx[mask]        # indices into the sorted arrays
                exc = excess[day_idx]
                sd = np.argsort(s)[::-1]
                ic = spearmanr(pct, exc).statistic
                if np.isfinite(ic):
                    ics.append(float(ic))
                ndcg5.append(_ndcg_at_k(exc[sd], 5)); ndcg10.append(_ndcg_at_k(exc[sd], 10))
                p5.append(float(np.mean(exc[sd][:5] > 0))); p10.append(float(np.mean(exc[sd][:10] > 0)))
                top = exc[pct >= BUY_PCT]
                d0 = fdates[day_idx[0]]
                val = float(np.mean(top) - ROUND_TRIP_COST) if len(top) else 0.0
                daily_top[d0] = val
                fold_daily.append(val)
                for local, ti in enumerate(day_idx):
                    oos.append(RankerOOSPrediction(
                        sample_index=int(orig[ti]), symbol=syms[ti], sector=secs[ti],
                        feature_date=fdates[ti], entry_date=edates[ti], exit_date=xdates[ti],
                        horizon=horizon, rank_score=float(s[local]), percentile=float(pct[local]),
                        forward_return=float(fwd[ti]), benchmark_return=float(bench[ti]),
                        excess_return=float(exc[local]), technical_label=str(tech[ti])))
            if fold_daily:
                fold_positive.append(1 if float(np.mean(fold_daily)) > 0 else 0)
        top_excess = float(np.mean(list(daily_top.values()))) if daily_top else -1.0
        daily_by_config[cfg["name"]] = daily_top
        cand = {"config": cfg, "oos": oos,
                "metrics": {"daily_rank_ic": round(float(np.mean(ics)) if ics else 0.0, 4),
                            "ndcg_at_5": round(float(np.mean(ndcg5)) if ndcg5 else 0.0, 4),
                            "ndcg_at_10": round(float(np.mean(ndcg10)) if ndcg10 else 0.0, 4),
                            "precision_at_5": round(float(np.mean(p5)) if p5 else 0.0, 4),
                            "precision_at_10": round(float(np.mean(p10)) if p10 else 0.0, 4),
                            "top_decile_excess_after_cost": round(top_excess, 4),
                            "folds_positive_frac": round(float(np.mean(fold_positive)) if fold_positive else 0.0, 4),
                            "n_dates": int(len(np.unique(qid))), "samples": int(len(y))},
                "top_excess": top_excess}
        if best is None or cand["top_excess"] > best["top_excess"]:
            best = cand

    final = _make(best["config"])
    final.fit(X, y, qid=qid)
    # dates x configs matrix of daily after-cost top-decile excess (PBO input: every trial, not just the winner)
    all_dates = sorted(set().union(*[set(d) for d in daily_by_config.values()])) if daily_by_config else []
    matrix = [[daily_by_config[c["name"]].get(d, 0.0) for c in configs] for d in all_dates]
    best["metrics"]["n_trials"] = len(configs)
    return {"model": final, "config": best["config"], "oos": best["oos"], "metrics": best["metrics"],
            "trial_matrix": {"dates": [d.isoformat() for d in all_dates],
                             "configs": [c["name"] for c in configs],
                             "matrix": matrix}}


@dataclass(frozen=True)
class AbsoluteOOSPrediction:
    sample_index: int
    symbol: str
    feature_date: date
    horizon: str
    absolute_class_score: float
    absolute_regression_score: float


@dataclass(frozen=True)
class CombinedOOSPrediction:
    sample_index: int
    symbol: str
    sector: str
    feature_date: date
    entry_date: date
    exit_date: date
    horizon: str
    rank_score: float
    percentile: float
    forward_return: float
    benchmark_return: float
    excess_return: float
    technical_label: str
    absolute_class_score: float
    absolute_regression_score: float


def _abs_model_factory():
    try:
        import lightgbm
        clf = lightgbm.LGBMClassifier(n_estimators=400, learning_rate=0.04, num_leaves=31,
                                      subsample=0.85, colsample_bytree=0.85, random_state=42, verbose=-1)
        reg = lightgbm.LGBMRegressor(n_estimators=400, learning_rate=0.04, num_leaves=31,
                                     subsample=0.85, colsample_bytree=0.85, random_state=42, verbose=-1)
        return clf, reg
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
        return (HistGradientBoostingClassifier(max_iter=300, learning_rate=0.045, random_state=42),
                HistGradientBoostingRegressor(max_iter=300, learning_rate=0.045, random_state=42))


def train_absolute_model(ds: "RankingDataset", *, horizon: str,
                         split_indices: np.ndarray | None = None, folds: int = 4) -> dict:
    import copy

    sel = np.asarray(split_indices if split_indices is not None else np.arange(len(ds.y)), dtype=np.int64)
    X = ds.X[sel]
    fdates = [ds.feature_dates[i] for i in sel]
    syms = [ds.symbols[i] for i in sel]
    net = ds.forward_returns[sel] - ROUND_TRIP_COST
    y_pos = (net > 0).astype(np.int64)
    label_end = [ds.exit_dates[i] for i in sel]
    splits = purged_date_splits(fdates, label_end, folds=folds)
    clf_proto, reg_proto = _abs_model_factory()

    oos: list[AbsoluteOOSPrediction] = []
    for train_idx, test_idx in splits:
        clf = copy.deepcopy(clf_proto); reg = copy.deepcopy(reg_proto)
        clf.fit(X[train_idx], y_pos[train_idx]); reg.fit(X[train_idx], net[train_idx])
        proba = clf.predict_proba(X[test_idx])[:, list(clf.classes_).index(1)] \
            if 1 in list(clf.classes_) else np.zeros(len(test_idx))
        preds = reg.predict(X[test_idx])
        for local, ti in enumerate(test_idx):
            oos.append(AbsoluteOOSPrediction(int(sel[ti]), syms[ti], fdates[ti], horizon,
                                             float(proba[local]), float(preds[local])))
    clf_final = copy.deepcopy(clf_proto); reg_final = copy.deepcopy(reg_proto)
    clf_final.fit(X, y_pos); reg_final.fit(X, net)
    return {"clf": clf_final, "reg": reg_final, "oos": oos}


def join_oos(ranker_oos: list[RankerOOSPrediction],
             absolute_oos: list[AbsoluteOOSPrediction]) -> list[CombinedOOSPrediction]:
    abs_by_key = {(a.sample_index, a.symbol, a.feature_date, a.horizon): a for a in absolute_oos}
    combined: list[CombinedOOSPrediction] = []
    for r in ranker_oos:
        key = (r.sample_index, r.symbol, r.feature_date, r.horizon)
        a = abs_by_key.get(key)
        if a is None:
            raise ValueError(f"no absolute OOS record for ranker sample {key}")
        combined.append(CombinedOOSPrediction(
            r.sample_index, r.symbol, r.sector, r.feature_date, r.entry_date, r.exit_date, r.horizon,
            r.rank_score, r.percentile, r.forward_return, r.benchmark_return, r.excess_return,
            r.technical_label, a.absolute_class_score, a.absolute_regression_score))
    return combined


MIN_CAL_SUPPORT = 200


@dataclass(frozen=True)
class CalibratedPrediction:
    raw: CombinedOOSPrediction
    p_beat_market: float
    p_positive_absolute: float
    expected_excess_net: float
    expected_absolute_net: float
    calibration_support: int


@dataclass
class DualCalibrator:
    beat_iso: Any
    pos_iso: Any
    support: int

    @classmethod
    def fit(cls, combined: list[CombinedOOSPrediction]) -> "DualCalibrator":
        from sklearn.isotonic import IsotonicRegression

        pct = np.asarray([c.percentile for c in combined])
        beat = np.asarray([1 if c.excess_return > 0 else 0 for c in combined], dtype=np.float64)
        cls_score = np.asarray([c.absolute_class_score for c in combined])
        pos = np.asarray([1 if (c.forward_return - ROUND_TRIP_COST) > 0 else 0 for c in combined], dtype=np.float64)
        beat_iso = pos_iso = None
        if len(combined) >= MIN_CAL_SUPPORT:
            beat_iso = IsotonicRegression(out_of_bounds="clip").fit(pct, beat)
            pos_iso = IsotonicRegression(out_of_bounds="clip").fit(cls_score, pos)
        return cls(beat_iso=beat_iso, pos_iso=pos_iso, support=len(combined))

    def apply(self, pred: CombinedOOSPrediction) -> CalibratedPrediction:
        p_beat = float(self.beat_iso.predict([pred.percentile])[0]) if self.beat_iso is not None else pred.percentile
        p_pos = float(self.pos_iso.predict([pred.absolute_class_score])[0]) if self.pos_iso is not None else pred.absolute_class_score
        return CalibratedPrediction(
            raw=pred, p_beat_market=round(p_beat, 4), p_positive_absolute=round(p_pos, 4),
            expected_excess_net=round(pred.excess_return - ROUND_TRIP_COST, 4),
            expected_absolute_net=round(pred.absolute_regression_score, 4),
            calibration_support=self.support)


def calibration_report(combined: list[CombinedOOSPrediction], calibrator: DualCalibrator) -> dict:
    def _brier_ece(prob: np.ndarray, actual: np.ndarray) -> tuple[float, float]:
        brier = float(np.mean((prob - actual) ** 2)) if len(prob) else 0.0
        edges = np.linspace(0, 1, 11)
        ece = 0.0
        for a, b in zip(edges[:-1], edges[1:]):
            m = (prob >= a) & (prob < b if b < 1 else prob <= b)
            if np.any(m):
                ece += float(np.mean(m)) * abs(float(np.mean(prob[m])) - float(np.mean(actual[m])))
        return round(brier, 4), round(ece, 4)

    cals = [calibrator.apply(c) for c in combined]
    beat_p = np.asarray([c.p_beat_market for c in cals])
    beat_a = np.asarray([1 if c.raw.excess_return > 0 else 0 for c in cals], dtype=np.float64)
    pos_p = np.asarray([c.p_positive_absolute for c in cals])
    pos_a = np.asarray([1 if (c.raw.forward_return - ROUND_TRIP_COST) > 0 else 0 for c in cals], dtype=np.float64)
    b_brier, b_ece = _brier_ece(beat_p, beat_a)
    p_brier, p_ece = _brier_ece(pos_p, pos_a)
    return {"beat_market": {"brier": b_brier, "ece": b_ece},
            "positive_absolute": {"brier": p_brier, "ece": p_ece},
            "support": calibrator.support}


@dataclass(frozen=True)
class PolicyConfig:
    buy_pct: float = 0.90
    strong_buy_pct: float = 0.97
    sell_pct: float = 0.10
    strong_sell_pct: float = 0.03
    min_p_beat: float = 0.55
    min_p_positive: float = 0.55


DEFAULT_POLICY = PolicyConfig()


def rank_to_signal(*, percentile: float, p_beat_market: float, expected_excess_net: float,
                   p_positive_absolute: float, expected_absolute_net: float,
                   data_quality_ok: bool, liquidity_ok: bool, risk_ok: bool,
                   calibration_support_ok: bool, config: PolicyConfig = DEFAULT_POLICY) -> SignalLabel:
    if not (data_quality_ok and calibration_support_ok):
        return SignalLabel.NO_SIGNAL
    # BUY side: rank AND relative AND absolute AND conviction AND tradability
    if percentile >= config.buy_pct and liquidity_ok and risk_ok:
        if (p_beat_market >= config.min_p_beat and expected_excess_net > 0
                and p_positive_absolute >= config.min_p_positive and expected_absolute_net > 0):
            return SignalLabel.STRONG_BUY if percentile >= config.strong_buy_pct else SignalLabel.BUY
        return SignalLabel.HOLD
    # SELL side: bottom rank AND negative absolute expectation AND low P(positive)
    if percentile <= config.sell_pct:
        if expected_absolute_net < 0 and p_positive_absolute < (1 - config.min_p_positive):
            return SignalLabel.STRONG_SELL if percentile <= config.strong_sell_pct else SignalLabel.SELL
        return SignalLabel.HOLD          # underperformer, not a faller
    return SignalLabel.HOLD


def policy_metrics(calibrated: list["CalibratedPrediction"], config: PolicyConfig = DEFAULT_POLICY) -> dict:
    from collections import Counter

    labels, buys_net, sectors_top = [], [], []
    for c in calibrated:
        lab = rank_to_signal(percentile=c.raw.percentile, p_beat_market=c.p_beat_market,
                             expected_excess_net=c.expected_excess_net,
                             p_positive_absolute=c.p_positive_absolute,
                             expected_absolute_net=c.expected_absolute_net,
                             data_quality_ok=True, liquidity_ok=True, risk_ok=True,
                             calibration_support_ok=c.calibration_support >= MIN_CAL_SUPPORT, config=config)
        labels.append(lab.value)
        if lab in (SignalLabel.BUY, SignalLabel.STRONG_BUY):
            buys_net.append(c.raw.forward_return - ROUND_TRIP_COST)
            sectors_top.append(c.raw.sector)
    buys = np.asarray(buys_net)
    sec_counts = Counter(sectors_top)
    total = sum(sec_counts.values()) or 1
    hhi = sum((n / total) ** 2 for n in sec_counts.values())
    return {
        "coverage": round(float(np.mean([l in ("BUY", "STRONG_BUY") for l in labels])), 4),
        "large_loss_rate": round(float(np.mean(buys < -0.02)) if len(buys) else 0.0, 4),
        "buy_hit_rate": round(float(np.mean(buys > 0)) if len(buys) else 0.0, 4),
        "sector_hhi": round(hhi, 4),
        "top_sector_share": round(max(sec_counts.values()) / total, 4) if sec_counts else 0.0,
        "n_buys": int(len(buys)),
    }


def score_layer(ranker_model: Any, clf: Any, reg: Any, ds: "RankingDataset",
                indices: np.ndarray, horizon: str) -> list[CombinedOOSPrediction]:
    """Score a later time-layer (calibration/holdout) with already-fitted models.

    Returns one CombinedOOSPrediction per sample with percentiles computed within
    each feature date's cross-section. The models must have been fitted strictly
    before this layer's dates (three_layer_split guarantees the ordering).
    """
    idx = np.asarray(indices, dtype=np.int64)
    if len(idx) == 0:
        return []
    X = ds.X[idx]
    scores = np.asarray(ranker_model.predict(X), dtype=np.float64)
    proba = clf.predict_proba(X)[:, list(clf.classes_).index(1)] \
        if 1 in list(clf.classes_) else np.zeros(len(idx))
    preds = np.asarray(reg.predict(X), dtype=np.float64)

    by_date: dict[date, list[int]] = defaultdict(list)
    for local, i in enumerate(idx):
        by_date[ds.feature_dates[int(i)]].append(local)

    out: list[CombinedOOSPrediction] = []
    for locs in by_date.values():
        larr = np.asarray(locs)
        s = scores[larr]
        pct = (rankdata(s, method="average") - 1) / (len(s) - 1) if len(s) > 1 else np.asarray([0.5])
        for k, local in enumerate(larr):
            i = int(idx[local])
            out.append(CombinedOOSPrediction(
                sample_index=i, symbol=ds.symbols[i], sector=ds.sectors[i],
                feature_date=ds.feature_dates[i], entry_date=ds.entry_dates[i],
                exit_date=ds.exit_dates[i], horizon=horizon,
                rank_score=float(s[k]), percentile=float(pct[k]),
                forward_return=float(ds.forward_returns[i]),
                benchmark_return=float(ds.benchmark_forward_returns[i]),
                excess_return=float(ds.forward_returns[i] - ds.benchmark_forward_returns[i]),
                technical_label=str(ds.technical_labels[i]),
                absolute_class_score=float(proba[local]),
                absolute_regression_score=float(preds[local])))
    return out
