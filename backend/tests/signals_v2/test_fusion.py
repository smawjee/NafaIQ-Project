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


def test_weak_directional_buy_is_gated_to_hold():
    signal, _, _, _ = fuse_signal(
        technical=TechnicalRating(signal=SignalLabel.HOLD, score=0.1, votes=[], reasons=[], warnings=[]),
        ml=MlPrediction(),
        risk=RiskAssessment(risk_level="LOW", liquidity_score=80, volatility_score=10, caps=[]),
        regime=RegimeAssessment(regime="BULLISH", score=0.8, reason="bull"),
        data_quality=DataQuality(eligible=True, status="OK", history_days=300, liquidity_score=80, freshness="LIVE"),
        features={"relative_strength_kse20": 0.08, "volume_vs_20d": 2.0},
    )
    assert signal is SignalLabel.HOLD


def test_strong_technical_only_buy_is_gated_to_hold():
    signal, _, _, _ = fuse_signal(
        technical=TechnicalRating(signal=SignalLabel.STRONG_BUY, score=0.8, votes=[], reasons=[], warnings=[]),
        ml=MlPrediction(),
        risk=RiskAssessment(risk_level="LOW", liquidity_score=80, volatility_score=10, caps=[]),
        regime=RegimeAssessment(regime="BULLISH", score=0.2, reason="bull"),
        data_quality=DataQuality(eligible=True, status="OK", history_days=300, liquidity_score=80, freshness="LIVE"),
        features={"relative_strength_kse20": 0.05, "volume_vs_20d": 1.4},
    )
    assert signal is SignalLabel.HOLD


def test_validated_ml_can_emit_bullish_signal():
    signal, _, _, model_version = fuse_signal(
        technical=TechnicalRating(signal=SignalLabel.STRONG_BUY, score=0.8, votes=[], reasons=[], warnings=[]),
        ml=MlPrediction(
            signal=SignalLabel.STRONG_BUY,
            confidence=80,
            status="VALIDATED",
            eligible_for_fusion=True,
            model_version="fusion-v1",
        ),
        risk=RiskAssessment(risk_level="LOW", liquidity_score=80, volatility_score=10, caps=[]),
        regime=RegimeAssessment(regime="BULLISH", score=0.2, reason="bull"),
        data_quality=DataQuality(eligible=True, status="OK", history_days=300, liquidity_score=80, freshness="LIVE"),
        features={"relative_strength_kse20": 0.05, "volume_vs_20d": 1.4},
    )
    assert signal in {SignalLabel.BUY, SignalLabel.STRONG_BUY}
    assert model_version == "fusion-v1"


def test_extreme_risk_gates_bullish_signal_to_hold():
    signal, _, _, _ = fuse_signal(
        technical=TechnicalRating(signal=SignalLabel.STRONG_BUY, score=0.9, votes=[], reasons=[], warnings=[]),
        ml=MlPrediction(),
        risk=RiskAssessment(risk_level="EXTREME", liquidity_score=80, volatility_score=90, caps=[]),
        regime=RegimeAssessment(regime="BULLISH", score=0.4, reason="bull"),
        data_quality=DataQuality(eligible=True, status="OK", history_days=300, liquidity_score=80, freshness="LIVE"),
        features={"relative_strength_kse20": 0.05, "volume_vs_20d": 2.0},
    )
    assert signal is SignalLabel.HOLD


def test_bearish_avoidance_signal_can_survive_without_ml():
    signal, _, _, _ = fuse_signal(
        technical=TechnicalRating(signal=SignalLabel.HOLD, score=-0.1, votes=[], reasons=[], warnings=[]),
        ml=MlPrediction(),
        risk=RiskAssessment(risk_level="LOW", liquidity_score=80, volatility_score=10, caps=[]),
        regime=RegimeAssessment(regime="BEARISH", score=-0.8, reason="bear"),
        data_quality=DataQuality(eligible=True, status="OK", history_days=300, liquidity_score=80, freshness="LIVE"),
        features={"relative_strength_kse20": -0.08, "volume_vs_20d": 2.0},
    )
    assert signal is SignalLabel.SELL
