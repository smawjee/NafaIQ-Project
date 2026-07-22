from app.services.signals_v2 import constants as C


def test_v3_constants_present_and_consistent():
    assert C.MIN_REQUIRED_BARS == C.MAX_FEATURE_LOOKBACK + C.FEATURE_SAFETY_BARS == 260
    assert C.ROUND_TRIP_COST == 2 * C.ONE_WAY_COST == 0.005
    assert C.TRAINING_GRID_STRIDE["20D"] == 10
    assert C.PORTFOLIO_REBALANCE_DAYS["20D"] == 5
    assert C.MAX_ENTRY_DELAY_TRADING_DAYS == 2
    # training stride and rebalance cadence are DISTINCT concepts
    assert C.TRAINING_GRID_STRIDE != C.PORTFOLIO_REBALANCE_DAYS
