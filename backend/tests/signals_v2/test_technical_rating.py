from app.services.signals_v2.labels import SignalLabel
from app.services.signals_v2.technical_rating import compute_technical_rating


def test_bullish_feature_set_returns_buy():
    rating = compute_technical_rating(
        {
            "last_close": 120,
            "price_sma20_ratio": 0.08,
            "price_sma50_ratio": 0.1,
            "price_sma200_ratio": 0.15,
            "rsi14": 58,
            "macd_hist": 2,
            "bb_position": 0.7,
            "stochastic_k": 60,
            "williams_r14": -35,
            "mfi14": 62,
            "volume_vs_20d": 1.5,
            "ret_5d": 0.04,
            "relative_strength_kse20": 0.04,
            "pe": 7,
        }
    )
    assert rating.signal in {SignalLabel.BUY, SignalLabel.STRONG_BUY}
    assert rating.score > 0
    assert rating.reasons


def test_conflicting_feature_set_resolves_near_hold():
    rating = compute_technical_rating(
        {
            "last_close": 100,
            "price_sma20_ratio": 0.02,
            "price_sma50_ratio": -0.02,
            "price_sma200_ratio": 0.0,
            "rsi14": 49,
            "macd_hist": -1,
            "bb_position": 0.5,
            "volume_vs_20d": 1.0,
            "ret_5d": 0.0,
            "relative_strength_kse20": 0.0,
        }
    )
    assert abs(rating.score) < 0.25
