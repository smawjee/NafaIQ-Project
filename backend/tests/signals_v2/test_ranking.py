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


from app.services.signals_v2.ranking import purged_date_splits, three_layer_split


def _grid(n_dates, names, start=date(2023, 1, 2), step=7, label_span=20):
    fdates, ldates = [], []
    for k in range(n_dates):
        d = start + timedelta(days=k * step)
        for _ in range(names):
            fdates.append(d)
            ldates.append(d + timedelta(days=label_span))
    return fdates, ldates


def test_purged_splits_no_label_overlap():
    fdates, ldates = _grid(60, 5)
    splits = purged_date_splits(fdates, ldates, folds=4, min_train_dates=5)
    assert len(splits) >= 2
    ford = np.asarray([d.toordinal() for d in fdates])
    lord = np.asarray([d.toordinal() for d in ldates])
    for train_idx, test_idx in splits:
        test_start = ford[test_idx].min()
        assert lord[train_idx].max() < test_start        # no label leaks into test
        assert len(set(train_idx) & set(test_idx)) == 0


def test_three_layer_split_disjoint_and_ordered():
    fdates, _ = _grid(100, 3)
    layers = three_layer_split(fdates)
    dev, cal, hold = layers["dev"], layers["calibration"], layers["holdout"]
    ford = np.asarray([d.toordinal() for d in fdates])
    assert ford[dev].max() < ford[cal].min() < ford[hold].min()
    assert len(set(dev) & set(cal)) == 0 and len(set(cal) & set(hold)) == 0


def test_three_layer_split_inconclusive_when_tiny():
    fdates, _ = _grid(5, 2)
    layers = three_layer_split(fdates, min_support={"dev": 20, "calibration": 5, "holdout": 5})
    assert layers.get("status") == "INCONCLUSIVE"


from app.services.signals_v2.ranking import build_ranking_dataset, eligible_universe
from app.services.signals_v2.training import SIGNAL_FEATURES_V3


def _hist(closes, start=date(2023, 1, 2)):
    rows, d = [], start
    for c in closes:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        rows.append({"symbol": "X", "date": d.isoformat(), "open": c, "high": c * 1.01,
                     "low": c * 0.99, "close": c, "volume": 50_000})
        d += timedelta(days=1)
    return rows


def test_build_ranking_dataset_execution_aligned():
    rng = np.random.default_rng(7)
    histories = {}
    for i in range(35):
        closes = (100 * np.cumprod(1 + rng.normal(0.0005, 0.02, 420))).tolist()
        histories[f"S{i:02d}"] = [dict(r, symbol=f"S{i:02d}") for r in _hist(closes)]
    kse = _hist((1000 * np.cumprod(1 + rng.normal(0.0004, 0.01, 420))).tolist())
    kse_rows = [{"date": r["date"], "close": r["close"]} for r in kse]

    ds = build_ranking_dataset(histories=histories, fundamentals={}, profiles={},
                               kse_rows=kse_rows, horizon="20D", min_names_per_date=30)
    assert len(ds.y) > 0
    assert ds.X.shape[1] == len(SIGNAL_FEATURES_V3)
    # entry date is strictly AFTER feature date (T+1 convention), exit after entry
    for fdt, edt, xdt in zip(ds.feature_dates, ds.entry_dates, ds.exit_dates):
        assert edt > fdt
        assert xdt > edt
    from collections import Counter
    assert min(Counter(ds.dates).values()) >= 30      # thin dates dropped


def test_forward_return_uses_entry_not_feature_close():
    # deterministic 1% up per bar: return over 20 sessions from entry must be (1.01^20 - 1),
    # NOT include the T->T+1 step twice.
    closes = [100.0 * (1.01 ** i) for i in range(320)]
    histories = {f"S{i:02d}": [dict(r, symbol=f"S{i:02d}") for r in _hist(closes)] for i in range(35)}
    kse = _hist([1000.0] * 320)
    kse_rows = [{"date": r["date"], "close": r["close"]} for r in kse]
    ds = build_ranking_dataset(histories=histories, fundamentals={}, profiles={},
                               kse_rows=kse_rows, horizon="20D", min_names_per_date=30)
    # entry_close = 1.01^(t+1), exit_close = 1.01^(t+1+20) -> return = 1.01^20 - 1
    assert np.allclose(ds.forward_returns, 1.01 ** 20 - 1, atol=1e-6)


def test_eligible_universe_filters_short_and_illiquid():
    good = {f"S{i}": [dict(r, symbol=f"S{i}") for r in _hist([100.0] * 300)] for i in range(3)}
    good["SHORT"] = [dict(r, symbol="SHORT") for r in _hist([100.0] * 50)]
    as_of = date.fromisoformat(good["S0"][-1]["date"])
    universe = eligible_universe(good, as_of)
    assert "SHORT" not in universe and "S0" in universe
