from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite, log, sqrt
from typing import Any, Optional

import numpy as np


@dataclass(frozen=True)
class FeatureFrame:
    symbol: str
    dates: list[date]
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    fundamentals: dict[str, Any]
    profile: dict[str, Any]
    snapshot: dict[str, Any]
    kse_close: np.ndarray


def build_feature_frame(
    *,
    symbol: str,
    ohlcv_rows: list[dict[str, Any]],
    snapshot: dict[str, Any] | None = None,
    fundamentals: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    kse_rows: list[dict[str, Any]] | None = None,
) -> FeatureFrame:
    rows = sorted(ohlcv_rows, key=lambda r: str(r.get("date")))
    dates = [_parse_date(r.get("date")) for r in rows]
    open_ = _series(rows, "open")
    high = _series(rows, "high")
    low = _series(rows, "low")
    close = _series(rows, "close")
    volume = _series(rows, "volume")

    snap = snapshot or {}
    live_price = _num(snap.get("price"))
    if live_price and len(close):
        close[-1] = live_price
        high[-1] = max(high[-1], live_price)
        low[-1] = min(low[-1], live_price) if low[-1] > 0 else live_price
        if snap.get("day_high") is not None:
            high[-1] = max(high[-1], _num(snap.get("day_high")) or high[-1])
        if snap.get("day_low") is not None:
            day_low = _num(snap.get("day_low"))
            if day_low:
                low[-1] = min(low[-1], day_low)
        if snap.get("volume") is not None:
            volume[-1] = _num(snap.get("volume")) or volume[-1]

    kse = np.asarray(
        [_num(r.get("close")) or 0.0 for r in sorted(kse_rows or [], key=lambda r: str(r.get("date")))],
        dtype=np.float64,
    )
    return FeatureFrame(
        symbol=symbol.upper(),
        dates=dates,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        fundamentals=fundamentals or {},
        profile=profile or {},
        snapshot=snap,
        kse_close=kse,
    )


def compute_feature_snapshot(frame: FeatureFrame) -> dict[str, Any]:
    c, h, l, v = frame.close, frame.high, frame.low, frame.volume
    if len(c) == 0:
        return {}
    features: dict[str, Any] = {
        "last_close": _finite(c[-1]),
        "history_days": len(c),
        "volume": _finite(v[-1]),
        "turnover": _finite(c[-1] * v[-1]),
        "ret_1d": _return(c, 1),
        "ret_3d": _return(c, 3),
        "ret_5d": _return(c, 5),
        "ret_10d": _return(c, 10),
        "ret_20d": _return(c, 20),
        "ret_60d": _return(c, 60),
        "ret_120d": _return(c, 120),
        "ret_240d": _return(c, 240),
        "ret_240d_ex20": _long_reversal(c, 240, 20),
        "volatility_20d": _volatility(c, 20),
        "atr14_pct": _atr_pct(h, l, c, 14),
        "volume_vs_20d": _volume_ratio(v, 20),
        "dist_52w_high": _dist_high(c, h),
        "dist_52w_low": _dist_low(c, l),
        "rsi14": _rsi_last(c, 14),
        "macd_hist": _macd_hist(c),
        "stochastic_k": _stochastic_k(h, l, c, 14),
        "williams_r14": _williams_r(h, l, c, 14),
        "mfi14": _mfi(h, l, c, v, 14),
        "bb_position": _bb_position(c, 20),
        "obv_20d_slope": _obv_slope(c, v, 20),
        "roc10": _return(c, 10),
        "cci20": _cci(h, l, c, 20),
        "relative_strength_kse20": _relative_strength(c, frame.kse_close, 20),
    }
    for period in (10, 20, 30, 50, 100, 200):
        sma = _sma_last(c, period)
        ema = _ema_last(c, period)
        features[f"sma{period}"] = sma
        features[f"ema{period}"] = ema
        features[f"price_sma{period}_ratio"] = _ratio(c[-1], sma)
        features[f"price_ema{period}_ratio"] = _ratio(c[-1], ema)
    for key in ("pe", "pb", "roe", "div_yield", "payout"):
        features[key] = _num(frame.fundamentals.get(key))
    return features


