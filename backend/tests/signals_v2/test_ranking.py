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


def test_build_ranking_dataset_grid_stride_override_densifies_dates():
    rng = np.random.default_rng(7)
    histories = {}
    for i in range(35):
        closes = (100 * np.cumprod(1 + rng.normal(0.0005, 0.02, 420))).tolist()
        histories[f"S{i:02d}"] = [dict(r, symbol=f"S{i:02d}") for r in _hist(closes)]
    kse = _hist((1000 * np.cumprod(1 + rng.normal(0.0004, 0.01, 420))).tolist())
    kse_rows = [{"date": r["date"], "close": r["close"]} for r in kse]

    coarse = build_ranking_dataset(histories=histories, fundamentals={}, profiles={},
                                   kse_rows=kse_rows, horizon="20D",
                                   min_names_per_date=30, grid_stride=20)
    dense = build_ranking_dataset(histories=histories, fundamentals={}, profiles={},
                                  kse_rows=kse_rows, horizon="20D",
                                  min_names_per_date=30, grid_stride=5)
    assert len(set(dense.feature_dates)) > len(set(coarse.feature_dates))


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


def test_train_ranker_recovers_planted_alpha():
    pytest.importorskip("xgboost")
    from app.services.signals_v2.ranking import RankingDataset, train_ranker
    from app.services.signals_v2.training import SIGNAL_FEATURES_V3

    rng = np.random.default_rng(11)
    n_dates, names = 50, 40
    base = date(2022, 1, 3)
    fdates, X, fwd, bench, syms, secs, edts, xdts = [], [], [], [], [], [], [], []
    for k in range(n_dates):
        d = base + timedelta(days=7 * k)
        alpha = rng.normal(0, 0.03, names)
        feats = rng.normal(0, 1, (names, len(SIGNAL_FEATURES_V3)))
        feats[:, 0] = alpha / 0.03 + rng.normal(0, 0.3, names)   # feature 0 ~ alpha
        market = rng.normal(0.002, 0.01)
        for j in range(names):
            fdates.append(d); syms.append(f"S{j:02d}"); secs.append("SEC")
            edts.append(d + timedelta(days=1)); xdts.append(d + timedelta(days=21))
            X.append(feats[j]); fwd.append(market + alpha[j]); bench.append(market)
    fwd, bench = np.asarray(fwd), np.asarray(bench)
    from app.services.signals_v2.ranking import relative_deciles
    dec = relative_deciles(fdates, fwd - bench, min_names=30)
    ds = RankingDataset(
        X=np.asarray(X), y=np.asarray([str(int(v)) for v in dec], dtype=object),
        dates=fdates, symbols=syms, forward_returns=fwd, benchmark_forward_returns=bench,
        technical_labels=np.asarray(["HOLD"] * len(fdates), dtype=object),
        feature_names=list(SIGNAL_FEATURES_V3), feature_dates=fdates, entry_dates=edts,
        exit_dates=xdts, sectors=secs)
    result = train_ranker(ds, horizon="20D", folds=3)
    assert result["metrics"]["daily_rank_ic"] > 0.5
    assert result["metrics"]["top_decile_excess_after_cost"] > 0
    assert len(result["oos"]) > 0
    o = result["oos"][0]
    assert o.entry_date > o.feature_date and 0.0 <= o.percentile <= 1.0
    assert result["model"].predict(ds.X[:1]).shape == (1,)


def test_join_oos_key_based_and_1to1():
    from app.services.signals_v2.ranking import (
        AbsoluteOOSPrediction, CombinedOOSPrediction, RankerOOSPrediction, join_oos)
    d = date(2024, 1, 1)
    r = [RankerOOSPrediction(1, "A", "S", d, d + timedelta(days=1), d + timedelta(days=21),
                             "20D", 0.5, 0.9, 0.03, 0.01, 0.02, "HOLD"),
         RankerOOSPrediction(2, "B", "S", d, d + timedelta(days=1), d + timedelta(days=21),
                             "20D", 0.1, 0.2, -0.01, 0.01, -0.02, "SELL")]
    a = [AbsoluteOOSPrediction(2, "B", d, "20D", 0.3, -0.005),
         AbsoluteOOSPrediction(1, "A", d, "20D", 0.7, 0.02)]     # deliberately shuffled
    combined = join_oos(r, a)
    assert len(combined) == 2
    by_sym = {c.symbol: c for c in combined}
    assert by_sym["A"].absolute_regression_score == 0.02       # joined by KEY, not position
    assert by_sym["B"].absolute_class_score == 0.3
    assert isinstance(combined[0], CombinedOOSPrediction)


def test_join_oos_raises_on_mismatch():
    from app.services.signals_v2.ranking import AbsoluteOOSPrediction, RankerOOSPrediction, join_oos
    d = date(2024, 1, 1)
    r = [RankerOOSPrediction(1, "A", "S", d, d, d, "20D", 0.5, 0.9, 0.0, 0.0, 0.0, "HOLD")]
    with pytest.raises(ValueError):
        join_oos(r, [])                                          # no matching absolute record


