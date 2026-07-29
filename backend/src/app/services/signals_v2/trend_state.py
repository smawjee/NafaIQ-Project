"""Rule-based trend-state classification + volatility-derived risk metrics.

The trend state answers "which phase is this stock in?" — the part of market
behavior that is actually persistent (trend/volatility clustering), unlike
short-horizon returns (Phase 0 RED, 2026-07-22). Continuation probabilities
attached to warnings come ONLY from calibrate_trend_stats.py output measured
on real PSX history; nothing is invented.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TrendAssessment:
    state: str            # UPTREND | WEAKENING | DOWNTREND | BASING | RANGE | UNKNOWN
    score: float          # [-1, 1]
    evidence: list[str]


def _num(features: dict[str, Any], key: str) -> float | None:
    v = features.get(key)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def classify_trend(features: dict[str, Any]) -> TrendAssessment:
    r50 = _num(features, "price_sma50_ratio")
    r200 = _num(features, "price_sma200_ratio")
    sma50 = _num(features, "sma50")
    sma200 = _num(features, "sma200")
    ret20 = _num(features, "ret_20d") or 0.0
    ret60 = _num(features, "ret_60d") or 0.0
    dist_low = _num(features, "dist_52w_low")

    if r50 is None or r200 is None:
        return TrendAssessment("UNKNOWN", 0.0, ["insufficient history for 50/200-day structure"])

    above50, above200 = r50 > 0, r200 > 0
    # sma50 > sma200  <=>  price/sma50 < price/sma200  <=>  r50 < r200 — so the
    # ratio inequality classifies identically when raw MAs are absent (store vectors).
    golden = (sma50 > sma200) if (sma50 is not None and sma200 is not None) else (r200 > r50)

    if above50 and above200 and golden and ret60 > 0:
        score = min(1.0, (min(r50, 0.15) + min(r200, 0.25) + min(ret60, 0.30)) / 0.7 + 0.2)
        return TrendAssessment("UPTREND", round(score, 3), [
            "price above both 50-day and 200-day averages",
            "50-day average above 200-day (bullish structure)",
            f"60-day return {ret60:+.1%}",
        ])
    # BASING before DOWNTREND: near the 52-week low with a positive 20-day bounce
    # is a bottoming attempt, not an active downtrend.
    if not above200 and ret20 > 0 and dist_low is not None and dist_low <= 0.15:
        return TrendAssessment("BASING", round(min(0.4, ret20 * 4), 3), [
            f"within {dist_low:.0%} of the 52-week low with a recent bounce",
            f"20-day return {ret20:+.1%}",
        ])
    if not above50 and not above200 and not golden and ret60 < 0:
        score = -min(1.0, (min(-r50, 0.15) + min(-r200, 0.25) + min(-ret60, 0.30)) / 0.7 + 0.2)
        return TrendAssessment("DOWNTREND", round(score, 3), [
            "price below both 50-day and 200-day averages",
            "50-day average below 200-day (bearish structure)",
            f"60-day return {ret60:+.1%}",
        ])
    if above200 and not above50 and ret20 < 0:
        return TrendAssessment("WEAKENING", round(-min(0.5, -ret20 * 5), 3), [
            "price slipped below the 50-day average while still above the 200-day",
            f"20-day return {ret20:+.1%}",
        ])
    return TrendAssessment("RANGE", 0.0, ["no dominant trend structure"])


import json
from pathlib import Path

_ML_DIR = Path(__file__).resolve().parents[2] / "ml" / "signals_v2"
_STOP_FLOOR = 0.03
_VOL_BANDS = ((0.25, "LOW"), (0.45, "MODERATE"), (0.70, "HIGH"))


def load_trend_stats() -> dict | None:
    path = _ML_DIR / "trend_stats.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def risk_metrics(features: dict[str, Any], trend: TrendAssessment,
                 stats: dict | None = None) -> dict:
    vol = _num(features, "volatility_20d") or 0.0
    atr = _num(features, "atr14_pct") or 0.0
    position_risk = "EXTREME"
    for ceiling, label in _VOL_BANDS:
        if vol <= ceiling:
            position_risk = label
            break
    continuation = None
    if stats:
        continuation = (stats.get("states") or {}).get(trend.state)
    return {
        "annualized_volatility": round(vol, 4),
        "expected_20d_move_pct": round(vol * (20 / 252) ** 0.5, 4),
        "suggested_stop_pct": round(max(_STOP_FLOOR, 2 * atr), 4),
        "position_risk": position_risk,
        "continuation": continuation,
    }


def render_trend_warnings(trend: TrendAssessment, metrics: dict) -> list[str]:
    out: list[str] = []
    cont = metrics.get("continuation")
    if trend.state == "DOWNTREND":
        msg = "Downtrend intact: price below its 50- and 200-day averages."
        if cont and cont.get("n", 0) >= 100:
            msg += (f" Historically on PSX, {cont['p_negative_20d']:.0%} of such downtrends"
                    f" kept falling over the next 20 sessions"
                    f" (median move {cont['median_20d_return']:+.1%}, n={cont['n']}).")
        out.append(msg)
        out.append(f"Suggested protective stop: {metrics['suggested_stop_pct']:.1%} below current price (2x ATR).")
    elif trend.state == "WEAKENING":
        msg = "Uptrend weakening: price has slipped below its 50-day average."
        if cont and cont.get("n", 0) >= 100:
            msg += (f" Historically, {cont['p_negative_20d']:.0%} of these turned negative"
                    f" over the next 20 sessions (n={cont['n']}).")
        out.append(msg)
    if metrics.get("position_risk") in ("HIGH", "EXTREME"):
        out.append(f"Volatility is {metrics['position_risk']}"
                   f" ({metrics['annualized_volatility']:.0%} annualized) — size positions accordingly.")
    return out
