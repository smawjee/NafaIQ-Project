"""Tests for the per-symbol round-trip cost model.

A research verdict is decided *after cost*, so a silent bug here decides the
programme. The first Corwin-Schultz-based version of this module passed a suite
much like this one and was still wrong on real data: it was flat in liquidity
and tracked volatility instead of spread. The tests below therefore pin the two
*structural* properties that failure violated, not just the arithmetic.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.services.signals.costs import (
    CostParams,
    corwin_schultz_spread,
    liquidity_spread,
    round_trip_cost,
    round_trip_cost_from_bars,
)


def _bars(n: int, *, price: float = 100.0, volume: float = 100_000,
          vol: float = 0.0) -> list[dict]:
    rng = np.random.default_rng(7)
    rows, p = [], price
    for i in range(n):
        if vol:
            p *= float(np.exp(rng.normal(0.0, vol)))
        rows.append({
            "date": f"2024-01-{(i % 28) + 1:02d}",
            "open": p, "high": p * 1.01, "low": p * 0.99,
            "close": p, "volume": volume,
        })
    return rows


# --- the two properties the previous model failed -------------------------


def test_spread_is_strictly_decreasing_in_turnover():
    """The failure that invalidated the first round of results.

    The Corwin-Schultz version estimated 0.95% for a name trading PKR 18k/day
    and 0.80% for one trading PKR 147m/day — 7,800x the liquidity, same spread.
    """
    turnovers = [1e4, 1e5, 1e6, 1e7, 1e8, 1e9]
    spreads = [liquidity_spread(price=100.0, turnover_pkr=t)[0] for t in turnovers]
    assert all(a > b for a, b in zip(spreads, spreads[1:])), spreads
    # And the range must be economically meaningful, not flat.
    assert spreads[0] / spreads[-1] > 3


def test_spread_does_not_depend_on_volatility():
    """The other failure: spread must not be a function of recent price moves.

    Cost is computed from price and turnover only, so a violent name and a calm
    name with identical liquidity must be quoted the same spread.
    """
    calm = round_trip_cost(price=100.0, turnover_pkr=5e7, daily_volatility=0.005)
    wild = round_trip_cost(price=100.0, turnover_pkr=5e7, daily_volatility=0.05)
    assert calm.spread == pytest.approx(wild.spread)


def test_volatility_only_enters_through_impact():
    calm = round_trip_cost(price=100.0, turnover_pkr=5e7, daily_volatility=0.005)
    wild = round_trip_cost(price=100.0, turnover_pkr=5e7, daily_volatility=0.05)
    assert wild.impact > calm.impact
    assert wild.total > calm.total


# --- tick grid -------------------------------------------------------------


def test_low_priced_scrip_is_floored_by_the_tick_grid():
    """A PKR 2 stock cannot quote finer than 0.01/2 = 50bp however liquid."""
    spread, floored = liquidity_spread(price=2.0, turnover_pkr=1e9)
    assert floored is True
    assert spread == pytest.approx(0.01 / 2.0)


def test_high_priced_liquid_scrip_is_not_tick_floored():
    spread, floored = liquidity_spread(price=500.0, turnover_pkr=5e7)
    assert floored is False
    assert spread < 0.01


def test_zero_or_missing_price_does_not_crash():
    spread, _ = liquidity_spread(price=0.0, turnover_pkr=1e7)
    assert np.isfinite(spread)


# --- turnover edge cases ---------------------------------------------------


def test_untraded_name_gets_the_maximum_spread():
    params = CostParams()
    for bad in (0.0, -1.0, float("nan"), None):
        spread, _ = liquidity_spread(price=100.0, turnover_pkr=bad)  # type: ignore[arg-type]
        assert spread == pytest.approx(params.max_spread)


def test_spread_is_bounded():
    params = CostParams()
    tiny, _ = liquidity_spread(price=100.0, turnover_pkr=1.0)
    huge, _ = liquidity_spread(price=100.0, turnover_pkr=1e15)
    assert tiny <= params.max_spread
    assert huge >= params.min_spread


# --- round trip assembly ---------------------------------------------------


def test_components_sum_to_total_when_uncapped():
    est = round_trip_cost(price=100.0, turnover_pkr=1e7, daily_volatility=0.02)
    assert est.total == pytest.approx(est.explicit + est.spread + est.impact, rel=1e-9)


def test_cost_is_floored_at_explicit_fees():
    est = round_trip_cost(
        price=1000.0, turnover_pkr=1e12,
        params=CostParams(explicit_round_trip=0.0, min_round_trip=0.004,
                          min_spread=0.0, tick_size_pkr=0.0),
    )
    assert est.total == pytest.approx(0.004)


def test_cost_is_capped_for_untradeable_names():
    est = round_trip_cost(price=1.0, turnover_pkr=1.0, daily_volatility=0.5,
                          params=CostParams(max_round_trip=0.05))
    assert est.total == pytest.approx(0.05)


def test_missing_volatility_drops_impact_instead_of_guessing():
    assert round_trip_cost(price=100.0, turnover_pkr=1e7,
                           daily_volatility=None).impact == 0.0


def test_thin_name_costs_more_than_liquid_name():
    liquid = round_trip_cost(price=100.0, turnover_pkr=5e8)
    thin = round_trip_cost(price=100.0, turnover_pkr=5e4)
    assert thin.total > liquid.total


# --- bars wrapper ----------------------------------------------------------


def test_from_bars_uses_median_turnover_and_last_price():
    liquid = round_trip_cost_from_bars(_bars(120, price=100, volume=5_000_000))
    thin = round_trip_cost_from_bars(_bars(120, price=100, volume=500))
    assert thin.total > liquid.total


def test_from_bars_respects_the_lookback_window():
    """A point-in-time estimate must ignore bars outside its window."""
    history = _bars(200, volume=5_000_000) + _bars(20, volume=200)
    recent = round_trip_cost_from_bars(history, lookback=20)
    full = round_trip_cost_from_bars(history, lookback=220)
    assert recent.total > full.total


def test_empty_history_returns_the_floor_not_a_crash():
    est = round_trip_cost_from_bars([])
    assert est.total == pytest.approx(CostParams().min_round_trip)


def test_from_bars_survives_corrupt_rows():
    rows = _bars(80)
    rows[10]["close"] = None
    rows[20]["volume"] = float("nan")
    rows[30]["close"] = -5
    est = round_trip_cost_from_bars(rows)
    assert np.isfinite(est.total)


def test_as_dict_is_json_safe():
    d = round_trip_cost(price=100.0, turnover_pkr=1e7).as_dict()
    assert set(d) == {"total", "explicit", "spread", "impact", "tick_floored"}
    assert isinstance(d["tick_floored"], bool)


# --- retained reference implementation -------------------------------------


def test_corwin_schultz_still_computes_for_regression_use():
    """Kept only as a reference; must not silently break."""
    price = np.full(60, 100.0)
    assert corwin_schultz_spread(price * 1.01, price * 0.99) is not None
    assert corwin_schultz_spread(np.asarray([100.0]), np.asarray([99.0])) is None


def test_corwin_schultz_is_not_on_the_default_cost_path():
    """Guards the module docstring's claim: the default path is price+turnover.

    If someone reintroduces a bar-derived spread, the volatility-independence
    test above should fail — this asserts the signature stays price/turnover so
    the regression is loud rather than quiet.
    """
    import inspect
    sig = inspect.signature(round_trip_cost)
    assert set(sig.parameters) == {
        "price", "turnover_pkr", "daily_volatility", "params"
    }
