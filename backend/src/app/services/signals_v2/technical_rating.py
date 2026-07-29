"""TradingView-style technical rating.

Two transparent sub-consensuses, each a mean of -1/0/+1 indicator votes:
  * moving-average consensus  — 12 MAs (SMA+EMA at 10/20/30/50/100/200)
  * oscillator consensus      — RSI, MACD, Stochastic, CCI, Williams %R, MFI,
                                ROC/momentum, Bollinger position
score = 0.5 * ma_score + 0.5 * osc_score  ->  STRONG BUY … STRONG SELL.

No forward-return claim: the rating describes current technical posture, so it
is faithful by construction. Relative strength, volume, regime and fundamentals
are blended in later by fusion, not here (avoids double counting).
"""
from __future__ import annotations

from typing import Any

from app.services.signals_v2.indicators import num
from app.services.signals_v2.labels import score_to_signal
from app.services.signals_v2.schemas import IndicatorVote, TechnicalRating

MA_PERIODS = (10, 20, 30, 50, 100, 200)
MA_DEADBAND = 0.005  # |price/MA - 1| below this counts as "on" the average


def compute_technical_rating(features: dict[str, Any]) -> TechnicalRating:
    ma_votes = _moving_average_votes(features)
    osc_votes = _oscillator_votes(features)
    votes = ma_votes + osc_votes

    ma_score = _mean_vote(ma_votes)
    osc_score = _mean_vote(osc_votes)
    if ma_votes and osc_votes:
        score = 0.5 * ma_score + 0.5 * osc_score
    else:
        score = ma_score or osc_score
    signal = score_to_signal(score)

    reasons = _summary_reasons(ma_votes, osc_votes)
    # Support the actual direction: lead a bearish rating with what's negative.
    if score >= 0:
        reasons += [v.reason for v in votes if v.vote > 0][:2]
    else:
        reasons += [v.reason for v in votes if v.vote < 0][:2]
    warnings = [v.reason for v in votes if v.vote < 0][:2] if score >= 0 else []
    if num(features, "last_close") is None:
        warnings.append("Latest price is unavailable")
    if not reasons:
        reasons = ["Technical indicators are mixed"]

    return TechnicalRating(
        signal=signal, score=score, votes=votes,
        reasons=reasons, warnings=warnings,
        ma_score=round(ma_score, 4), osc_score=round(osc_score, 4),
    )


def _moving_average_votes(features: dict[str, Any]) -> list[IndicatorVote]:
    votes: list[IndicatorVote] = []
    for kind in ("sma", "ema"):
        for period in MA_PERIODS:
            ratio = num(features, f"price_{kind}{period}_ratio")
            if ratio is None:
                continue
            vote = 1 if ratio > MA_DEADBAND else -1 if ratio < -MA_DEADBAND else 0
            where = "above" if vote > 0 else "below" if vote < 0 else "near"
            name = f"{kind.upper()}{period}"
            votes.append(IndicatorVote(name=name, vote=vote, weight=1.0, value=ratio,
                                       reason=f"Price is {where} {name}"))
    return votes


def _oscillator_votes(features: dict[str, Any]) -> list[IndicatorVote]:
    votes: list[IndicatorVote] = []

    def add(name: str, vote: int, value: float | None, reason: str) -> None:
        votes.append(IndicatorVote(name=name, vote=vote, weight=1.0, value=value, reason=reason))

    rsi = num(features, "rsi14")
    if rsi is not None:
        if rsi >= 75:
            add("RSI14", -1, rsi, "RSI is overbought")
        elif rsi >= 55:
            add("RSI14", 1, rsi, "RSI momentum is bullish")
        elif rsi <= 25:
            add("RSI14", 1, rsi, "RSI is deeply oversold (rebound)")
        elif rsi < 45:
            add("RSI14", -1, rsi, "RSI momentum is weak")
        else:
            add("RSI14", 0, rsi, "RSI is neutral")

    macd = num(features, "macd_hist")
    if macd is not None:
        add("MACD", 1 if macd > 0 else -1 if macd < 0 else 0, macd,
            "MACD momentum is positive" if macd > 0 else "MACD momentum is negative" if macd < 0 else "MACD is neutral")

    stoch = num(features, "stochastic_k")
    if stoch is not None:
        vote = -1 if stoch > 85 else 1 if stoch < 20 else 1 if stoch > 55 else -1 if stoch < 40 else 0
        add("STOCHASTIC", vote, stoch,
            "Stochastic supports upside" if vote > 0 else "Stochastic is weak" if vote < 0 else "Stochastic is neutral")

    cci = num(features, "cci20")
    if cci is not None:
        vote = 1 if cci > 100 else -1 if cci < -100 else 0
        add("CCI20", vote, cci,
            "CCI shows strong up-momentum" if vote > 0 else "CCI shows strong down-momentum" if vote < 0 else "CCI is neutral")

    wr = num(features, "williams_r14")
    if wr is not None:
        vote = -1 if wr > -15 else 1 if wr < -80 else 1 if wr > -45 else -1 if wr < -65 else 0
        add("WILLIAMS_R14", vote, wr,
            "Williams %R supports momentum" if vote > 0 else "Williams %R is weak" if vote < 0 else "Williams %R is neutral")

    mfi = num(features, "mfi14")
    if mfi is not None:
        vote = -1 if mfi > 80 else 1 if mfi < 25 else 1 if mfi > 50 else -1 if mfi < 40 else 0
        add("MFI14", vote, mfi,
            "Money flow confirms buying" if vote > 0 else "Money flow is defensive" if vote < 0 else "Money flow is neutral")

    roc = num(features, "roc10")
    if roc is not None:
        add("ROC10", 1 if roc > 0 else -1 if roc < 0 else 0, roc,
            "10-day momentum is positive" if roc > 0 else "10-day momentum is negative" if roc < 0 else "Momentum is flat")

    bb = num(features, "bb_position")
    if bb is not None:
        if bb > 1.05:
            add("BOLLINGER", -1, bb, "Price is extended above the Bollinger band")
        elif bb < -0.05:
            add("BOLLINGER", 1, bb, "Price is stretched below the Bollinger band")
        elif 0.45 <= bb <= 0.8:
            add("BOLLINGER", 1, bb, "Price is in a constructive Bollinger range")
        else:
            add("BOLLINGER", 0, bb, "Bollinger position is neutral")

    return votes


def _mean_vote(votes: list[IndicatorVote]) -> float:
    if not votes:
        return 0.0
    return sum(v.vote for v in votes) / len(votes)


def _summary_reasons(ma_votes: list[IndicatorVote], osc_votes: list[IndicatorVote]) -> list[str]:
    reasons: list[str] = []
    if ma_votes:
        bull = sum(1 for v in ma_votes if v.vote > 0)
        reasons.append(f"Moving averages: {bull}/{len(ma_votes)} bullish")
    if osc_votes:
        bull = sum(1 for v in osc_votes if v.vote > 0)
        reasons.append(f"Oscillators: {bull}/{len(osc_votes)} bullish")
    return reasons
