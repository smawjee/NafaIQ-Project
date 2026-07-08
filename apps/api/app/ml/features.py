import numpy as np


def compute_features(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[float],
    fundamentals: dict = {},
) -> dict[str, float]:
    n = len(closes)
    if n < 60:
        return {}

    c = np.array(closes, dtype=np.float64)
    h = np.array(highs, dtype=np.float64)
    l = np.array(lows, dtype=np.float64)
    v = np.array(volumes, dtype=np.float64)

    features: dict[str, float] = {}

    # ── price-derived ──
    features["logret_5"] = float(np.log(c[-1] / c[-6])) if n >= 6 else 0.0
    features["logret_10"] = float(np.log(c[-1] / c[-11])) if n >= 11 else 0.0
    features["logret_20"] = float(np.log(c[-1] / c[-21])) if n >= 21 else 0.0
    features["logret_60"] = float(np.log(c[-1] / c[-61])) if n >= 61 else 0.0
    h52 = np.max(h[-252:]) if n >= 252 else np.max(h)
    l52 = np.min(l[-252:]) if n >= 252 else np.min(l)
    features["dist_52w_high"] = float((c[-1] - h52) / h52) if h52 else 0.0
    features["dist_52w_low"] = float((c[-1] - l52) / l52) if l52 else 0.0

    # ── trend ──
    sma20 = np.mean(c[-20:]) if n >= 20 else c[-1]
    sma50 = np.mean(c[-50:]) if n >= 50 else c[-1]
    sma200 = np.mean(c[-200:]) if n >= 200 else c[-1]
    features["price_sma20_ratio"] = float(c[-1] / sma20 - 1) if sma20 else 0.0
    features["price_sma50_ratio"] = float(c[-1] / sma50 - 1) if sma50 else 0.0
    features["price_sma200_ratio"] = float(c[-1] / sma200 - 1) if sma200 else 0.0
    features["sma20_slope"] = float((sma20 - np.mean(c[-25:-5])) / sma20) if n >= 25 and sma20 else 0.0
    features["sma50_vs_sma200"] = float((sma50 - sma200) / sma200) if n >= 200 and sma200 else 0.0

    # ── momentum ──
    features["rsi14"] = _rsi(c, 14)
    macd_line, macd_signal = _macd(c)
    features["macd_hist"] = macd_line - macd_signal
    features["macd_signal_state"] = float(
        np.sign(macd_line - macd_signal)
    )
    features["williams_r"] = _williams_r(h, l, c, 14)

    # ── volatility ──
    features["atr14_pct"] = float(_atr(h, l, c, 14) / c[-1]) if c[-1] > 0 else 0.0
    bb_upper, bb_lower = _bollinger(c, 20, 2)
    features["bb_position"] = float(
        (c[-1] - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) != 0 else 0.5
    )
    logrets = np.diff(np.log(c[-21:]))
    features["volatility_20d"] = float(np.std(logrets) * np.sqrt(252)) if len(logrets) else 0.0

    # ── volume ──
    v20_avg = np.mean(v[-20:]) if n >= 20 and np.any(v[-20:]) else 1.0
    features["volume_vs_20d"] = float(v[-1] / v20_avg) if v20_avg > 0 else 1.0
    features["obv_5d_slope"] = _obv_slope(c, v, 5)
    features["obv_20d_slope"] = _obv_slope(c, v, 20)
    features["mfi14"] = _mfi(h, l, c, v, 14)

    # ── fundamentals ──
    features["pe_zscore"] = float(fundamentals.get("pe_zscore", 0))
    features["pb"] = float(fundamentals.get("pb", 0) or 0)
    features["roe"] = float(fundamentals.get("roe", 0) or 0)
    features["div_yield"] = float(fundamentals.get("div_yield", 0) or 0)
    features["payout"] = float(fundamentals.get("payout", 0) or 0)

    return features


FEATURE_NAMES = [
    "logret_5", "logret_10", "logret_20", "logret_60",
    "dist_52w_high", "dist_52w_low",
    "price_sma20_ratio", "price_sma50_ratio", "price_sma200_ratio",
    "sma20_slope", "sma50_vs_sma200",
    "rsi14", "macd_hist", "macd_signal_state",
    "williams_r",
    "atr14_pct", "bb_position", "volatility_20d",
    "volume_vs_20d", "obv_5d_slope", "obv_20d_slope",
    "mfi14",
    "pe_zscore", "pb", "roe", "div_yield", "payout",
]


def features_array(f: dict[str, float]) -> list[float]:
    return [f.get(name, 0.0) for name in FEATURE_NAMES]


# ── indicator helpers (pure numpy) ──

def _rsi(c: np.ndarray, period: int) -> float:
    delta = np.diff(c)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = np.mean(gain[-period:])
    avg_loss = np.mean(loss[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - 100 / (1 + rs))


def _macd(c: np.ndarray, fast=12, slow=26, signal_period=9):
    ema_fast = _ema(c, fast)
    ema_slow = _ema(c, slow)
    macd_line = ema_fast[-1] - ema_slow[-1]
    macd_full = ema_fast[-signal_period * 2:] - ema_slow[-signal_period * 2:]
    macd_signal = _ema(macd_full, signal_period)[-1]
    return macd_line, macd_signal


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    alpha = 2 / (period + 1)
    result = np.zeros_like(data)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
    return result


def _atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, period: int) -> float:
    tr = np.maximum(h[-period:] - l[-period:], np.abs(h[-period:] - np.roll(c, 1)[-period:]))
    tr = np.maximum(tr, np.abs(l[-period:] - np.roll(c, 1)[-period:]))
    return float(np.mean(tr))


def _bollinger(c: np.ndarray, period: int, std_mult: float):
    sma = np.mean(c[-period:]) if len(c) >= period else 0.0
    std = np.std(c[-period:]) if len(c) >= period else 0.0
    return sma + std_mult * std, sma - std_mult * std


def _williams_r(h: np.ndarray, l: np.ndarray, c: np.ndarray, period: int) -> float:
    highest = np.max(h[-period:])
    lowest = np.min(l[-period:])
    if highest == lowest:
        return -50.0
    return float(-100 * (highest - c[-1]) / (highest - lowest))


def _obv_slope(c: np.ndarray, v: np.ndarray, lookback: int) -> float:
    obv_arr = np.zeros(len(c))
    for i in range(1, len(c)):
        if c[i] > c[i - 1]:
            obv_arr[i] = obv_arr[i - 1] + v[i]
        elif c[i] < c[i - 1]:
            obv_arr[i] = obv_arr[i - 1] - v[i]
        else:
            obv_arr[i] = obv_arr[i - 1]
    if len(obv_arr) < lookback:
        return 0.0
    x = np.arange(lookback)
    y = obv_arr[-lookback:]
    if np.std(y) == 0:
        return 0.0
    slope = float(np.polyfit(x, y, 1)[0] / np.mean(np.abs(y)))
    return slope


def _mfi(h: np.ndarray, l: np.ndarray, c: np.ndarray, v: np.ndarray, period: int) -> float:
    tp = (h[-period:] + l[-period:] + c[-period:]) / 3
    mf = tp * v[-period:]
    pos = np.sum(np.where(tp > np.roll(tp, 1), mf, 0.0)[1:])
    neg = np.sum(np.where(tp < np.roll(tp, 1), mf, 0.0)[1:])
    if neg == 0:
        return 100.0
    mfr = pos / neg
    return float(100 - 100 / (1 + mfr))
