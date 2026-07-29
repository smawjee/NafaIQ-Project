from app.services.signals_v2.trend_state import TrendAssessment, classify_trend


def _feats(**kw):
    base = {
        "last_close": 100.0, "sma50": 95.0, "sma200": 90.0,
        "price_sma50_ratio": 100.0 / 95.0 - 1, "price_sma200_ratio": 100.0 / 90.0 - 1,
        "ret_20d": 0.04, "ret_60d": 0.10, "dist_52w_high": -0.05, "dist_52w_low": 0.40,
        "volatility_20d": 0.25, "atr14_pct": 0.02,
    }
    base.update(kw)
    return base


def test_uptrend_detected():
    t = classify_trend(_feats())
    assert t.state == "UPTREND" and t.score > 0
    assert any("50" in e or "200" in e for e in t.evidence)


def test_downtrend_detected():
    t = classify_trend(_feats(last_close=80.0, sma50=88.0, sma200=95.0,
                              price_sma50_ratio=80 / 88 - 1, price_sma200_ratio=80 / 95 - 1,
                              ret_20d=-0.06, ret_60d=-0.15,
                              dist_52w_high=-0.30, dist_52w_low=0.05))
    assert t.state == "DOWNTREND" and t.score < 0


def test_weakening_above_200_below_50():
    t = classify_trend(_feats(last_close=93.0, sma50=95.0, sma200=90.0,
                              price_sma50_ratio=93 / 95 - 1, price_sma200_ratio=93 / 90 - 1,
                              ret_20d=-0.03, ret_60d=0.02))
    assert t.state == "WEAKENING"


def test_basing_near_52w_low_with_bounce():
    t = classify_trend(_feats(last_close=85.0, sma50=88.0, sma200=95.0,
                              price_sma50_ratio=85 / 88 - 1, price_sma200_ratio=85 / 95 - 1,
                              ret_20d=0.05, ret_60d=-0.10, dist_52w_low=0.08))
    assert t.state == "BASING"


def test_unknown_when_missing_mas():
    t = classify_trend({"ret_20d": 0.02})
    assert t.state == "UNKNOWN" and t.score == 0.0


def test_ratio_only_classification_matches():
    # store vectors carry ratios but not raw sma50/sma200 — same verdicts required
    up = _feats()
    down = _feats(last_close=80.0, sma50=88.0, sma200=95.0,
                  price_sma50_ratio=80 / 88 - 1, price_sma200_ratio=80 / 95 - 1,
                  ret_20d=-0.06, ret_60d=-0.15, dist_52w_high=-0.30, dist_52w_low=0.05)
    for feats, expected in ((up, "UPTREND"), (down, "DOWNTREND")):
        stripped = {k: v for k, v in feats.items() if k not in ("sma50", "sma200", "last_close")}
        assert classify_trend(stripped).state == expected


import importlib.util
import sys
from pathlib import Path

from app.services.signals_v2.trend_state import render_trend_warnings, risk_metrics

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "signals" / "calibrate_trend_stats.py"
_spec = importlib.util.spec_from_file_location("calibrate_trend_stats", _SCRIPT)
_cal = importlib.util.module_from_spec(_spec)
sys.modules["calibrate_trend_stats"] = _cal
_spec.loader.exec_module(_cal)


def test_risk_metrics_from_snapshot():
    m = risk_metrics(_feats(volatility_20d=0.40, atr14_pct=0.025), classify_trend(_feats()))
    assert abs(m["annualized_volatility"] - 0.40) < 1e-9
    assert abs(m["expected_20d_move_pct"] - 0.40 * (20 / 252) ** 0.5) < 1e-4
    assert abs(m["suggested_stop_pct"] - 0.05) < 1e-9          # 2 x 2.5% ATR
    assert m["position_risk"] == "MODERATE"
    assert m["continuation"] is None                            # no stats passed


def test_risk_metrics_stop_floor_and_extreme_vol():
    m = risk_metrics(_feats(volatility_20d=0.90, atr14_pct=0.005), classify_trend(_feats()))
    assert m["suggested_stop_pct"] == 0.03                      # 3% floor
    assert m["position_risk"] == "EXTREME"


def test_measure_continuation_counts_and_rates():
    pairs = [("DOWNTREND", -0.05), ("DOWNTREND", -0.02), ("DOWNTREND", 0.03),
             ("UPTREND", 0.04), ("UPTREND", -0.01)]
    stats = _cal.measure_continuation(pairs)
    assert stats["DOWNTREND"]["n"] == 3
    assert abs(stats["DOWNTREND"]["p_negative_20d"] - 2 / 3) < 1e-4
    assert stats["UPTREND"]["n"] == 2


def test_warnings_show_numbers_only_with_stats():
    trend = classify_trend(_feats(last_close=80.0, sma50=88.0, sma200=95.0,
                                  price_sma50_ratio=80 / 88 - 1, price_sma200_ratio=80 / 95 - 1,
                                  ret_20d=-0.06, ret_60d=-0.15,
                                  dist_52w_high=-0.30, dist_52w_low=0.05))
    no_stats = render_trend_warnings(trend, risk_metrics(_feats(), trend))
    assert any("downtrend" in w.lower() for w in no_stats)
    assert not any("historically" in w.lower() for w in no_stats)

    stats = {"states": {"DOWNTREND": {"n": 500, "p_negative_20d": 0.62, "median_20d_return": -0.031}}}
    with_stats = render_trend_warnings(trend, risk_metrics(_feats(), trend, stats=stats))
    assert any("62%" in w for w in with_stats)                  # measured, not invented
