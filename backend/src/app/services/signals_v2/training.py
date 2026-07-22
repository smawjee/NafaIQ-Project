from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

import numpy as np
from sklearn.metrics import accuracy_score, precision_score
from sklearn.preprocessing import StandardScaler

from app.services.signals_v2.backtest import triple_barrier_labels
from app.services.signals_v2.features import build_feature_frame, compute_feature_snapshot
from app.services.signals_v2.labels import SignalLabel
from app.services.signals_v2.technical_rating import compute_technical_rating

HORIZON_DAYS = {"5D": 5, "20D": 20, "60D": 60}

SIGNAL_FEATURES = [
    "ret_1d",
    "ret_3d",
    "ret_5d",
    "ret_10d",
    "ret_20d",
    "ret_60d",
    "volatility_20d",
    "atr14_pct",
    "volume_vs_20d",
    "dist_52w_high",
    "dist_52w_low",
    "rsi14",
    "macd_hist",
    "stochastic_k",
    "williams_r14",
    "mfi14",
    "bb_position",
    "obv_20d_slope",
    "roc10",
    "cci20",
    "relative_strength_kse20",
    "price_sma10_ratio",
    "price_sma20_ratio",
    "price_sma30_ratio",
    "price_sma50_ratio",
    "price_sma100_ratio",
    "price_sma200_ratio",
    "price_ema10_ratio",
    "price_ema20_ratio",
    "price_ema30_ratio",
    "price_ema50_ratio",
    "price_ema100_ratio",
    "price_ema200_ratio",
    "pe",
    "pb",
    "roe",
    "div_yield",
    "payout",
]

CLASS_ORDER = [
    SignalLabel.STRONG_SELL.value,
    SignalLabel.SELL.value,
    SignalLabel.HOLD.value,
    SignalLabel.BUY.value,
    SignalLabel.STRONG_BUY.value,
]


@dataclass(frozen=True)
class Dataset:
    X: np.ndarray
    y: np.ndarray
    dates: list[date]
    symbols: list[str]
    forward_returns: np.ndarray
    benchmark_forward_returns: np.ndarray
    technical_labels: np.ndarray
    feature_names: list[str]


@dataclass(frozen=True)
class ProbabilityCalibrator:
    bins: list[float]
    values: list[float]
    global_accuracy: float

    @classmethod
    def fit(cls, probabilities: np.ndarray, y_true: np.ndarray) -> "ProbabilityCalibrator":
        if probabilities.size == 0 or len(y_true) == 0:
            return cls(bins=[0.0, 1.0], values=[0.5], global_accuracy=0.5)
        confidence = np.max(probabilities, axis=1)
        predicted = np.argmax(probabilities, axis=1)
        actual = np.asarray([CLASS_ORDER.index(str(label)) if str(label) in CLASS_ORDER else -1 for label in y_true])
        correct = predicted == actual
        edges = np.linspace(0, 1, 11)
        values: list[float] = []
        global_acc = float(np.mean(correct)) if len(correct) else 0.5
        for start, end in zip(edges[:-1], edges[1:]):
            mask = (confidence >= start) & (confidence < end if end < 1 else confidence <= end)
            if np.any(mask):
                empirical = float(np.mean(correct[mask]))
                midpoint = float((start + end) / 2)
                values.append(round(empirical * 0.75 + midpoint * 0.25, 4))
            else:
                values.append(round(global_acc, 4))
        return cls(bins=[round(float(x), 4) for x in edges.tolist()], values=values, global_accuracy=round(global_acc, 4))

    def transform(self, probabilities: np.ndarray) -> np.ndarray:
        if probabilities.size == 0:
            return probabilities
        out = probabilities.astype(np.float64, copy=True)
        for row in out:
            top = int(np.argmax(row))
            raw = float(row[top])
            calibrated = self._calibrated_confidence(raw)
            remainder = max(0.0, 1.0 - calibrated)
            non_top_sum = float(np.sum(row) - raw)
            if non_top_sum > 0:
                for i in range(len(row)):
                    if i != top:
                        row[i] = row[i] / non_top_sum * remainder
            else:
                fill = remainder / max(1, len(row) - 1)
                for i in range(len(row)):
                    if i != top:
                        row[i] = fill
            row[top] = calibrated
        return out

    def _calibrated_confidence(self, value: float) -> float:
        for idx, (start, end) in enumerate(zip(self.bins[:-1], self.bins[1:])):
            if start <= value < end or (idx == len(self.values) - 1 and value <= end):
                return max(0.01, min(0.99, self.values[idx]))
        return max(0.01, min(0.99, self.global_accuracy))