def test_dual_calibrator_monotone_and_wraps():
    from dataclasses import replace

    from app.services.signals_v2.ranking import CombinedOOSPrediction, DualCalibrator
    rng = np.random.default_rng(3)
    d = date(2024, 1, 1)
    combined = []
    for i in range(3000):
        pct = rng.uniform(0, 1)
        cls = rng.uniform(0, 1)
        exc = (pct - 0.5) * 0.1
        absr = (cls - 0.5) * 0.08
        combined.append(CombinedOOSPrediction(
            i, f"S{i}", "SEC", d, d, d, "20D", pct, pct, exc + 0.0, 0.0, exc,
            "HOLD", cls, absr))
    cal = DualCalibrator.fit(combined)
    hi = cal.apply(replace(combined[0], percentile=0.95, absolute_class_score=0.95))
    lo = cal.apply(replace(combined[0], percentile=0.05, absolute_class_score=0.05))
    assert hi.p_beat_market > lo.p_beat_market
    assert hi.p_positive_absolute > lo.p_positive_absolute
    assert hi.calibration_support > 0


def test_symmetric_policy_gates():
    from app.services.signals_v2.ranking import rank_to_signal

    def sig(pct, pb, ee, pp, ea, q=True, liq=True, risk=True, sup=True):
        return rank_to_signal(percentile=pct, p_beat_market=pb, expected_excess_net=ee,
                              p_positive_absolute=pp, expected_absolute_net=ea,
                              data_quality_ok=q, liquidity_ok=liq, risk_ok=risk,
                              calibration_support_ok=sup)

    # top rank + all positives + gates -> STRONG BUY / BUY
    assert sig(0.98, 0.65, 0.02, 0.65, 0.03) == SignalLabel.STRONG_BUY
    assert sig(0.92, 0.60, 0.01, 0.60, 0.01) == SignalLabel.BUY
    # top rank but absolute expectation negative -> HOLD (not BUY)
    assert sig(0.98, 0.65, 0.02, 0.65, -0.005) == SignalLabel.HOLD
    # top rank but low conviction -> HOLD
    assert sig(0.98, 0.50, 0.02, 0.65, 0.03) == SignalLabel.HOLD
    # bottom rank BUT positive absolute expectation -> HOLD (underperformer, NOT sell)
    assert sig(0.05, 0.30, -0.03, 0.60, 0.01) == SignalLabel.HOLD
    # bottom rank + negative absolute + low P(positive) -> SELL / STRONG SELL
    assert sig(0.05, 0.30, -0.03, 0.30, -0.02) == SignalLabel.SELL
    assert sig(0.01, 0.20, -0.05, 0.20, -0.04) == SignalLabel.STRONG_SELL
    # any gate fails -> NO_SIGNAL
    assert sig(0.98, 0.65, 0.02, 0.65, 0.03, q=False) == SignalLabel.NO_SIGNAL
    assert sig(0.98, 0.65, 0.02, 0.65, 0.03, sup=False) == SignalLabel.NO_SIGNAL


def test_score_layer_percentiles_within_date_and_key_alignment():
    pytest.importorskip("xgboost")
    pytest.importorskip("lightgbm")
    from app.services.signals_v2.ranking import (
        RankingDataset, score_layer, train_absolute_model, train_ranker)
    from app.services.signals_v2.training import SIGNAL_FEATURES_V3

    rng = np.random.default_rng(5)
    n_dates, names = 60, 35
    base = date(2022, 1, 3)
    fdates, X, fwd, bench, syms, secs, edts, xdts = [], [], [], [], [], [], [], []
    for k in range(n_dates):
        d = base + timedelta(days=7 * k)
        alpha = rng.normal(0, 0.03, names)
        feats = rng.normal(0, 1, (names, len(SIGNAL_FEATURES_V3)))
        feats[:, 0] = alpha / 0.03 + rng.normal(0, 0.3, names)
        for j in range(names):
            fdates.append(d); syms.append(f"S{j:02d}"); secs.append("SEC")
            edts.append(d + timedelta(days=1)); xdts.append(d + timedelta(days=21))
            X.append(feats[j]); fwd.append(0.002 + alpha[j]); bench.append(0.002)
    fwd, bench = np.asarray(fwd), np.asarray(bench)
    from app.services.signals_v2.ranking import relative_deciles, three_layer_split
    dec = relative_deciles(fdates, fwd - bench, min_names=30)
    ds = RankingDataset(
        X=np.asarray(X), y=np.asarray([str(int(v)) for v in dec], dtype=object),
        dates=fdates, symbols=syms, forward_returns=fwd, benchmark_forward_returns=bench,
        technical_labels=np.asarray(["HOLD"] * len(fdates), dtype=object),
        feature_names=list(SIGNAL_FEATURES_V3), feature_dates=fdates, entry_dates=edts,
        exit_dates=xdts, sectors=secs)
    layers = three_layer_split(ds.feature_dates, min_support={"dev": 20, "calibration": 5, "holdout": 5})
    ranker = train_ranker(ds, horizon="20D", split_indices=layers["dev"], folds=3,
                          configs=[{"name": "t", "learning_rate": 0.05, "max_depth": 3, "n_estimators": 60}])
    absolute = train_absolute_model(ds, horizon="20D", split_indices=layers["dev"], folds=3)
    records = score_layer(ranker["model"], absolute["clf"], absolute["reg"], ds,
                          layers["calibration"], "20D")
    assert len(records) == len(layers["calibration"])
    cal_dates = {ds.feature_dates[i] for i in layers["calibration"]}
    for r in records:
        assert r.feature_date in cal_dates                       # only calibration layer scored
        assert 0.0 <= r.percentile <= 1.0
        assert r.forward_return == float(ds.forward_returns[r.sample_index])   # key-aligned
    # percentiles span the full range within each date's cross-section
    one_date = next(iter(cal_dates))
    day = [r.percentile for r in records if r.feature_date == one_date]
    assert min(day) == 0.0 and max(day) == 1.0
