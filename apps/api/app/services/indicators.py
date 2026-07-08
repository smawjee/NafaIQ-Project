from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional

from app.models import OHLCVBar, IndicatorResult


def bars_to_df(bars: list[OHLCVBar]) -> pd.DataFrame:
    df = pd.DataFrame([{
        "date": b.date,
        "open": b.open,
        "high": b.high,
        "low": b.low,
        "close": b.close,
        "volume": float(b.volume),
    } for b in bars])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df


# ---------- pure numpy indicators ----------

def _sma(series: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(series, np.nan, dtype=np.float64)
    if len(series) < period:
        return result
    cumsum = np.cumsum(np.insert(series, 0, 0))
    result[period - 1:] = (cumsum[period:] - cumsum[:-period]) / period
    return result


def _ema(series: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(series, np.nan, dtype=np.float64)
    if len(series) < period:
        return result
    k = 2.0 / (period + 1)
    result[period - 1] = np.mean(series[:period])
    for i in range(period, len(series)):
        result[i] = series[i] * k + result[i - 1] * (1 - k)
    return result


def _rsi(series: np.ndarray, period: int = 14) -> np.ndarray:
    result = np.full_like(series, np.nan, dtype=np.float64)
    if len(series) < period + 1:
        return result
    delta = np.diff(series)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = np.mean(gain[:period])
    avg_loss = np.mean(loss[:period])
    for i in range(period, len(delta)):
        avg_gain = (avg_gain * (period - 1) + gain[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        if avg_loss == 0:
            result[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i + 1] = 100.0 - (100.0 / (1.0 + rs))
    return result


def _macd(series: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, np.ndarray]:
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line[np.isfinite(macd_line)], signal) if np.any(np.isfinite(macd_line)) else np.full_like(macd_line, np.nan)
    if len(signal_line) < len(macd_line):
        padded = np.full_like(macd_line, np.nan)
        start = len(macd_line) - len(signal_line)
        padded[start:] = signal_line
        signal_line = padded
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def _bollinger(series: np.ndarray, period: int = 20, std_mult: float = 2.0) -> dict[str, np.ndarray]:
    middle = _sma(series, period)
    upper = np.full_like(series, np.nan, dtype=np.float64)
    lower = np.full_like(series, np.nan, dtype=np.float64)
    rolling_std = np.full_like(series, np.nan, dtype=np.float64)
    for i in range(period - 1, len(series)):
        window = series[i - period + 1:i + 1]
        rolling_std[i] = np.std(window, ddof=0)
    upper = middle + std_mult * rolling_std
    lower = middle - std_mult * rolling_std
    return {"upper": upper, "middle": middle, "lower": lower}


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    tr = np.maximum(high - low, np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))))
    tr[0] = high[0] - low[0]
    result = np.full_like(tr, np.nan, dtype=np.float64)
    if len(tr) < period:
        return result
    result[period - 1] = np.mean(tr[:period])
    for i in range(period, len(tr)):
        result[i] = (result[i - 1] * (period - 1) + tr[i]) / period
    return result


def _adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    tr = np.maximum(high - low, np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))))
    tr[0] = high[0] - low[0]
    up_move = high - np.roll(high, 1)
    down_move = np.roll(low, 1) - low
    up_move[0] = 0
    down_move[0] = 0
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr_vals = _atr(high, low, close, period)
    plus_di = 100.0 * _ema(plus_dm, period) / atr_vals
    minus_di = 100.0 * _ema(minus_dm, period) / atr_vals
    dx = 100.0 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx_vals = _ema(dx, period)
    return adx_vals


def _obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    direction = np.sign(np.diff(close, prepend=close[0]))
    return np.cumsum(direction * volume)


def _stochastic(high: np.ndarray, low: np.ndarray, close: np.ndarray, k_period: int = 14, d_period: int = 3) -> dict[str, np.ndarray]:
    k = np.full_like(close, np.nan, dtype=np.float64)
    for i in range(k_period - 1, len(close)):
        hh = np.max(high[i - k_period + 1:i + 1])
        ll = np.min(low[i - k_period + 1:i + 1])
        k[i] = 100.0 * (close[i] - ll) / (hh - ll + 1e-10)
    d = _sma(k[~np.isnan(k)], d_period) if np.any(~np.isnan(k)) else np.full_like(k, np.nan)
    if len(d) < len(k):
        padded = np.full_like(k, np.nan)
        start = len(k) - len(d)
        padded[start:] = d
        d = padded
    return {"k": k, "d": d}