def build_dataset(
    *,
    histories: dict[str, list[dict[str, Any]]],
    fundamentals: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    kse_rows: list[dict[str, Any]],
    horizon: str,
    min_history: int = 80,
    max_rows_per_symbol: int = 420,
    sample_stride: int = 20,
) -> Dataset:
    horizon_days = HORIZON_DAYS[horizon]
    xs: list[list[float]] = []
    ys: list[str] = []
    dates: list[date] = []
    symbols: list[str] = []
    returns: list[float] = []
    benchmark_returns: list[float] = []
    technical_labels: list[str] = []
    kse_sorted, kse_ordinals = _prepare_kse_lookup(kse_rows)

    for sym, raw_rows in histories.items():
        rows = sorted(raw_rows, key=lambda r: str(r.get("date")))
        if max_rows_per_symbol > 0:
            rows = rows[-max_rows_per_symbol:]
        if len(rows) < min_history + horizon_days:
            continue
        close = np.asarray([float(r.get("close") or 0) for r in rows], dtype=np.float64)
        atr_proxy = _rolling_atr_pct(rows)
        labels = {item.index: item for item in triple_barrier_labels(close, atr_proxy, horizon=horizon_days)}

        for i in range(min_history - 1, len(rows) - horizon_days, max(1, sample_stride)):
            label = labels.get(i)
            if label is None:
                continue
            frame = build_feature_frame(
                symbol=sym,
                ohlcv_rows=rows[: i + 1],
                fundamentals=fundamentals.get(sym, {}),
                profile=profiles.get(sym, {}),
                kse_rows=_kse_until(kse_sorted, kse_ordinals, rows[i].get("date")),
            )
            features = compute_feature_snapshot(frame)
            vector = _vectorize(features, SIGNAL_FEATURES)
            if not np.isfinite(vector).all():
                continue
            technical = compute_technical_rating(features)
            xs.append(vector.tolist())
            ys.append(label.label.value)
            dates.append(frame.dates[-1])
            symbols.append(sym)
            returns.append(label.forward_return)
            benchmark_returns.append(_benchmark_forward_return(kse_sorted, kse_ordinals, rows[i].get("date"), horizon_days))
            technical_labels.append(technical.signal.value)

    if not xs:
        return Dataset(
            X=np.empty((0, len(SIGNAL_FEATURES))),
            y=np.asarray([], dtype=object),
            dates=[],
            symbols=[],
            forward_returns=np.asarray([], dtype=np.float64),
            benchmark_forward_returns=np.asarray([], dtype=np.float64),
            technical_labels=np.asarray([], dtype=object),
            feature_names=SIGNAL_FEATURES,
        )
    return Dataset(
        X=np.asarray(xs, dtype=np.float64),
        y=np.asarray(ys, dtype=object),
        dates=dates,
        symbols=symbols,
        forward_returns=np.asarray(returns, dtype=np.float64),
        benchmark_forward_returns=np.asarray(benchmark_returns, dtype=np.float64),
        technical_labels=np.asarray(technical_labels, dtype=object),
        feature_names=SIGNAL_FEATURES,
    )


