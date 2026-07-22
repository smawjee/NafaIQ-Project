import numpy as np
from datetime import date, timedelta

from app.services.signals_v2.portfolio_sim import simulate_topk


def _series(dates, start, drift):
    p, out = start, {}
    for d in dates:
        out[d] = p
        p *= (1 + drift)
    return out


def test_simulator_beats_flat_market_when_picks_rise_faster():
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(60)]
    winners = {s: _series(dates, 100, 0.01) for s in ("A", "B", "C")}   # +1%/day
    losers = {s: _series(dates, 100, 0.0) for s in ("D", "E")}          # flat
    prices = {**winners, **losers}
    kse = _series(dates, 1000, 0.002)                                   # +0.2%/day
    picks = {d: ["A", "B", "C"] for d in dates}
    res = simulate_topk(picks, prices, kse, k=3, rebalance_days=5)
    assert res["net_return"] > kse[dates[-1]] / kse[dates[0]] - 1
    assert res["nav_returns"].ndim == 1 and len(res["nav_returns"]) > 0
    assert -1.0 <= res["max_drawdown"] <= 0.0


def test_simulator_holds_cash_when_no_picks():
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(20)]
    prices = {"A": _series(dates, 100, 0.05)}
    kse = _series(dates, 1000, 0.0)
    picks = {d: [] for d in dates}
    res = simulate_topk(picks, prices, kse, k=3, rebalance_days=5)
    assert abs(res["net_return"]) < 1e-9      # all cash -> flat NAV
