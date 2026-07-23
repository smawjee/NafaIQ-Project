from app.services.signals_v2.fusion import fuse_signal
from app.services.signals_v2.labels import SignalLabel
from app.services.signals_v2.schemas import (
    DataQuality, MlPrediction, RegimeAssessment, RiskAssessment, TechnicalRating,
)


def _parts(ml):
    return dict(
        technical=TechnicalRating(signal=SignalLabel.SELL, score=-0.6, votes=[], reasons=[], warnings=[]),
        ml=ml,
        risk=RiskAssessment(risk_level="LOW", liquidity_score=80, volatility_score=20, caps=[], warnings=[]),
        regime=RegimeAssessment(regime="NEUTRAL", score=0.0, reason="test"),
        data_quality=DataQuality(eligible=True, status="OK", history_days=300, freshness="LIVE"),
        features={},
    )


def test_validated_but_ineligible_ml_does_not_blend():
    ml = MlPrediction(signal=SignalLabel.STRONG_BUY, confidence=90, status="VALIDATED",
                      eligible_for_fusion=False, source="ranker-v3.1")
    label, _, _, model_version = fuse_signal(**_parts(ml))
    assert model_version == "technical-v3.0"        # ML ignored; technical drives
    assert label in (SignalLabel.SELL, SignalLabel.STRONG_SELL, SignalLabel.HOLD)


def test_eligible_ml_still_does_not_blend_in_v3():
    """ML is parked in v3.0: even a fusion-eligible prediction changes nothing."""
    ml = MlPrediction(signal=SignalLabel.STRONG_BUY, confidence=90, status="VALIDATED",
                      eligible_for_fusion=True, source="fusion-v1")
    label, _, _, model_version = fuse_signal(**_parts(ml))
    assert model_version == "technical-v3.0"
    assert label in (SignalLabel.SELL, SignalLabel.STRONG_SELL, SignalLabel.HOLD)


def test_default_ml_prediction_is_ineligible():
    ml = MlPrediction()
    assert ml.eligible_for_fusion is False
    assert ml.source == "unknown"