def evaluate_walk_forward(
    *,
    X: np.ndarray,
    y: np.ndarray,
    dates: list[date],
    forward_returns: np.ndarray,
    model_factory,
    benchmark_forward_returns: np.ndarray | None = None,
    technical_labels: np.ndarray | None = None,
    scaler: bool = False,
    folds: int = 4,
    gap: int = 20,
) -> tuple[dict[str, Any], Any, StandardScaler | None, ProbabilityCalibrator | None]:
    order = np.argsort(np.asarray([d.toordinal() for d in dates]))
    X, y, forward_returns = X[order], y[order], forward_returns[order]
    benchmark = benchmark_forward_returns[order] if benchmark_forward_returns is not None else None
    technical = technical_labels[order] if technical_labels is not None else None
    splits = _walk_forward_splits(len(y), folds=folds, gap=gap)
    fold_metrics: list[dict[str, Any]] = []
    all_pred: list[str] = []
    all_true: list[str] = []
    all_returns: list[float] = []
    all_benchmark_returns: list[float] = []
    all_probabilities: list[np.ndarray] = []

    for fold, (train_idx, test_idx) in enumerate(splits, start=1):
        X_train, X_test = X[train_idx], X[test_idx]
        scaler_obj = StandardScaler() if scaler else None
        if scaler_obj is not None:
            X_train = scaler_obj.fit_transform(X_train)
            X_test = scaler_obj.transform(X_test)
        model = model_factory()
        weights = sample_weights(y[train_idx])
        model.fit(X_train, y[train_idx], sample_weight=weights)
        pred = model.predict(X_test)
        fold_benchmark = benchmark[test_idx] if benchmark is not None else None
        fold_result = _metrics(y[test_idx], pred, forward_returns[test_idx], fold_benchmark)
        fold_result["fold"] = fold
        fold_result["train_samples"] = int(len(train_idx))
        fold_result["test_samples"] = int(len(test_idx))
        fold_metrics.append(fold_result)
        all_pred.extend(pred.tolist())
        all_true.extend(y[test_idx].tolist())
        all_returns.extend(forward_returns[test_idx].tolist())
        if fold_benchmark is not None:
            all_benchmark_returns.extend(fold_benchmark.tolist())
        probabilities = _aligned_predict_proba(model, X_test)
        if probabilities is not None:
            all_probabilities.append(probabilities)

    final_scaler = StandardScaler() if scaler else None
    X_final = final_scaler.fit_transform(X) if final_scaler is not None else X
    final_model = model_factory()
    final_model.fit(X_final, y, sample_weight=sample_weights(y))
    aggregate = _metrics(
        np.asarray(all_true, dtype=object),
        np.asarray(all_pred, dtype=object),
        np.asarray(all_returns),
        np.asarray(all_benchmark_returns) if all_benchmark_returns else None,
    )
    aggregate["folds"] = fold_metrics
    aggregate["samples"] = int(len(y))
    aggregate["class_distribution"] = dict(Counter(y.tolist()))
    if technical is not None:
        aggregate["technical_baseline"] = _metrics(y, technical, forward_returns, benchmark)
    calibrator = None
    if all_probabilities:
        probabilities = np.vstack(all_probabilities)
        calibrator = ProbabilityCalibrator.fit(probabilities, np.asarray(all_true, dtype=object))
        aggregate["calibration"] = _calibration_metrics(probabilities, np.asarray(all_true, dtype=object), calibrator)
    return aggregate, final_model, final_scaler, calibrator


def sample_weights(y: np.ndarray) -> np.ndarray:
    counts = Counter(y.tolist())
    total = len(y)
    classes = max(1, len(counts))
    return np.asarray([total / (classes * counts[label]) for label in y], dtype=np.float64)


def _metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    forward_returns: np.ndarray,
    benchmark_forward_returns: np.ndarray | None = None,
) -> dict[str, Any]:
    buy_mask = np.isin(y_pred, [SignalLabel.BUY.value, SignalLabel.STRONG_BUY.value])
    sell_mask = np.isin(y_pred, [SignalLabel.SELL.value, SignalLabel.STRONG_SELL.value])
    bullish_true = np.isin(y_true, [SignalLabel.BUY.value, SignalLabel.STRONG_BUY.value])
    bearish_true = np.isin(y_true, [SignalLabel.SELL.value, SignalLabel.STRONG_SELL.value])
    avg_buy_return = float(np.mean(forward_returns[buy_mask])) if np.any(buy_mask) else 0.0
    avg_buy_benchmark = (
        float(np.mean(benchmark_forward_returns[buy_mask]))
        if benchmark_forward_returns is not None and np.any(buy_mask)
        else 0.0
    )
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_precision": round(float(precision_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        "buy_precision": round(float(np.mean(bullish_true[buy_mask])) if np.any(buy_mask) else 0.0, 4),
        "sell_precision": round(float(np.mean(bearish_true[sell_mask])) if np.any(sell_mask) else 0.0, 4),
        "false_buy_rate": round(float(np.mean(~bullish_true[buy_mask])) if np.any(buy_mask) else 0.0, 4),
        "avg_buy_return": round(avg_buy_return, 4),
        "avg_buy_benchmark_return": round(avg_buy_benchmark, 4),
        "avg_buy_excess_return": round(avg_buy_return - avg_buy_benchmark, 4),
        "coverage": round(float(np.mean(y_pred != SignalLabel.HOLD.value)), 4),
    }


