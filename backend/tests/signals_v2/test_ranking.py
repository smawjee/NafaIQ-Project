import numpy as np
import pytest
from datetime import date, timedelta

from app.services.signals_v2.labels import SignalLabel
from app.services.signals_v2.ranking import (
    ROUND_TRIP_COST, excess_to_label, relative_deciles,
)


def test_excess_to_label_bands_and_horizon_scaling():
    assert excess_to_label(0.08, "20D") == SignalLabel.STRONG_BUY
    assert excess_to_label(0.03, "20D") == SignalLabel.BUY
    assert excess_to_label(0.0, "20D") == SignalLabel.HOLD
    assert excess_to_label(-0.03, "20D") == SignalLabel.SELL
    assert excess_to_label(-0.08, "20D") == SignalLabel.STRONG_SELL
    assert excess_to_label(0.02, "20D") == SignalLabel.BUY
    assert excess_to_label(0.02, "60D") == SignalLabel.HOLD
    assert ROUND_TRIP_COST == 0.005


def test_relative_deciles_within_date_and_ties():
    d1, d2 = date(2025, 1, 1), date(2025, 2, 1)
    n = 40
    dates = [d1] * n + [d2] * n
    excess = np.asarray(list(range(n)) + list(range(n, 0, -1)), dtype=np.float64)
    dec = relative_deciles(dates, excess, min_names=30)
    assert dec[0] == 0 and dec[n - 1] == 9
    assert dec[n] == 9 and dec[2 * n - 1] == 0
    for day in (dec[:n], dec[n:]):
        counts = np.bincount(day, minlength=10)
        assert counts.min() == 4 and counts.max() == 4


def test_relative_deciles_ties_are_averaged_not_arbitrary():
    d = date(2025, 1, 1)
    dates = [d] * 30
    excess = np.zeros(30)                      # all tied
    dec = relative_deciles(dates, excess, min_names=30)
    assert len(set(dec.tolist())) == 1         # ties -> same bin, deterministic


def test_relative_deciles_excludes_thin_dates():
    dates = [date(2025, 1, 1)] * 10
    dec = relative_deciles(dates, np.arange(10, dtype=np.float64), min_names=30)
    assert (dec == -1).all()
