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


def top_contributions(model, feature_vector, feature_names, k: int = 3) -> dict:
    """Top-k positive/negative per-feature contributions for one prediction.

    Uses TreeSHAP-style contributions (XGBoost pred_contribs / LightGBM
    pred_contrib). Returns {"positive": [[name, value], ...], "negative": [...]}
    sorted by magnitude; contributions, not causation.
    """
    import numpy as np

    x = np.asarray(feature_vector, dtype=np.float64).reshape(1, -1)
    contribs = None
    try:
        import xgboost
        if isinstance(model, xgboost.XGBModel):
            booster = model.get_booster()
            dm = xgboost.DMatrix(x, feature_names=[str(n) for n in feature_names])
            contribs = np.asarray(booster.predict(dm, pred_contribs=True))[0][:-1]  # drop bias term
    except ImportError:
        pass
    if contribs is None and "lightgbm" in type(model).__module__:
        contribs = np.asarray(model.predict(x, pred_contrib=True))[0][:-1]
    if contribs is None:
        return {"positive": [], "negative": []}
    order = np.argsort(contribs)
    negative = [[str(feature_names[i]), round(float(contribs[i]), 5)]
                for i in order[:k] if contribs[i] < 0]
    positive = [[str(feature_names[i]), round(float(contribs[i]), 5)]
                for i in order[::-1][:k] if contribs[i] > 0]
    return {"positive": positive, "negative": negative}


def render_ai_reasons(explanation_factors: dict | None) -> list[str]:
    """Human-readable AI reasons from stored explanation factors.

    AI reasons come ONLY from model contributions (price/technical features);
    fundamental context is rendered separately and never presented as an AI reason.
    """
    if not explanation_factors:
        return []
    reasons: list[str] = []
    for head, label in (("ranker", "relative ranking"), ("absolute", "absolute return")):
        factors = explanation_factors.get(head) or {}
        for name, value in (factors.get("positive") or [])[:3]:
            reasons.append(f"{name} supported the {label} view (contribution {value:+.3f})")
        for name, value in (factors.get("negative") or [])[:3]:
            reasons.append(f"{name} weighed against the {label} view (contribution {value:+.3f})")
    if reasons:
        reasons.append("Feature contributions describe this model's prediction, not market causation.")
    return _unique(reasons)
