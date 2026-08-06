from app.services.signals.risk import assess_risk, liquidity_score


def test_low_liquidity_adds_hold_cap():
    risk = assess_risk({"atr14_pct": 0.02, "volatility_20d": 0.1}, freshness="LIVE", liquidity=10)
    assert "MAX_HOLD_LOW_LIQUIDITY" in risk.caps


def test_stale_data_blocks_signal():
    risk = assess_risk({"atr14_pct": 0.02, "volatility_20d": 0.1}, freshness="STALE", liquidity=80)
    assert "NO_SIGNAL_STALE_DATA" in risk.caps


def test_liquidity_score_uses_turnover_and_volume():
    assert liquidity_score({"turnover": 10_000_000, "volume": 200_000}) > 50