def _aligned_predict_proba(model: Any, X: np.ndarray) -> np.ndarray | None:
    if not hasattr(model, "predict_proba"):
        return None
    raw = np.asarray(model.predict_proba(X), dtype=np.float64)
    classes = [str(cls) for cls in getattr(model, "classes_", [])]
    if raw.ndim != 2 or not classes:
        return None
    out = np.zeros((raw.shape[0], len(CLASS_ORDER)), dtype=np.float64)
    for src_idx, label in enumerate(classes):
        if label in CLASS_ORDER:
            out[:, CLASS_ORDER.index(label)] = raw[:, src_idx]
    denom = np.sum(out, axis=1, keepdims=True)
    denom[denom == 0] = 1.0
    return out / denom


def _calibration_metrics(
    probabilities: np.ndarray,
    y_true: np.ndarray,
    calibrator: ProbabilityCalibrator,
) -> dict[str, float]:
    raw_confidence = np.max(probabilities, axis=1)
    raw_pred = np.argmax(probabilities, axis=1)
    actual = np.asarray([CLASS_ORDER.index(str(label)) if str(label) in CLASS_ORDER else -1 for label in y_true])
    correct = raw_pred == actual
    calibrated = calibrator.transform(probabilities)
    calibrated_confidence = np.max(calibrated, axis=1)
    return {
        "raw_ece": round(_ece(raw_confidence, correct), 4),
        "calibrated_ece": round(_ece(calibrated_confidence, correct), 4),
        "global_accuracy": round(float(np.mean(correct)) if len(correct) else 0.0, 4),
    }


def _ece(confidence: np.ndarray, correct: np.ndarray) -> float:
    edges = np.linspace(0, 1, 11)
    error = 0.0
    for start, end in zip(edges[:-1], edges[1:]):
        mask = (confidence >= start) & (confidence < end if end < 1 else confidence <= end)
        if np.any(mask):
            error += float(np.mean(mask)) * abs(float(np.mean(confidence[mask])) - float(np.mean(correct[mask])))
    return error


def _walk_forward_splits(n: int, *, folds: int, gap: int) -> list[tuple[np.ndarray, np.ndarray]]:
    fold_size = n // (folds + 1)
    splits: list[tuple[np.ndarray, np.ndarray]] = []
    for fold in range(1, folds + 1):
        train_end = fold_size * fold
        test_start = min(n, train_end + gap)
        test_end = min(n, test_start + fold_size)
        if train_end < 100 or test_end <= test_start:
            continue
        splits.append((np.arange(0, train_end), np.arange(test_start, test_end)))
    if not splits:
        raise ValueError("not enough ordered samples for walk-forward validation")
    return splits


def _vectorize(features: dict[str, Any], names: Iterable[str]) -> np.ndarray:
    return np.asarray([_clean_number(features.get(name)) for name in names], dtype=np.float64)


