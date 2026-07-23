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
