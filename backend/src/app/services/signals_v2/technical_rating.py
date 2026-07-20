from __future__ import annotations

from typing import Any

from app.services.signals_v2.indicators import num
from app.services.signals_v2.labels import score_to_signal
from app.services.signals_v2.schemas import IndicatorVote, TechnicalRating


def compute_technical_rating(features: dict[str, Any]) -> TechnicalRating:
    votes: list[IndicatorVote] = []
    price = num(features, "last_close")

    def add(name: str, vote: int, weight: float, value: float | None, reason: str) -> None:
        votes.append(IndicatorVote(name=name, vote=vote, weight=weight, value=value, reason=reason))

    for period, weight in ((20, 1.2), (50, 1.2), (200, 1.4)):
        ratio = num(features, f"price_sma{period}_ratio")
        vote = 1 if ratio is not None and ratio > 0.01 else -1 if ratio is not None and ratio < -0.01 else 0
        if vote > 0:
            reason = f"Price is above SMA{period}"
        elif vote < 0:
            reason = f"Price is below SMA{period}"
        else:
            reason = f"Price is near SMA{period}"
        add(f"SMA{period}", vote, weight, ratio, reason)

    rsi = num(features, "rsi14")
    if rsi is None:
        add("RSI14", 0, 1.0, rsi, "RSI is unavailable")
    elif rsi >= 75:
        add("RSI14", -1, 1.0, rsi, "RSI is overbought")
    elif rsi >= 50:
        add("RSI14", 1, 1.0, rsi, "RSI is bullish but not overbought")
    elif rsi <= 25:
        add("RSI14", 1, 0.8, rsi, "RSI is deeply oversold")
    elif rsi < 45:
        add("RSI14", -1, 1.0, rsi, "RSI momentum is weak")
    else:
        add("RSI14", 0, 1.0, rsi, "RSI is neutral")

    macd = num(features, "macd_hist")
    add(
        "MACD",
        1 if macd is not None and macd > 0 else -1 if macd is not None and macd < 0 else 0,
        1.2,
        macd,
        "MACD momentum is positive" if macd and macd > 0 else "MACD momentum is negative" if macd and macd < 0 else "MACD is neutral",
    )

    bb = num(features, "bb_position")
    if bb is None:
        add("BOLLINGER", 0, 0.8, bb, "Bollinger position is unavailable")
    elif bb > 1.05:
        add("BOLLINGER", -1, 0.8, bb, "Price is extended above the Bollinger band")
    elif bb < -0.05:
        add("BOLLINGER", 1, 0.8, bb, "Price is stretched below the Bollinger band")
    elif 0.45 <= bb <= 0.8:
        add("BOLLINGER", 1, 0.8, bb, "Price is in a constructive Bollinger range")
    else:
        add("BOLLINGER", 0, 0.8, bb, "Bollinger position is neutral")

    stoch = num(features, "stochastic_k")
    if stoch is not None:
        vote = -1 if stoch > 85 else 1 if stoch < 20 else 1 if stoch > 55 else -1 if stoch < 40 else 0
        reason = "Stochastic momentum supports upside" if vote > 0 else "Stochastic momentum is weak" if vote < 0 else "Stochastic is neutral"
        add("STOCHASTIC", vote, 0.7, stoch, reason)

    wr = num(features, "williams_r14")
    if wr is not None:
        vote = -1 if wr > -15 else 1 if wr < -80 else 1 if wr > -45 else -1 if wr < -65 else 0
        reason = "Williams %R supports momentum" if vote > 0 else "Williams %R is weak" if vote < 0 else "Williams %R is neutral"
        add("WILLIAMS_R14", vote, 0.6, wr, reason)

    mfi = num(features, "mfi14")
    if mfi is not None:
        vote = -1 if mfi > 80 else 1 if mfi < 25 else 1 if mfi > 50 else -1 if mfi < 40 else 0
        reason = "Money flow confirms buying" if vote > 0 else "Money flow is defensive" if vote < 0 else "Money flow is neutral"
        add("MFI14", vote, 0.8, mfi, reason)

    vol_ratio = num(features, "volume_vs_20d")
    ret_5d = num(features, "ret_5d")
    if vol_ratio is not None and ret_5d is not None:
        vote = 1 if vol_ratio >= 1.2 and ret_5d > 0 else -1 if vol_ratio >= 1.2 and ret_5d < 0 else 0
        reason = "Volume confirms the price move" if vote > 0 else "High volume confirms selling pressure" if vote < 0 else "Volume confirmation is neutral"
        add("VOLUME_CONFIRMATION", vote, 1.0, vol_ratio, reason)

    rel = num(features, "relative_strength_kse20")
    if rel is not None:
        vote = 1 if rel > 0.015 else -1 if rel < -0.015 else 0
        reason = "Stock is outperforming KSE-100 over 20 days" if vote > 0 else "Stock is underperforming KSE-100 over 20 days" if vote < 0 else "Relative strength versus KSE-100 is neutral"
        add("RELATIVE_STRENGTH", vote, 1.1, rel, reason)

    pe = num(features, "pe")
    if pe is not None and pe > 0:
        vote = 1 if pe < 8 else -1 if pe > 25 else 0
        reason = "Valuation is supportive on P/E" if vote > 0 else "Valuation is expensive on P/E" if vote < 0 else "Valuation is neutral on P/E"
        add("PE_VALUATION", vote, 0.5, pe, reason)

    total_weight = sum(v.weight for v in votes if v.weight > 0) or 1.0
    score = sum(v.vote * v.weight for v in votes) / total_weight
    signal = score_to_signal(score)
    positives = [v.reason for v in votes if v.vote > 0][:3]
    negatives = [v.reason for v in votes if v.vote < 0][:2]
    warnings = negatives
    reasons = positives or ["Technical indicators are mixed"]
    if price is None:
        warnings.append("Latest price is unavailable")
    return TechnicalRating(signal=signal, score=score, votes=votes, reasons=reasons, warnings=warnings)