def _series(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.asarray([_num(r.get(key)) or 0.0 for r in rows], dtype=np.float64)


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _num(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        n = float(value)
        return n if isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _finite(value: Any) -> Optional[float]:
    return _num(value)


def _return(series: np.ndarray, periods: int) -> Optional[float]:
    if len(series) <= periods or series[-periods - 1] <= 0:
        return None
    return float(series[-1] / series[-periods - 1] - 1)


def _ratio(a: Any, b: Any) -> Optional[float]:
    aa, bb = _num(a), _num(b)
    if aa is None or bb is None or bb == 0:
        return None
    return float(aa / bb - 1)


def _sma_last(series: np.ndarray, period: int) -> Optional[float]:
    if len(series) < period:
        return None
    return float(np.mean(series[-period:]))


def _ema_last(series: np.ndarray, period: int) -> Optional[float]:
    if len(series) < period:
        return None
    alpha = 2 / (period + 1)
    ema = float(np.mean(series[:period]))
    for value in series[period:]:
        ema = float(value) * alpha + ema * (1 - alpha)
    return ema


def _rsi_last(series: np.ndarray, period: int) -> Optional[float]:
    if len(series) < period + 1:
        return None
    delta = np.diff(series)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = np.mean(gain[-period:])
    avg_loss = np.mean(loss[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - 100 / (1 + rs))


def _macd_hist(series: np.ndarray) -> Optional[float]:
    fast, slow = _ema_last(series, 12), _ema_last(series, 26)
    if fast is None or slow is None:
        return None
    macd_line = fast - slow
    if len(series) < 35:
        return macd_line
    tail = []
    for i in range(len(series) - 18, len(series) + 1):
        window = series[:i]
        f, s = _ema_last(window, 12), _ema_last(window, 26)
        if f is not None and s is not None:
            tail.append(f - s)
    signal = _ema_last(np.asarray(tail, dtype=np.float64), 9) if len(tail) >= 9 else 0
    return float(macd_line - (signal or 0))


def _atr_pct(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> Optional[float]:
    if len(close) < period + 1 or close[-1] <= 0:
        return None
    prev_close = np.roll(close, 1)
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    tr[0] = high[0] - low[0]
    return float(np.mean(tr[-period:]) / close[-1])


def _volume_ratio(volume: np.ndarray, period: int) -> Optional[float]:
    if len(volume) < period + 1:
        return None
    avg = float(np.mean(volume[-period - 1:-1]))
    if avg <= 0:
        return None
    return float(volume[-1] / avg)


def _volatility(close: np.ndarray, period: int) -> Optional[float]:
    if len(close) < period + 1 or np.any(close[-period - 1:] <= 0):
        return None
    logrets = np.diff(np.log(close[-period - 1:]))
    return float(np.std(logrets) * sqrt(252))


def _dist_high(close: np.ndarray, high: np.ndarray) -> Optional[float]:
    if len(close) == 0:
        return None
    h = float(np.max(high[-252:]))
    return float(close[-1] / h - 1) if h > 0 else None


def _dist_low(close: np.ndarray, low: np.ndarray) -> Optional[float]:
    if len(close) == 0:
        return None
    l = float(np.min(low[-252:]))
    return float(close[-1] / l - 1) if l > 0 else None


def _stochastic_k(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> Optional[float]:
    if len(close) < period:
        return None
    hh = float(np.max(high[-period:]))
    ll = float(np.min(low[-period:]))
    if hh == ll:
        return 50.0
    return float(100 * (close[-1] - ll) / (hh - ll))


def _williams_r(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> Optional[float]:
    k = _stochastic_k(high, low, close, period)
    return None if k is None else float(k - 100)


def _mfi(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, period: int) -> Optional[float]:
    if len(close) < period + 1:
        return None
    tp = (high + low + close) / 3
    mf = tp * volume
    pos = np.sum(np.where(tp[-period:] > np.roll(tp, 1)[-period:], mf[-period:], 0.0))
    neg = np.sum(np.where(tp[-period:] < np.roll(tp, 1)[-period:], mf[-period:], 0.0))
    if neg == 0:
        return 100.0
    ratio = pos / neg
    return float(100 - 100 / (1 + ratio))


def _bb_position(close: np.ndarray, period: int) -> Optional[float]:
    if len(close) < period:
        return None
    window = close[-period:]
    mid = float(np.mean(window))
    std = float(np.std(window))
    upper, lower = mid + 2 * std, mid - 2 * std
    if upper == lower:
        return 0.5
    return float((close[-1] - lower) / (upper - lower))


def _obv_slope(close: np.ndarray, volume: np.ndarray, lookback: int) -> Optional[float]:
    if len(close) < lookback + 1:
        return None
    direction = np.sign(np.diff(close, prepend=close[0]))
    obv = np.cumsum(direction * volume)
    y = obv[-lookback:]
    if np.std(y) == 0:
        return 0.0
    x = np.arange(lookback)
    denom = np.mean(np.abs(y)) or 1.0
    return float(np.polyfit(x, y, 1)[0] / denom)


def _cci(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> Optional[float]:
    if len(close) < period:
        return None
    tp = (high + low + close) / 3
    window = tp[-period:]
    sma = float(np.mean(window))
    mean_dev = float(np.mean(np.abs(window - sma)))
    if mean_dev == 0:
        return 0.0
    return float((tp[-1] - sma) / (0.015 * mean_dev))


def _relative_strength(close: np.ndarray, benchmark: np.ndarray, period: int) -> Optional[float]:
    if len(close) <= period or len(benchmark) <= period:
        return None
    return_stock = _return(close, period)
    return_benchmark = _return(benchmark, period)
    if return_stock is None or return_benchmark is None:
        return None
    return float(return_stock - return_benchmark)


def _long_reversal(series: np.ndarray, long_p: int, skip_p: int) -> Optional[float]:
    """Long-horizon return excluding the most recent skip_p bars (PSX shows loser reversal)."""
    if len(series) <= long_p or series[-long_p - 1] <= 0 or series[-skip_p - 1] <= 0:
        return None
    return float(series[-skip_p - 1] / series[-long_p - 1] - 1)
