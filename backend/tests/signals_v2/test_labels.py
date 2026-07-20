from app.services.signals_v2.labels import SignalLabel, cap_signal, display, score_to_signal


def test_score_to_signal_thresholds():
    assert score_to_signal(0.56) is SignalLabel.STRONG_BUY
    assert score_to_signal(0.2) is SignalLabel.BUY
    assert score_to_signal(0.0) is SignalLabel.HOLD
    assert score_to_signal(-0.2) is SignalLabel.SELL
    assert score_to_signal(-0.56) is SignalLabel.STRONG_SELL


def test_display_labels_are_api_labels():
    assert display(SignalLabel.STRONG_BUY) == "STRONG BUY"
    assert display(SignalLabel.NO_SIGNAL) == "NO SIGNAL"


def test_cap_signal_downgrades_only_when_needed():
    assert cap_signal(SignalLabel.STRONG_BUY, SignalLabel.HOLD) is SignalLabel.HOLD
    assert cap_signal(SignalLabel.SELL, SignalLabel.HOLD) is SignalLabel.SELL
