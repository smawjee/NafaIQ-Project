"""Context builders must hand the model real data, in the right order.

Each of these pins a wiring defect found by auditing the live bundles. They are
all silent failures: nothing raised, the report generated, and the model
narrated whatever it was given — nulls, untraded symbols, or a two-month-old
window presented as the recent trend.
"""
from __future__ import annotations

import importlib
from datetime import date, timedelta

import pytest

market_ctx = importlib.import_module("app.services.ai.context.market")
stock_ctx = importlib.import_module("app.services.ai.context.stock")


class _NoEvidence:
    """`evidence` is an injected parameter, not a module attribute."""

    async def retrieve(self, query, subject=None, k=5):
        return []


def _snapshot():
    return [
        {"symbol": "DEL", "change_pct": 10.03, "price": 22.17, "volume": 357500},
        {"symbol": "TATM", "change_pct": 10.0, "price": 145.11, "volume": 360148},
        # Halted/stale: keeps a change_pct but never traded.
        {"symbol": "IDSM", "change_pct": 10.0, "price": 0.0, "volume": 0},
        {"symbol": "TCORPR2", "change_pct": -24.79, "price": 0.0, "volume": 0},
        {"symbol": "MACFL", "change_pct": -10.0, "price": 63.43, "volume": 1059168},
        {"symbol": "FLAT", "change_pct": 0.0, "price": 10.0, "volume": 100},
    ]


def _sector_rows():
    return [
        {"sector": "POWER GENERATION & DISTRIBUTION", "avg_change_pct": 3.0, "stock_count": 15},
        {"sector": "TEXTILE SPINNING", "avg_change_pct": 2.34, "stock_count": 35},
        {"sector": "WOOLLEN", "avg_change_pct": -1.35, "stock_count": 1},
    ]


async def _build_market(monkeypatch):
    async def _cards():
        return [{"code": "KSE100", "close": 1.0, "prev_close": 1.0, "change": 0.0,
                 "change_pct": 0.0, "date": "2026-08-06"}]

    async def _snap():
        return _snapshot()

    async def _sectors():
        return _sector_rows()

    async def _ann(_sym, _n):
        return []

    monkeypatch.setattr(market_ctx.market_quotes, "index_cards", _cards)
    monkeypatch.setattr(market_ctx.market_quotes, "market_snapshot", _snap)
    monkeypatch.setattr(market_ctx.market_heatmap, "sector_averages", _sectors)
    monkeypatch.setattr(market_ctx.market_quotes, "announcements", _ann)
    return await market_ctx.build_market_brief_context(evidence=_NoEvidence())


# ---------- sectors ----------


async def test_sector_rotation_carries_real_names_and_percentages(monkeypatch):
    """`sector_averages()` is keyed 'sector'/'avg_change_pct', not 'name'/'pct'.

    Reading the wrong keys produced 42 rows of {name: null, pct: null}, so the
    brief's SECTOR ROTATION section — which the prompt explicitly demands — was
    written from nothing but nulls, every single day.
    """
    bundle = await _build_market(monkeypatch)
    sectors = bundle["sectors"]
    assert sectors, "sector rotation must not be empty"
    assert all(s["name"] for s in sectors)
    assert any(s["pct"] for s in sectors)
    assert sectors[0]["name"] == "POWER GENERATION & DISTRIBUTION"
    assert sectors[0]["pct"] == pytest.approx(3.0)
    # Breadth per sector: +1.5% across 4 names is not the signal +1.5% across 35 is.
    assert sectors[0]["stock_count"] == 15


# ---------- movers ----------


async def test_movers_exclude_symbols_that_did_not_trade(monkeypatch):
    """A stale listing keeps a last-known change_pct while reporting price 0 and
    volume 0. Because that figure sits at the extremes it won a top-5 slot
    outright — TCORPR2 was ranked the day's biggest loser having not traded."""
    bundle = await _build_market(monkeypatch)
    named = {m["symbol"] for m in bundle["movers"]["gainers"] + bundle["movers"]["losers"]}
    assert "IDSM" not in named
    assert "TCORPR2" not in named
    assert "DEL" in named and "MACFL" in named
    for m in bundle["movers"]["gainers"] + bundle["movers"]["losers"]:
        assert m["price"] > 0 and m["volume"] > 0


async def test_breadth_ignores_symbols_that_did_not_trade(monkeypatch):
    bundle = await _build_market(monkeypatch)
    b = bundle["breadth"]
    # DEL + TATM advance, MACFL declines, FLAT unchanged; the two untraded rows
    # count for nothing.
    assert (b["advancers"], b["decliners"], b["unchanged"]) == (2, 1, 1)


# ---------- stock history window ----------


def _bars(n: int, end: date = date(2026, 8, 6)):
    """`history()` returns NEWEST-FIRST — mirror that, with real dates.

    Calendar days, not trading days: the builder only sorts and slices, so the
    gaps a real week has make no difference to what is being pinned here.
    """
    return [
        {
            "symbol": "HBL",
            "date": (end - timedelta(days=i)).isoformat(),
            "open": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i,
            "close": 100.0 + i, "volume": 1000 + i,
        }
        for i in range(n)
    ]


async def _build_stock(monkeypatch, bars):
    async def _quote(_s):
        return {"symbol": "HBL", "price": 100.0}

    async def _fund(_s):
        return {"symbol": "HBL"}

    async def _prof(_s):
        return {"symbol": "HBL", "name": "HBL", "listed_shares": 100.0}

    async def _hist(_s, n):
        return bars[:n]

    async def _ann(_s, _n):
        return []

    async def _div(_s):
        return []

    monkeypatch.setattr(stock_ctx.market_quotes, "quote", _quote)
    monkeypatch.setattr(stock_ctx.market_quotes, "fundamentals", _fund)
    monkeypatch.setattr(stock_ctx.market_quotes, "profile", _prof)
    monkeypatch.setattr(stock_ctx.market_history, "history", _hist)
    monkeypatch.setattr(stock_ctx.market_quotes, "announcements", _ann)
    monkeypatch.setattr(stock_ctx.market_quotes, "dividends", _div)
    return await stock_ctx.build_stock_analysis_context(
        subject="HBL", evidence=_NoEvidence()
    )


async def test_price_history_is_the_most_recent_window_in_order(monkeypatch):
    """`history()` is newest-first, so `hist[-30:]` took the THIRTY OLDEST bars
    and labelled them the recent trend — on 2026-08-06 that was a window ending
    two months earlier, listed backwards."""
    bundle = await _build_stock(monkeypatch, _bars(300))
    ph = bundle["price_history"]
    dates = [p["date"] for p in ph]
    assert dates == sorted(dates), "price history must run oldest -> newest"
    assert dates[-1] == "2026-08-06", "must end on the newest bar"


async def test_long_moving_average_resolves(monkeypatch):
    """SMA200 needs 200 closes; fetching only the 60-bar display window made the
    deepest indicator the prompt asks for null on every stock report."""
    bundle = await _build_stock(monkeypatch, _bars(300))
    assert bundle["indicators"].get("sma200") is not None


async def test_display_window_stays_bounded_even_though_more_is_fetched(monkeypatch):
    bundle = await _build_stock(monkeypatch, _bars(300))
    assert bundle["price_range"]["bars"] == 60
    assert len(bundle["price_history"]) == 30


async def test_short_history_degrades_without_raising(monkeypatch):
    """A newly-listed symbol has far fewer than 200 bars."""
    bundle = await _build_stock(monkeypatch, _bars(20))
    assert bundle["indicators"].get("sma200") is None
    assert bundle["price_history"]
