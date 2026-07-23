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
