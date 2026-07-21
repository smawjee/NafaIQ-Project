from app.services.signals_v2.backtest import triple_barrier_labels
from app.services.signals_v2.labels import SignalLabel


def test_triple_barrier_labels_first_hit():
    labels = triple_barrier_labels([100, 101, 105, 104, 103], [0.02] * 5, horizon=3)
    assert labels[0].label in {SignalLabel.BUY, SignalLabel.STRONG_BUY}
    assert labels[0].exit_index == 2
