from __future__ import annotations

from app.services.signals_v2.schemas import RegimeAssessment, RiskAssessment, TechnicalRating


def build_reasons(technical: TechnicalRating, risk: RiskAssessment, regime: RegimeAssessment) -> list[str]:
    reasons: list[str] = []
    reasons.extend(technical.reasons[:3])
    if regime.score > 0:
        reasons.append(regime.reason)
    if risk.liquidity_score >= 60:
        reasons.append("Liquidity is sufficient for a more reliable signal")
    return _unique(reasons)[:5] or ["Signal is neutral because indicators are mixed"]


def build_warnings(
    *,
    technical: TechnicalRating,
    risk: RiskAssessment,
    data_warnings: list[str],
    regime: RegimeAssessment,
) -> list[str]:
    warnings: list[str] = []
    warnings.extend(data_warnings)
    warnings.extend(risk.warnings)
    warnings.extend(technical.warnings[:2])
    if regime.score < 0:
        warnings.append(regime.reason)
    return _unique(warnings)[:6]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out
