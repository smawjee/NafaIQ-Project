from datetime import datetime, timezone

from app.services.signals_v2.labels import SignalLabel
from app.services.signals_v2.schemas import (
    MlPrediction,
    RegimeAssessment,
    RiskAssessment,
    SignalV2Response,
    TechnicalRating,
    to_v1,
)


def test_v2_response_maps_to_v1_contract():
    response = SignalV2Response.from_parts(
        symbol="HBL",
        horizon="20D",
        signal=SignalLabel.BUY,
        confidence=68,
        rank_score=74,
        technical=TechnicalRating(signal=SignalLabel.BUY, score=0.3, votes=[], reasons=[], warnings=[]),
        ml=MlPrediction(),
        risk=RiskAssessment(risk_level="MODERATE", liquidity_score=80, volatility_score=30),
        regime=RegimeAssessment(regime="BULLISH", score=0.2, reason="bull"),
        freshness="LIVE",
        reasons=["Price is above SMA20"],
        warnings=[],
        features_snapshot={},
        model_version="technical-v2.0",
        engine_version="signals-v2",
        predicted_at=datetime.now(timezone.utc),
    )
    compat = to_v1(response)
    assert compat.signal == "BUY"
    assert compat.features_used
