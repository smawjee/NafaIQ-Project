import numpy as np
import pytest

from app.services.signals_v2.explain import render_ai_reasons, top_contributions
from app.services.signals_v2.training import SIGNAL_FEATURES_V3


def _planted_model_and_vector():
    xgboost = pytest.importorskip("xgboost")
    rng = np.random.default_rng(2)
    n = 400
    X = rng.normal(0, 1, (n, len(SIGNAL_FEATURES_V3)))
    y = X[:, 0] * 2.0 - X[:, 1] * 1.5 + rng.normal(0, 0.1, n)   # features 0 and 1 dominate
    model = xgboost.XGBRegressor(n_estimators=50, max_depth=3, random_state=0)
    model.fit(X, y)
    vec = np.zeros(len(SIGNAL_FEATURES_V3))
    vec[0] = 2.0    # pushes prediction up
    vec[1] = 2.0    # pushes prediction down
    return model, vec


def test_top_contributions_disjoint_and_bounded():
    model, vec = _planted_model_and_vector()
    out = top_contributions(model, vec, SIGNAL_FEATURES_V3, k=3)
    pos_names = {name for name, _ in out["positive"]}
    neg_names = {name for name, _ in out["negative"]}
    assert len(out["positive"]) <= 3 and len(out["negative"]) <= 3
    assert not (pos_names & neg_names)
    assert SIGNAL_FEATURES_V3[0] in pos_names       # planted positive driver
    assert SIGNAL_FEATURES_V3[1] in neg_names       # planted negative driver
    for _, v in out["positive"]:
        assert v > 0
    for _, v in out["negative"]:
        assert v < 0


def test_fundamentals_never_appear_in_contributions():
    model, vec = _planted_model_and_vector()
    out = top_contributions(model, vec, SIGNAL_FEATURES_V3, k=5)
    names = {name for name, _ in out["positive"] + out["negative"]}
    for f in ("pe", "pb", "roe", "div_yield", "payout"):
        assert f not in names                       # not model features at all


def test_render_ai_reasons_notes_contributions_not_causation():
    factors = {"ranker": {"positive": [["ret_20d", 0.4]], "negative": [["rsi14", -0.2]]},
               "absolute": {"positive": [], "negative": []}}
    reasons = render_ai_reasons(factors)
    assert any("ret_20d" in r for r in reasons)
    assert any("contribution" in r.lower() for r in reasons)


def test_render_ai_reasons_empty_factors():
    assert render_ai_reasons({}) == []
    assert render_ai_reasons(None) == []
