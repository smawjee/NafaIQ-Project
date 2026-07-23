from __future__ import annotations

from dataclasses import dataclass


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
