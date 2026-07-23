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


# --- v3.0: full TradingView-style MA + oscillator consensus ---

def _features(*, ma_ratio, rsi, macd, stoch, cci, wr, mfi, roc, bb):
    f = {"last_close": 100.0}
    for p in (10, 20, 30, 50, 100, 200):
        f[f"price_sma{p}_ratio"] = ma_ratio
        f[f"price_ema{p}_ratio"] = ma_ratio
    f.update({
        "rsi14": rsi, "macd_hist": macd, "stochastic_k": stoch,
        "cci20": cci, "williams_r14": wr, "mfi14": mfi, "roc10": roc,
        "bb_position": bb,
    })
    return f


_BULLISH = dict(ma_ratio=0.05, rsi=60, macd=0.5, stoch=60, cci=120, wr=-40, mfi=60, roc=0.05, bb=0.6)
_BEARISH = dict(ma_ratio=-0.05, rsi=40, macd=-0.5, stoch=30, cci=-120, wr=-70, mfi=35, roc=-0.05, bb=1.2)


def test_all_bullish_indicators_give_strong_buy():
    r = compute_technical_rating(_features(**_BULLISH))
    assert r.signal is SignalLabel.STRONG_BUY
    assert r.ma_score == 1.0
    assert r.osc_score >= 0.75


def test_all_bearish_indicators_give_strong_sell():
    r = compute_technical_rating(_features(**_BEARISH))
    assert r.signal is SignalLabel.STRONG_SELL
    assert r.ma_score == -1.0
    assert r.osc_score <= -0.75


def test_full_indicator_basket_is_scored():
    r = compute_technical_rating(_features(**_BULLISH))
    ma_votes = [v for v in r.votes if v.name.startswith(("SMA", "EMA"))]
    names = {v.name for v in r.votes}
    assert len(ma_votes) == 12  # SMA + EMA at 10/20/30/50/100/200
    assert {"RSI14", "MACD", "CCI20", "ROC10", "STOCHASTIC", "MFI14"} <= names


def test_bullish_ma_bearish_oscillators_net_to_hold():
    mixed = dict(_BEARISH)
    mixed["ma_ratio"] = 0.05  # MAs bullish, oscillators bearish -> net ~0
    r = compute_technical_rating(_features(**mixed))
    assert r.signal is SignalLabel.HOLD


def test_reasons_summarize_ma_and_oscillator_consensus():
    r = compute_technical_rating(_features(**_BULLISH))
    joined = " ".join(r.reasons)
    assert "Moving averages" in joined
    assert "Oscillators" in joined
