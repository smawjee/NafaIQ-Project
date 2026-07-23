import asyncio
from datetime import datetime, timezone

import pytest

import app.services.signals_v2.engine as engine
from app.services.signals_v2.schemas import SignalV2Response


def _response(**overrides):
    base = dict(
        symbol="HBL", horizon="20D", signal="BUY", confidence=60.0, rank_score=0.4,
        technical_signal="BUY", technical_score=0.4, risk_level="MODERATE",
        regime="NEUTRAL", freshness="LIVE", reasons=[], warnings=[],
        indicator_votes=[], features_snapshot={}, model_version="technical-v2.0",
        engine_version="signals-v2", predicted_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return SignalV2Response(**base)


def test_response_consensus_fields_default_none():
    r = _response()
    assert r.consensus is None
    assert r.consensus_agreement is None


def test_attach_consensus_populates_from_tv(monkeypatch):
    async def fake_fetch(horizon="20D"):
        return {"HBL": {"rating": 0.6, "ma_rating": 0.7, "oscillator_rating": 0.4,
                        "label": "STRONG_BUY", "source": "tradingview", "as_of": "x"}}

    monkeypatch.setattr(engine.tv_ratings, "fetch_consensus", fake_fetch)
    out = asyncio.run(engine._attach_consensus(_response(), "20D"))
    assert out.consensus["label"] == "STRONG_BUY"
    assert out.consensus["source"] == "tradingview"
    assert out.consensus_agreement == "AGREES"       # our BUY vs their STRONG_BUY


def test_attach_consensus_tolerates_failure(monkeypatch):
    async def boom(horizon="20D"):
        raise RuntimeError("tv down")

    monkeypatch.setattr(engine.tv_ratings, "fetch_consensus", boom)
    out = asyncio.run(engine._attach_consensus(_response(), "20D"))
    assert out.consensus is None and out.consensus_agreement is None


def test_attach_trend_populates_state_and_warnings():
    feats = {"last_close": 80.0, "sma50": 88.0, "sma200": 95.0,
             "price_sma50_ratio": 80 / 88 - 1, "price_sma200_ratio": 80 / 95 - 1,
             "ret_20d": -0.06, "ret_60d": -0.15, "dist_52w_high": -0.30,
             "dist_52w_low": 0.05, "volatility_20d": 0.30, "atr14_pct": 0.02}
    out = engine._attach_trend(_response(), feats, stats=None)
    assert out.trend_state == "DOWNTREND"
    assert out.trend_score < 0
    assert out.risk_metrics["suggested_stop_pct"] >= 0.03
    assert any("downtrend" in w.lower() for w in out.warnings)


def test_attach_trend_unknown_keeps_response_clean():
    out = engine._attach_trend(_response(), {}, stats=None)
    assert out.trend_state == "UNKNOWN"
    assert out.risk_metrics is not None
    assert out.warnings == []                                   # no noise for UNKNOWN/RANGE
