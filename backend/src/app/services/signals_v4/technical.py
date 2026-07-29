"""Deterministic 26-component technical setup.

This module consumes confirmed EOD bars only. It intentionally has no forecast
or probability semantics; the output describes the current indicator posture.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable

import numpy as np

from app.services.signals_v4.schemas import TechnicalComponent, TechnicalSetup

VERSION = "technical-v4.0"
MIN_BARS = 200
MIN_COVERAGE = 0.80


def compute_technical_setup(rows: list[dict[str, Any]]) -> TechnicalSetup:
    ordered = sorted(rows, key=lambda r: str(r.get("date")))
    close = _array(ordered, "close")
    high = _array(ordered, "high")
    low = _array(ordered, "low")
    volume = _array(ordered, "volume")
    components = _components(close, high, low, volume)
    components = [_clean_component(c) for c in components]
    available = [c for c in components if c.value is not None]
    coverage = len(available) / 26.0
    bulls = sum(c.vote > 0 for c in available)
    bears = sum(c.vote < 0 for c in available)
    neutral = sum(c.vote == 0 for c in available)
    latest = _date(ordered[-1].get("date")) if ordered else None
    if len(close) < MIN_BARS or coverage < MIN_COVERAGE:
        return TechnicalSetup(
            status="unavailable",
            bar_date=latest,
            coverage=round(coverage, 4),
            bullish_count=bulls,
            bearish_count=bears,
            neutral_count=neutral,
            components=components,
            version=VERSION,
            reason_code="INSUFFICIENT_HISTORY" if len(close) < MIN_BARS else "DATA_QUALITY_FAILURE",
        )
    score = sum(c.vote for c in available) / len(available)
    return TechnicalSetup(
        status="available",
        rating=_rating(score),
        score=round(score, 4),
        bar_date=latest,
        coverage=round(coverage, 4),
        bullish_count=bulls,
        bearish_count=bears,
        neutral_count=neutral,
        components=components,
        version=VERSION,
    )


def _components(c: np.ndarray, h: np.ndarray, l: np.ndarray, v: np.ndarray) -> list[TechnicalComponent]:
    last = _last(c)
    out: list[TechnicalComponent] = []

    # TradingView-style moving-average basket: 12 SMA/EMA values plus HMA9,
    # VWMA20 and the Ichimoku base line.
    for kind in ("SMA", "EMA"):
        for period in (10, 20, 30, 50, 100, 200):
            value = _sma(c, period) if kind == "SMA" else _ema(c, period)
            out.append(_ma_component(f"{kind}{period}", last, value))
    out.append(_ma_component("HMA9", last, _hma(c, 9)))
    out.append(_ma_component("VWMA20", last, _vwma(c, v, 20)))
    out.append(_ma_component("ICHIMOKU_BASE", last, _ichimoku_base(h, l, 26)))

    rsi, rsi_prev = _rsi(c, 14)
    out.append(_threshold("RSI14", rsi, 30, 70, "RSI is oversold" if rsi is not None and rsi <= 30 else "RSI is overbought" if rsi is not None and rsi >= 70 else "RSI is neutral"))

    stoch, stoch_prev = _stochastic(h, l, c, 14)
    out.append(_threshold("STOCHASTIC", stoch, 20, 80, "Stochastic is oversold" if stoch is not None and stoch <= 20 else "Stochastic is overbought" if stoch is not None and stoch >= 80 else "Stochastic is neutral"))

    cci, cci_prev = _cci(h, l, c, 20)
    cci_vote = 1 if cci is not None and cci <= -100 and (cci_prev is None or cci > cci_prev) else -1 if cci is not None and cci >= 100 and (cci_prev is None or cci < cci_prev) else 0
    out.append(TechnicalComponent(name="CCI20", vote=cci_vote, value=cci, reason="CCI is oversold and rising" if cci_vote > 0 else "CCI is overbought and falling" if cci_vote < 0 else "CCI is neutral or lacks a confirming turn"))

    adx, plus_di, minus_di = _adx(h, l, c, 14)
    adx_vote = 1 if adx is not None and adx >= 20 and plus_di is not None and minus_di is not None and plus_di > minus_di else -1 if adx is not None and adx >= 20 and plus_di is not None and minus_di is not None and minus_di > plus_di else 0
    out.append(TechnicalComponent(name="ADX14", vote=adx_vote, value=adx, reason="ADX confirms positive directional movement" if adx_vote > 0 else "ADX confirms negative directional movement" if adx_vote < 0 else "ADX trend strength is neutral"))

    ao = _awesome_oscillator(h, l)
    out.append(_sign("AO", ao, "Awesome Oscillator is positive", "Awesome Oscillator is negative"))

    momentum = _momentum(c, 10)
    out.append(_sign("MOMENTUM10", momentum, "Momentum is positive", "Momentum is negative"))

    macd_line, macd_signal = _macd(c)
    macd_vote = 1 if macd_line is not None and macd_signal is not None and macd_line > macd_signal else -1 if macd_line is not None and macd_signal is not None and macd_line < macd_signal else 0
    out.append(TechnicalComponent(name="MACD", vote=macd_vote, value=macd_line, reason="MACD is above its signal line" if macd_vote > 0 else "MACD is below its signal line" if macd_vote < 0 else "MACD is neutral"))

    stoch_rsi_k, stoch_rsi_d = _stoch_rsi(c, 14)
    srsi_vote = 1 if stoch_rsi_k is not None and stoch_rsi_d is not None and stoch_rsi_k > stoch_rsi_d else -1 if stoch_rsi_k is not None and stoch_rsi_d is not None and stoch_rsi_k < stoch_rsi_d else 0
    out.append(TechnicalComponent(name="STOCH_RSI", vote=srsi_vote, value=stoch_rsi_k, reason="Stochastic RSI is rising" if srsi_vote > 0 else "Stochastic RSI is falling" if srsi_vote < 0 else "Stochastic RSI is neutral"))

    williams = _williams(h, l, c, 14)
    out.append(_threshold("WILLIAMS_R", williams, -80, -20, "Williams %R is oversold" if williams is not None and williams <= -80 else "Williams %R is overbought" if williams is not None and williams >= -20 else "Williams %R is neutral"))

    bull_power, bear_power = _bull_bear_power(h, l, c, 13)
    bp_vote = 1 if bull_power is not None and bear_power is not None and bull_power > 0 and bear_power > 0 else -1 if bull_power is not None and bear_power is not None and bull_power < 0 and bear_power < 0 else 0
    out.append(TechnicalComponent(name="BULL_BEAR_POWER", vote=bp_vote, value=bull_power if bull_power is not None else bear_power, reason="Bull and bear power are positive" if bp_vote > 0 else "Bull and bear power are negative" if bp_vote < 0 else "Bull and bear power are mixed"))

    ultimate = _ultimate_oscillator(h, l, c)
    out.append(_threshold("ULTIMATE_OSC", ultimate, 30, 70, "Ultimate Oscillator is oversold" if ultimate is not None and ultimate <= 30 else "Ultimate Oscillator is overbought" if ultimate is not None and ultimate >= 70 else "Ultimate Oscillator is neutral"))
    return out


def _clean_component(component: TechnicalComponent) -> TechnicalComponent:
    value = component.value
    if value is not None and not np.isfinite(value):
        return component.model_copy(update={"value": None, "vote": 0, "reason": "Indicator unavailable because source data is incomplete"})
    return component


def _ma_component(name: str, price: float | None, value: float | None) -> TechnicalComponent:
    vote = 1 if price is not None and value is not None and price > value else -1 if price is not None and value is not None and price < value else 0
    return TechnicalComponent(name=name, vote=vote, value=value, reason=f"Price is above {name}" if vote > 0 else f"Price is below {name}" if vote < 0 else f"Price is near {name}")


def _threshold(name: str, value: float | None, bullish: float, bearish: float, reason: str) -> TechnicalComponent:
    vote = 1 if value is not None and value <= bullish else -1 if value is not None and value >= bearish else 0
    return TechnicalComponent(name=name, vote=vote, value=value, reason=reason)


def _sign(name: str, value: float | None, positive: str, negative: str) -> TechnicalComponent:
    vote = 1 if value is not None and value > 0 else -1 if value is not None and value < 0 else 0
    return TechnicalComponent(name=name, vote=vote, value=value, reason=positive if vote > 0 else negative if vote < 0 else f"{name} is neutral")


def _rating(score: float) -> str:
    if score >= 0.5:
        return "Strong Bullish"
    if score > 0.1:
        return "Bullish"
    if score > -0.1:
        return "Neutral"
    if score > -0.5:
        return "Bearish"
    return "Strong Bearish"


def _array(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    # Preserve missing observations as NaN so corrupted rows cannot inflate coverage.
    return np.asarray([_float(r.get(key), np.nan) for r in rows], dtype=np.float64)


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        n = float(value)
        return n if np.isfinite(n) else default
    except (TypeError, ValueError):
        return default


def _last(values: np.ndarray) -> float | None:
    return float(values[-1]) if len(values) and np.isfinite(values[-1]) and values[-1] > 0 else None


def _sma(values: np.ndarray, period: int) -> float | None:
    window = values[-period:]
    return float(np.mean(window)) if len(values) >= period and np.all(np.isfinite(window)) else None


def _ema(values: np.ndarray, period: int) -> float | None:
    if len(values) < period or not np.all(np.isfinite(values)):
        return None
    alpha = 2 / (period + 1)
    current = float(np.mean(values[:period]))
    for value in values[period:]:
        current = alpha * float(value) + (1 - alpha) * current
    return current


def _wma(values: np.ndarray, period: int) -> float | None:
    if len(values) < period or not np.all(np.isfinite(values[-period:])):
        return None
    weights = np.arange(1, period + 1, dtype=np.float64)
    return float(np.dot(values[-period:], weights) / weights.sum())


def _hma(values: np.ndarray, period: int) -> float | None:
    half = _wma(values, period // 2)
    full = _wma(values, period)
    if half is None or full is None:
        return None
    derived = np.append(values[:-1], 2 * half - full)
    return _wma(derived, max(1, int(np.sqrt(period))))


def _vwma(close: np.ndarray, volume: np.ndarray, period: int) -> float | None:
    if (len(close) < period or len(volume) < period or not np.all(np.isfinite(close[-period:])) or not np.all(np.isfinite(volume[-period:])) or np.sum(volume[-period:]) <= 0):
        return None
    return float(np.sum(close[-period:] * volume[-period:]) / np.sum(volume[-period:]))


def _ichimoku_base(high: np.ndarray, low: np.ndarray, period: int) -> float | None:
    if (len(high) < period or len(low) < period or not np.all(np.isfinite(high[-period:])) or not np.all(np.isfinite(low[-period:]))):
        return None
    return float((np.max(high[-period:]) + np.min(low[-period:])) / 2)


def _rsi(close: np.ndarray, period: int) -> tuple[float | None, float | None]:
    if len(close) < period + 2:
        return None, None
    delta = np.diff(close)
    gain = np.maximum(delta, 0)
    loss = np.maximum(-delta, 0)
    def one(g: np.ndarray, l: np.ndarray) -> float:
        avg_gain = float(np.mean(g[-period:]))
        avg_loss = float(np.mean(l[-period:]))
        return 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return one(gain, loss), one(gain[:-1], loss[:-1])


def _stochastic(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> tuple[float | None, float | None]:
    if len(close) < period + 1:
        return None, None
    def one(i: int) -> float:
        hi, lo = np.max(high[i - period + 1:i + 1]), np.min(low[i - period + 1:i + 1])
        return 50.0 if hi == lo else float((close[i] - lo) / (hi - lo) * 100)
    return one(len(close) - 1), one(len(close) - 2)


def _cci(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> tuple[float | None, float | None]:
    typical = (high + low + close) / 3
    if len(typical) < period + 1:
        return None, None
    def one(i: int) -> float:
        window = typical[i - period + 1:i + 1]
        mean = float(np.mean(window))
        mad = float(np.mean(np.abs(window - mean)))
        return 0.0 if mad == 0 else float((typical[i] - mean) / (0.015 * mad))
    return one(len(typical) - 1), one(len(typical) - 2)


def _adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> tuple[float | None, float | None, float | None]:
    if len(close) < period + 2:
        return None, None, None
    up = np.diff(high)
    down = -np.diff(low)
    plus = np.where((up > down) & (up > 0), up, 0.0)
    minus = np.where((down > up) & (down > 0), down, 0.0)
    tr = np.maximum(high[1:] - low[1:], np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
    if len(tr) < period:
        return None, None, None
    atr = float(np.mean(tr[-period:]))
    if atr == 0:
        return 0.0, 0.0, 0.0
    plus_di = float(100 * np.mean(plus[-period:]) / atr)
    minus_di = float(100 * np.mean(minus[-period:]) / atr)
    dx = 100 * abs(plus_di - minus_di) / max(plus_di + minus_di, 1e-9)
    return float(dx), plus_di, minus_di


def _awesome_oscillator(high: np.ndarray, low: np.ndarray) -> float | None:
    median = (high + low) / 2
    if len(median) < 34:
        return None
    return float(np.mean(median[-5:]) - np.mean(median[-34:]))


def _momentum(close: np.ndarray, period: int) -> float | None:
    return float(close[-1] - close[-period - 1]) if len(close) > period else None


def _macd(close: np.ndarray) -> tuple[float | None, float | None]:
    if len(close) < 35:
        return None, None
    fast = _ema_series(close, 12)
    slow = _ema_series(close, 26)
    line = fast - slow
    signal = _ema_series(line, 9)
    return float(line[-1]), float(signal[-1]) if len(signal) else None


def _ema_series(values: np.ndarray, period: int) -> np.ndarray:
    if len(values) == 0:
        return np.asarray([], dtype=np.float64)
    alpha = 2 / (period + 1)
    out = np.empty(len(values), dtype=np.float64)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def _stoch_rsi(close: np.ndarray, period: int) -> tuple[float | None, float | None]:
    if len(close) < period * 3:
        return None, None
    rsi_values = []
    for i in range(period + 1, len(close)):
        value, _ = _rsi(close[:i + 1], period)
        if value is not None:
            rsi_values.append(value)
    if len(rsi_values) < period:
        return None, None
    stoch = []
    for i in range(period - 1, len(rsi_values)):
        window = np.asarray(rsi_values[i - period + 1:i + 1])
        stoch.append(0.5 if np.max(window) == np.min(window) else (rsi_values[i] - np.min(window)) / (np.max(window) - np.min(window)))
    if len(stoch) < 3:
        return None, None
    k = float(np.mean(stoch[-3:]) * 100)
    d = float(np.mean(stoch[-5:]) * 100) if len(stoch) >= 5 else k
    return k, d


def _williams(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> float | None:
    if len(close) < period:
        return None
    hi, lo = np.max(high[-period:]), np.min(low[-period:])
    return -50.0 if hi == lo else float((hi - close[-1]) / (hi - lo) * -100)


def _bull_bear_power(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> tuple[float | None, float | None]:
    ema = _ema(close, period)
    if ema is None or not len(close):
        return None, None
    return float(high[-1] - ema), float(low[-1] - ema)


def _ultimate_oscillator(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> float | None:
    if len(close) < 29:
        return None
    prev = close[:-1]
    bp = close[1:] - np.minimum(low[1:], prev)
    tr = np.maximum(high[1:], prev) - np.minimum(low[1:], prev)
    def avg(period: int) -> float:
        return float(np.sum(bp[-period:]) / max(np.sum(tr[-period:]), 1e-9))
    return float(100 * (4 * avg(7) + 2 * avg(14) + avg(28)) / 7)


def _date(value: Any) -> date | None:
    try:
        return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None
