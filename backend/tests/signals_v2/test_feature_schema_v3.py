import numpy as np

from app.services.signals_v2.training import (
    CORE_PRICE_FEATURES, SIGNAL_FEATURES_V3, has_core_features, vectorize_v3,
)


def test_v3_schema_excludes_fundamentals_includes_reversal():
    for f in ("pe", "pb", "roe", "div_yield", "payout"):
        assert f not in SIGNAL_FEATURES_V3
    for f in ("ret_120d", "ret_240d", "ret_240d_ex20"):
        assert f in SIGNAL_FEATURES_V3
    assert len(SIGNAL_FEATURES_V3) == 36


def test_vectorize_preserves_nan_not_zero():
    vec = vectorize_v3({"ret_5d": 0.02}, ["ret_5d", "rsi14"])
    assert vec[0] == 0.02
    assert np.isnan(vec[1])            # missing -> NaN, NOT 0.0


def test_has_core_features_gate():
    good = {k: 0.1 for k in CORE_PRICE_FEATURES}
    assert has_core_features(good)
    bad = dict(good); bad[CORE_PRICE_FEATURES[0]] = None
    assert not has_core_features(bad)
