from app.services.signals_v2.fusion import fuse_signal
from app.services.signals_v2.labels import SignalLabel
from app.services.signals_v2.schemas import DataQuality, MlPrediction, RegimeAssessment, RiskAssessment, TechnicalRating


def test_low_liquidity_caps_bullish_signal_at_hold():
    signal, confidence, _, _ = fuse_signal(
        technical=TechnicalRating(signal=SignalLabel.STRONG_BUY, score=0.9, votes=[], reasons=[], warnings=[]),
        ml=MlPrediction(),
        risk=RiskAssessment(risk_level="LOW", liquidity_score=10, volatility_score=10, caps=["MAX_HOLD_LOW_LIQUIDITY"]),
        regime=RegimeAssessment(regime="BULLISH", score=0.35, reason="bull"),
        data_quality=DataQuality(eligible=True, status="OK", history_days=300, liquidity_score=10, freshness="LIVE"),
        features={"relative_strength_kse20": 0.05, "volume_vs_20d": 2},
    )
    assert signal is SignalLabel.HOLD
    assert confidence <= 70


def test_stale_data_returns_no_signal():
    signal, confidence, _, _ = fuse_signal(
        technical=TechnicalRating(signal=SignalLabel.BUY, score=0.4, votes=[], reasons=[], warnings=[]),
        ml=MlPrediction(),
        risk=RiskAssessment(risk_level="LOW", liquidity_score=80, volatility_score=10, caps=["NO_SIGNAL_STALE_DATA"]),
        regime=RegimeAssessment(regime="NEUTRAL", score=0, reason="neutral"),
        data_quality=DataQuality(eligible=True, status="OK", history_days=300, liquidity_score=80, freshness="STALE"),
        features={},
    )
    assert signal is SignalLabel.NO_SIGNAL
    assert confidence == 0
