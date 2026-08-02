import asyncio

import pytest

from app.services.market import flow_context


def test_classify_flow_trend():
    assert flow_context.classify_flow_trend(5e8, 2e9) == "FOREIGN_BUYING"
    assert flow_context.classify_flow_trend(-5e8, -2e9) == "FOREIGN_SELLING"
    assert flow_context.classify_flow_trend(5e8, -2e9) == "MIXED"
    assert flow_context.classify_flow_trend(-1e6, 2e9) == "MIXED"
    assert flow_context.classify_flow_trend(0.0, 0.0) == "NEUTRAL"


def test_get_flow_context_aggregates_foreign_types(monkeypatch):
    rows = [
        # newest first, two foreign types per day
        {"trade_date": "2026-07-22", "client_type": "FOREIGN CORPORATES",
         "net_value_pkr": 100.0, "net_value_usd": 1.0},
        {"trade_date": "2026-07-22", "client_type": "OVERSEAS PAKISTANI",
         "net_value_pkr": -30.0, "net_value_usd": -0.3},
        {"trade_date": "2026-07-21", "client_type": "FOREIGN CORPORATES",
         "net_value_pkr": 50.0, "net_value_usd": 0.5},
    ]

    async def fake_query(days=40):
        return rows

    monkeypatch.setattr(flow_context, "_foreign_rows", fake_query)
    flow_context._cache.clear()
    ctx = asyncio.run(flow_context.get_flow_context())
    assert ctx["foreign_net_5d_pkr"] == 120.0          # (100-30) + 50
    assert ctx["foreign_net_20d_pkr"] == 120.0
    assert ctx["last_date"] == "2026-07-22"
    assert ctx["trend"] == "FOREIGN_BUYING"
    assert ctx["source"] == "nccpl-via-finhisaab"


def test_get_flow_context_none_when_no_data(monkeypatch):
    async def empty(days=40):
        return []

    monkeypatch.setattr(flow_context, "_foreign_rows", empty)
    flow_context._cache.clear()
    assert asyncio.run(flow_context.get_flow_context()) is None


def test_get_flow_context_tolerates_failure(monkeypatch):
    async def boom(days=40):
        raise RuntimeError("db down")

    monkeypatch.setattr(flow_context, "_foreign_rows", boom)
    flow_context._cache.clear()
    assert asyncio.run(flow_context.get_flow_context()) is None
