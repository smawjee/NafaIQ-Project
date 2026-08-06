"""Decision policy — turning a measured probability into a rating.

Two independent paths live here:

* ``apply_forecast_policy`` — the publication rule for a promoted *ML* forecast
  (``psx_signal_forecasts``). Unused until a model passes the promotion gate.
* ``build_recommendation`` — the Tier 1 ladder, driven by measured base rates.
  This is the one that ships.

Three design points that are easy to get wrong
----------------------------------------------
**The base rate is not 0.50.** The measured PSX 20-session rate is **0.472** —
the median stock rose in fewer than half of all 20-day windows, because the
equal-weighted universe badly lagged the cap-weighted index over 2016-2026. A
naive ``p > 0.5 → BUY`` would therefore mislabel a merely typical stock as
bearish. Every threshold here is expressed *relative to the measured base rate*
carried in the artifact, so recalibration moves the bar automatically.

**The whole interval must clear the bar, not the point estimate.** Buys are
judged on ``p_lower`` and sells on ``p_upper`` — the conservative end of each.
A cohort too thin to be sure of cannot clear either bar, so abstention to HOLD
is a structural consequence rather than a special case.

**The bars are asymmetric, because the evidence is.** The pilot measured the
reversal effect running mostly through the short side — in the holdout, recent
winners fell 2.52% while recent losers gained only 0.47% (RESEARCH_LOG.md, H2).
Buy calls therefore face a wider margin than sell calls. Thresholds were set
from the measured distribution of cell probabilities (finest cells span
0.255-0.701, median Wilson half-width 0.033), targeting a majority-HOLD output.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.services.signals.schemas import Recommendation

#: Margin above the base rate that `p_lower` must clear.
BUY_MARGIN = 0.03
STRONG_BUY_MARGIN = 0.06
#: Margin below the base rate that `p_upper` must clear. Deliberately smaller
#: than the buy margins — see the module docstring.
SELL_MARGIN = 0.02
STRONG_SELL_MARGIN = 0.05

#: A cohort thinner than this cannot support a directional call at all.
MIN_SAMPLE_FOR_CALL = 150
#: STRONG rungs additionally require a clean measurement.
MIN_QUALITY_FOR_STRONG = 45.0


@dataclass(frozen=True)
class ForecastDecision:
    direction: str | None
    abstain_reason: str | None


def apply_forecast_policy(
    *,
    p_outperform: float | None,
    expected_excess_net: float | None,
    interval_lower: float | None,
    interval_upper: float | None,
) -> ForecastDecision:
    """Apply the symmetric publication rule without using realized outcomes."""
    if any(value is None for value in (p_outperform, expected_excess_net, interval_lower, interval_upper)):
        return ForecastDecision(None, "INCOMPLETE_FORECAST")
    assert p_outperform is not None
    assert expected_excess_net is not None
    assert interval_lower is not None
    assert interval_upper is not None
    if p_outperform >= 0.60 and expected_excess_net > 0 and interval_lower > 0:
        return ForecastDecision("OUTPERFORM", None)
    if p_outperform <= 0.40 and expected_excess_net < 0 and interval_upper < 0:
        return ForecastDecision("UNDERPERFORM", None)
    return ForecastDecision(None, "NO_VALIDATED_EDGE")


def build_recommendation(
    *,
    base_rate: Any,
    horizon: int = 20,
    quality_score: Optional[float] = None,
    round_trip_cost: Optional[float] = None,
    suggested_stop_pct: Optional[float] = None,
    global_rate: Optional[float] = None,
    drivers: Optional[list[str]] = None,
) -> Recommendation:
    """Map a measured cohort into a rating on the asymmetric ladder.

    ``base_rate`` is a ``base_rates.BaseRate`` (or None when the artifact is
    missing or the cohort could not be identified), and ``global_rate`` is the
    all-history margin the thresholds are measured against.
    """
    if base_rate is None or global_rate is None:
        return Recommendation(
            rating="HOLD", horizon_sessions=horizon,
            abstain_reason="NO_CALIBRATION_DATA",
            drivers=list(drivers or []),
        )

    p = float(base_rate.p)
    lower = float(base_rate.p_lower)
    upper = float(base_rate.p_upper)
    n = int(base_rate.n)
    base = float(global_rate)

    common = dict(
        horizon_sessions=horizon,
        p=round(p, 4), p_lower=round(lower, 4), p_upper=round(upper, 4),
        base_rate=round(base, 4),
        event=f"rose over the next {horizon} trading sessions",
        basis=base_rate.basis,
        sample_size=n,
        expected_move=base_rate.median_return,
        round_trip_cost=round(round_trip_cost, 5) if round_trip_cost is not None else None,
        suggested_stop_pct=suggested_stop_pct,
        drivers=list(drivers or []),
    )

    if n < MIN_SAMPLE_FOR_CALL:
        return Recommendation(rating="HOLD", abstain_reason="INSUFFICIENT_COHORT", **common)

    quality_ok = quality_score is None or quality_score >= MIN_QUALITY_FOR_STRONG

    # Sell side first: on PSX it carries the stronger evidence, and a stock can
    # satisfy neither side but never both.
    if upper < base - STRONG_SELL_MARGIN and quality_ok:
        return Recommendation(rating="STRONG_SELL", **common)
    if upper < base - SELL_MARGIN:
        return Recommendation(rating="SELL", **common)
    if lower > base + STRONG_BUY_MARGIN and quality_ok:
        return Recommendation(rating="STRONG_BUY", **common)
    if lower > base + BUY_MARGIN:
        return Recommendation(rating="BUY", **common)

    return Recommendation(
        rating="HOLD",
        abstain_reason=_why_hold(lower, upper, base),
        **common,
    )


def _why_hold(lower: float, upper: float, base: float) -> str:
    """Name the bar that was not cleared, so the UI can explain the abstention."""
    if lower <= base <= upper:
        return "INTERVAL_STRADDLES_BASE_RATE"
    if lower > base:
        return "EDGE_TOO_SMALL_TO_ACT"      # positive, but inside the buy margin
    return "EDGE_TOO_SMALL_TO_ACT"          # negative, but inside the sell margin