def _clean_number(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        n = float(value)
        return n if np.isfinite(n) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _prepare_kse_lookup(kse_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[int]]:
    rows = sorted(kse_rows, key=lambda r: str(r.get("date")))
    ordinals = [_parse_date(row.get("date")).toordinal() for row in rows]
    return rows, ordinals


def _kse_until(kse_rows: list[dict[str, Any]], ordinals: list[int], value: Any) -> list[dict[str, Any]]:
    target = _parse_date(value).toordinal()
    return kse_rows[: bisect_right(ordinals, target)]


def _benchmark_forward_return(kse_rows: list[dict[str, Any]], ordinals: list[int], value: Any, horizon: int) -> float:
    if not kse_rows:
        return 0.0
    idx = bisect_right(ordinals, _parse_date(value).toordinal()) - 1
    if idx < 0:
        return 0.0
    end = min(len(kse_rows) - 1, idx + horizon)
    start_close = _clean_number(kse_rows[idx].get("close"))
    end_close = _clean_number(kse_rows[end].get("close"))
    if start_close <= 0:
        return 0.0
    return float(end_close / start_close - 1)


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _rolling_atr_pct(rows: list[dict[str, Any]], period: int = 14) -> np.ndarray:
    high = np.asarray([float(r.get("high") or 0) for r in rows], dtype=np.float64)
    low = np.asarray([float(r.get("low") or 0) for r in rows], dtype=np.float64)
    close = np.asarray([float(r.get("close") or 0) for r in rows], dtype=np.float64)
    if len(close) == 0:
        return np.asarray([], dtype=np.float64)
    prev = np.roll(close, 1)
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    tr[0] = max(0.0, high[0] - low[0])
    out = np.full(len(close), 0.03, dtype=np.float64)
    for i in range(period - 1, len(close)):
        denom = close[i] if close[i] > 0 else 1.0
        out[i] = float(np.mean(tr[i - period + 1 : i + 1]) / denom)
    return out


def group_rows(rows: list[dict[str, Any]], key: str = "symbol") -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(key)
        if value:
            grouped[str(value).upper()].append(row)
    return dict(grouped)


def map_rows(rows: list[dict[str, Any]], key: str = "symbol") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        if value:
            out[str(value).upper()] = row
    return out


def save_dataset(dataset: Dataset, path: str) -> None:
    np.savez_compressed(
        path,
        X=dataset.X,
        y=dataset.y,
        dates=np.asarray([d.isoformat() for d in dataset.dates], dtype=object),
        symbols=np.asarray(dataset.symbols, dtype=object),
        forward_returns=dataset.forward_returns,
        benchmark_forward_returns=dataset.benchmark_forward_returns,
        technical_labels=dataset.technical_labels,
        feature_names=np.asarray(dataset.feature_names, dtype=object),
    )


def load_dataset(path: str) -> Dataset:
    loaded = np.load(path, allow_pickle=True)
    return Dataset(
        X=np.asarray(loaded["X"], dtype=np.float64),
        y=np.asarray(loaded["y"], dtype=object),
        dates=[_parse_date(value) for value in loaded["dates"].tolist()],
        symbols=[str(value) for value in loaded["symbols"].tolist()],
        forward_returns=np.asarray(loaded["forward_returns"], dtype=np.float64),
        benchmark_forward_returns=np.asarray(loaded["benchmark_forward_returns"], dtype=np.float64),
        technical_labels=np.asarray(loaded["technical_labels"], dtype=object),
        feature_names=[str(value) for value in loaded["feature_names"].tolist()],
    )


_FUNDAMENTAL_FEATURES = {"pe", "pb", "roe", "div_yield", "payout"}
_REVERSAL_FEATURES = ["ret_120d", "ret_240d", "ret_240d_ex20"]

SIGNAL_FEATURES_V3 = [f for f in SIGNAL_FEATURES if f not in _FUNDAMENTAL_FEATURES] + _REVERSAL_FEATURES

CORE_PRICE_FEATURES = ["ret_5d", "ret_20d", "rsi14", "price_sma50_ratio"]


def vectorize_v3(features: dict[str, Any], names: Iterable[str]) -> np.ndarray:
    """Vectorize preserving missing values as NaN (GBDT-native), never silent-zero."""
    out = []
    for name in names:
        v = features.get(name)
        try:
            f = float(v) if v is not None else np.nan
            out.append(f if np.isfinite(f) else np.nan)
        except (TypeError, ValueError):
            out.append(np.nan)
    return np.asarray(out, dtype=np.float64)


def has_core_features(features: dict[str, Any]) -> bool:
    for name in CORE_PRICE_FEATURES:
        v = features.get(name)
        try:
            if v is None or not np.isfinite(float(v)):
                return False
        except (TypeError, ValueError):
            return False
    return True
