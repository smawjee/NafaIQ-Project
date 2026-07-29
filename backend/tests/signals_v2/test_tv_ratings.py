import asyncio

import pytest

from app.services.market import tv_ratings


def test_tv_value_to_label_official_thresholds():
    assert tv_ratings.tv_value_to_label(0.75) == "STRONG_BUY"
    assert tv_ratings.tv_value_to_label(0.5) == "STRONG_BUY"
    assert tv_ratings.tv_value_to_label(0.3) == "BUY"
    assert tv_ratings.tv_value_to_label(0.1) == "BUY"
    assert tv_ratings.tv_value_to_label(0.0) == "HOLD"
    assert tv_ratings.tv_value_to_label(-0.09) == "HOLD"
    assert tv_ratings.tv_value_to_label(-0.3) == "SELL"
    assert tv_ratings.tv_value_to_label(-0.6) == "STRONG_SELL"
    assert tv_ratings.tv_value_to_label(None) is None


def test_consensus_agreement_buckets():
    assert tv_ratings.consensus_agreement("BUY", "STRONG_BUY") == "AGREES"
    assert tv_ratings.consensus_agreement("SELL", "STRONG_SELL") == "AGREES"
    assert tv_ratings.consensus_agreement("HOLD", "HOLD") == "AGREES"
    assert tv_ratings.consensus_agreement("BUY", "HOLD") == "MIXED"
    assert tv_ratings.consensus_agreement("STRONG_SELL", "HOLD") == "MIXED"
    assert tv_ratings.consensus_agreement("BUY", "SELL") == "DISAGREES"
    assert tv_ratings.consensus_agreement("STRONG_BUY", "STRONG_SELL") == "DISAGREES"
    assert tv_ratings.consensus_agreement("BUY", None) is None


def test_fetch_consensus_parses_scan_and_caches(monkeypatch):
    calls = {"n": 0}

    class _FakeScanner:
        async def scan(self, columns=None, sort_by="volume", sort_dir="desc", limit=500):
            calls["n"] += 1
            return [
                {"s": "PSX:HBL", "d": [0.6, 0.8, 0.4]},
                {"s": "PSX:OGDC", "d": [-0.2, -0.1, -0.3]},
                {"s": "PSX:BAD", "d": [None, None, None]},
            ]

    monkeypatch.setattr(tv_ratings, "get_scanner", lambda: _FakeScanner())
    tv_ratings._cache.clear()

    out = asyncio.run(tv_ratings.fetch_consensus("20D"))
    assert out["HBL"]["label"] == "STRONG_BUY"
    assert out["HBL"]["rating"] == 0.6
    assert out["HBL"]["ma_rating"] == 0.8
    assert out["HBL"]["source"] == "tradingview"
    assert out["OGDC"]["label"] == "SELL"
    assert "BAD" not in out                       # null ratings dropped

    asyncio.run(tv_ratings.fetch_consensus("20D"))
    assert calls["n"] == 1                        # second call served from TTL cache


def test_fetch_consensus_failure_returns_empty(monkeypatch):
    class _Boom:
        async def scan(self, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(tv_ratings, "get_scanner", lambda: _Boom())
    tv_ratings._cache.clear()
    assert asyncio.run(tv_ratings.fetch_consensus("20D")) == {}
