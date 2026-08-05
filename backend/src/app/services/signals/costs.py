"""Per-symbol round-trip trading cost for PSX.

Every prior signals experiment tested "after cost" with a single flat number.
That is wrong in both directions at once: it over-penalises OGDC and
under-penalises a name that trades PKR 200k a day. On a market where effective
spreads differ by an order of magnitude across the universe, a flat cost can
decide GREEN vs RED on its own, so the cost model gets its own tested module.

Three components, each reported separately so a result is auditable:

1. **Explicit** — brokerage both sides + CDC/SECP/statutory + sales tax on
   commission. Retail PSX brokerage is ~0.15% per side (discount brokers less,
   full-service up to 0.25%), and a round trip lands near 0.40% all-in. There is
   no prescribed rate — it varies by broker — so this is a parameter.
2. **Spread** — a transparent schedule that is *monotone decreasing in
   turnover* and floored at the tick grid. See the note below on why it is not
   estimated from the price series.
3. **Impact** — the square-root law, impact ≈ c·σ·√(Q/ADV), applied on both
   sides. Small on liquid names, dominant on thin ones, which is precisely the
   effect a flat cost erases.

Why the spread is assumed rather than estimated
-----------------------------------------------
PSX publishes no quote data, so the obvious move is to recover the effective
spread from daily bars with Corwin-Schultz (2012). **That estimator does not
work on this market.** `scripts/signals/diagnose_cost.py` measured it across the
full 2016-2026 panel and found:

* estimated spread is essentially *flat* in liquidity — turnover decile 0
  (PKR 18.7k/day) 0.952% vs decile 9 (PKR 146.6m/day) 0.797%, despite a
  7,800x liquidity difference;
* it is a clean U-shape in recent return (0.99% for the biggest losers, 0.76%
  in the middle, 1.10% for the biggest winners), i.e. it is measuring
  volatility, not spread.

Corwin-Schultz separates the two through the ratio of one-day to two-day
high-low ranges. PSX price limits (±7.5%/±10%), limit-days and frequent
no-trade bars (high == low) violate that scaling, so a trending name has its
drift absorbed as "spread". Since the reversal signal buys exactly the names
that just trended hardest, the bias is signal-aligned and would silently decide
research verdicts.

A schedule that is transparently approximate in a *known* direction is worth
more than an estimator that is silently wrong in an unknown one — and its
parameters can be swept in a sensitivity analysis, which a black-box estimate
cannot be. `corwin_schultz_spread` is retained below for reference and
regression-testing, but it is not on the default path.

Pure functions: no DB, no I/O, no look-ahead. Every input must be a trailing
window; nothing here may see a future bar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

# (3 - 2*sqrt(2)), the Corwin-Schultz constant.
_CS_K = 3.0 - 2.0 * np.sqrt(2.0)


@dataclass(frozen=True)
class CostParams:
    """Tunable cost assumptions. Defaults target a PSX retail account.

    The spread parameters are *assumptions*, not measurements. Sweep them
    (see `scripts/signals/pilot_reversal.py --sensitivity`) rather than trusting
    any single setting.
    """

    #: Commission both sides + CDC + SECP + sales tax, as a fraction of notional.
    #: ~0.15% per side plus statutory charges lands near 0.40% for a round trip.
    explicit_round_trip: float = 0.0040

    #: PSX minimum price increment. Sets a hard floor: a quoted spread cannot be
    #: finer than the tick grid, which matters a lot for low-priced scrips.
    tick_size_pkr: float = 0.01

    #: Turnover at which `spread_at_reference` applies, in PKR/day.
    reference_turnover_pkr: float = 10_000_000.0
    #: Full quoted spread (not half) at the reference turnover.
    spread_at_reference: float = 0.0030
    #: Spread scales as (reference_turnover / turnover) ** elasticity. Empirical
    #: spread-liquidity elasticities in equity markets sit around 0.2-0.4.
    liquidity_elasticity: float = 0.30
    #: Bounds on the scheduled spread, before the tick floor is applied.
    min_spread: float = 0.0005
    max_spread: float = 0.10

    #: Fraction of average daily volume the hypothetical order consumes.
    participation: float = 0.01
    #: Coefficient c in the square-root impact law. 0.5 is the common calibration.
    impact_coefficient: float = 0.5

    #: Floor: a round trip can never be cheaper than the explicit fees.
    min_round_trip: float = 0.0040
    #: Ceiling: past this a name is untradeable, and the cap stops one absurd
    #: estimate from dominating a portfolio-level average.
    max_round_trip: float = 0.25


@dataclass(frozen=True)
class CostEstimate:
    """Round-trip cost as a fraction of notional, with its components."""

    total: float
    explicit: float
    spread: float
    impact: float
    #: True when the tick grid, not the liquidity schedule, set the spread.
    tick_floored: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": round(self.total, 6),
            "explicit": round(self.explicit, 6),
            "spread": round(self.spread, 6),
            "impact": round(self.impact, 6),
            "tick_floored": self.tick_floored,
        }


def liquidity_spread(
    *,
    price: float,
    turnover_pkr: float,
    params: CostParams | None = None,
) -> tuple[float, bool]:
    """Full round-trip spread as a fraction of price, and whether the tick floored it.

    Monotone decreasing in turnover by construction, and never finer than one
    tick. Both properties are asserted in the test suite, because they are what
    the Corwin-Schultz estimator failed to deliver on PSX data.
    """
    p = params or CostParams()

    tick_floor = (p.tick_size_pkr / price) if price and price > 0 else p.max_spread

    if turnover_pkr is None or not np.isfinite(turnover_pkr) or turnover_pkr <= 0:
        scheduled = p.max_spread
    else:
        ratio = p.reference_turnover_pkr / turnover_pkr
        scheduled = p.spread_at_reference * (ratio ** p.liquidity_elasticity)
        scheduled = float(np.clip(scheduled, p.min_spread, p.max_spread))

    spread = max(scheduled, tick_floor)
    return float(min(spread, p.max_spread)), bool(tick_floor > scheduled)


def _impact(volatility: Optional[float], participation: float, coefficient: float) -> float:
    """One-side impact under the square-root law, c * sigma * sqrt(Q/ADV)."""
    if volatility is None or not np.isfinite(volatility) or volatility <= 0:
        return 0.0
    if participation <= 0:
        return 0.0
    return float(coefficient * volatility * np.sqrt(participation))


def round_trip_cost(
    *,
    price: float,
    turnover_pkr: float,
    daily_volatility: Optional[float] = None,
    params: CostParams | None = None,
) -> CostEstimate:
    """All-in round-trip cost for one symbol, as a fraction of notional.

    ``turnover_pkr`` is the trailing median daily traded value and
    ``daily_volatility`` the daily return standard deviation (not annualised).
    Pass None for volatility to drop the impact term rather than guess it.
    """
    p = params or CostParams()

    spread, tick_floored = liquidity_spread(
        price=price, turnover_pkr=turnover_pkr, params=p
    )
    # Impact is paid on both legs.
    impact = 2.0 * _impact(daily_volatility, p.participation, p.impact_coefficient)

    total = float(np.clip(p.explicit_round_trip + spread + impact,
                          p.min_round_trip, p.max_round_trip))
    return CostEstimate(
        total=total,
        explicit=p.explicit_round_trip,
        spread=spread,
        impact=impact,
        tick_floored=tick_floored,
    )


def round_trip_cost_from_bars(
    rows: list[dict[str, Any]],
    *,
    lookback: int = 60,
    params: CostParams | None = None,
) -> CostEstimate:
    """Convenience wrapper over the repo's row-dict bar format.

    Uses only the trailing ``lookback`` bars, so a caller can hand in a full
    history and still get a point-in-time estimate.
    """
    p = params or CostParams()
    tail = rows[-lookback:] if lookback > 0 else rows
    if not tail:
        return CostEstimate(
            total=p.min_round_trip, explicit=p.explicit_round_trip,
            spread=0.0, impact=0.0, tick_floored=False,
        )

    close = np.asarray([_num(r.get("close")) for r in tail], dtype=np.float64)
    volume = np.asarray([_num(r.get("volume")) for r in tail], dtype=np.float64)

    valid = np.isfinite(close) & (close > 0)
    price = float(close[valid][-1]) if valid.any() else 0.0

    turnover_series = close * volume
    finite_turnover = turnover_series[np.isfinite(turnover_series)]
    turnover = float(np.median(finite_turnover)) if finite_turnover.size else 0.0

    return round_trip_cost(
        price=price,
        turnover_pkr=turnover,
        daily_volatility=_daily_volatility(close),
        params=p,
    )


def _daily_volatility(close: np.ndarray) -> Optional[float]:
    ok = np.isfinite(close) & (close > 0)
    series = close[ok]
    if series.size < 3:
        return None
    rets = np.diff(np.log(series))
    if rets.size < 2:
        return None
    sigma = float(np.std(rets))
    return sigma if np.isfinite(sigma) and sigma > 0 else None


def _num(value: Any) -> float:
    try:
        n = float(value)
        return n if np.isfinite(n) else np.nan
    except (TypeError, ValueError):
        return np.nan


# --- reference only -------------------------------------------------------


def corwin_schultz_spread(high: np.ndarray, low: np.ndarray) -> Optional[float]:
    """Corwin & Schultz (2012) high-low spread estimator.

    **Not used on the default cost path.** Retained for reference and because
    the diagnostic script compares against it. On PSX it measures volatility
    rather than spread — see the module docstring for the measured evidence.
    Do not reintroduce it into a cost path without re-running
    `scripts/signals/diagnose_cost.py` and showing the flat-in-liquidity and
    U-shape-in-return pathologies are gone.
    """
    h = np.asarray(high, dtype=np.float64)
    l = np.asarray(low, dtype=np.float64)
    if h.size != l.size or h.size < 2:
        return None

    ok = np.isfinite(h) & np.isfinite(l) & (h > 0) & (l > 0) & (h >= l)
    pair_ok = ok[:-1] & ok[1:]
    if not np.any(pair_ok):
        return None

    h0, h1 = h[:-1][pair_ok], h[1:][pair_ok]
    l0, l1 = l[:-1][pair_ok], l[1:][pair_ok]

    beta = np.log(h0 / l0) ** 2 + np.log(h1 / l1) ** 2
    gamma = np.log(np.maximum(h0, h1) / np.minimum(l0, l1)) ** 2

    alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / _CS_K - np.sqrt(gamma / _CS_K)
    spread = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))

    spread = np.where(np.isfinite(spread), spread, 0.0)
    spread = np.maximum(spread, 0.0)
    if spread.size == 0:
        return None
    return float(np.mean(spread))
