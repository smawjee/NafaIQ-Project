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
                          min_names_per_date: int = 30) -> RankingDataset:
    horizon_days = HORIZON_DAYS[horizon]
    stride = TRAINING_GRID_STRIDE[horizon]
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