def _williams_r(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    wr = np.full_like(close, np.nan, dtype=np.float64)
    for i in range(period - 1, len(close)):
        hh = np.max(high[i - period + 1:i + 1])
        ll = np.min(low[i - period + 1:i + 1])
        wr[i] = -100.0 * (hh - close[i]) / (hh - ll + 1e-10)
    return wr


def _donchian(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 20) -> dict[str, np.ndarray]:
    upper = np.full_like(close, np.nan, dtype=np.float64)
    middle = np.full_like(close, np.nan, dtype=np.float64)
    lower = np.full_like(close, np.nan, dtype=np.float64)
    for i in range(period - 1, len(close)):
        upper[i] = np.max(high[i - period + 1:i + 1])
        lower[i] = np.min(low[i - period + 1:i + 1])
        middle[i] = (upper[i] + lower[i]) / 2.0
    return {"upper": upper, "middle": middle, "lower": lower}


# ---------- main compute function ----------

def compute_indicators(bars: list[OHLCVBar], indicator_list: list[str]) -> IndicatorResult:
    if not bars:
        return IndicatorResult(symbol="", indicators={})

    symbol = bars[0].symbol
    df = bars_to_df(bars)
    if df.empty or len(df) < 14:
        return IndicatorResult(symbol=symbol, indicators={})

    close = df["close"].to_numpy(dtype=np.float64)
    high = df["high"].to_numpy(dtype=np.float64)
    low = df["low"].to_numpy(dtype=np.float64)
    volume = df["volume"].to_numpy(dtype=np.float64)

    results: dict = {}
    for name in indicator_list:
        n = name.lower().strip()
        try:
            if n == "rsi14":
                rsi_arr = _rsi(close, 14)
                results["rsi14"] = _last(rsi_arr)
            elif n == "macd":
                macd_d = _macd(close)
                results["macd"] = {
                    "macd": _last(macd_d["macd"]),
                    "signal": _last(macd_d["signal"]),
                    "histogram": _last(macd_d["histogram"]),
                }
            elif n in ("sma20", "sma50", "sma200"):
                period = int(n.replace("sma", ""))
                arr = _sma(close, period)
                results[n] = _last(arr)
            elif n in ("ema20", "ema50"):
                period = int(n.replace("ema", ""))
                arr = _ema(close, period)
                results[n] = _last(arr)
            elif n == "bollinger":
                bb = _bollinger(close)
                results["bollinger"] = {
                    "upper": _last(bb["upper"]),
                    "middle": _last(bb["middle"]),
                    "lower": _last(bb["lower"]),
                }
            elif n == "atr14":
                arr = _atr(high, low, close, 14)
                results["atr14"] = _last(arr)
            elif n == "adx14":
                arr = _adx(high, low, close, 14)
                results["adx14"] = _last(arr)
            elif n == "stochastic":
                st = _stochastic(high, low, close)
                results["stochastic"] = {"k": _last(st["k"]), "d": _last(st["d"])}
            elif n == "obv":
                arr = _obv(close, volume)
                results["obv"] = _last(arr)
            elif n == "williams_r14":
                arr = _williams_r(high, low, close, 14)
                results["williams_r14"] = _last(arr)
            elif n == "donchian":
                dc = _donchian(high, low, close)
                results["donchian"] = {
                    "upper": _last(dc["upper"]),
                    "middle": _last(dc["middle"]),
                    "lower": _last(dc["lower"]),
                }
            else:
                results[name] = None
        except Exception:
            results[name] = None

    return IndicatorResult(symbol=symbol, indicators=results)


def _last(arr: np.ndarray) -> Optional[float]:
    if arr is None:
        return None
    finite = arr[np.isfinite(arr)]
    if len(finite) == 0:
        return None
    return round(float(finite[-1]), 4)
