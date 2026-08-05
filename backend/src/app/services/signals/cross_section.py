"""Cross-sectional factor ranking across the liquid PSX universe.

A single stock's technical rating is weak information; its *rank against the
universe* is strong. For each of a small set of transparent, price-derived
factors we percentile-rank every symbol, then blend the ranks into one
composite percentile. Everything here is descriptive — it says "where does this
stock sit today relative to peers", never "what will it do next".

Pure functions over already-computed feature snapshots: no DB, no look-ahead,
no forward returns.
"""
from __future__ import annotations

from typing import Any, Optional

# name -> (feature key, higher_is_stronger, weight). Weights are transparent and
# sum to 1.0. 'low_volatility' inverts: calmer names rank higher (a quality tilt).
FACTORS: dict[str, tuple[str, bool, float]] = {
    "trend": ("_trend", True, 0.25),
    "momentum": ("ret_60d", True, 0.25),
    "rel_strength": ("relative_strength_kse20", True, 0.22),
    "low_volatility": ("volatility_20d", False, 0.16),
    "liquidity": ("turnover", True, 0.12),
}

# Ranked and reported, but deliberately NOT blended into the composite.
#
# The 20-session return percentile is what `base_rates.reversal_bucket` needs to
# place a stock in its historical cohort, and it has to be cross-sectional, so
# the daily job is the only sensible place to compute it. It stays out of the
# composite because the composite drives the user-facing "Top X% of PSX" chip —
# adding a sixth weight would silently re-rank every stock in the app.
#
# name -> (feature key, higher_is_stronger). Ascending: the biggest 20-day
# losers land near percentile 0, which is exactly what reversal_bucket expects.
CONTEXT_FACTORS: dict[str, tuple[str, bool]] = {
    "reversal_20d": ("ret_20d", True),
}


def factor_inputs(features: dict[str, Any]) -> dict[str, Optional[float]]:
    """Extract the raw factor values for one symbol from its feature snapshot."""
    trend = _blend(
        _num(features.get("price_sma50_ratio")),
        _num(features.get("price_sma200_ratio")),
    )
    base = {"_trend": trend}
    out: dict[str, Optional[float]] = {}
    for name, (key, _dir, _w) in FACTORS.items():
        out[name] = _num(base.get(key)) if key in base else _num(features.get(key))
    for name, (key, _dir) in CONTEXT_FACTORS.items():
        out[name] = _num(base.get(key)) if key in base else _num(features.get(key))
    return out


def rank_universe(universe: list[tuple[str, dict[str, Optional[float]]]]) -> dict[str, dict[str, Any]]:
    """Percentile-rank each factor across the universe and blend into a composite.

    `universe` is [(symbol, factor_inputs)]. Returns {symbol: {...}} where each
    entry carries per-factor {value, percentile} plus a composite_percentile in
    [0,100]. Percentiles are computed only over symbols with a present value, so
    a missing factor neither helps nor hurts (it drops from that symbol's blend).
    """
    symbols = [s for s, _ in universe]
    values = {s: f for s, f in universe}
    n = len(symbols)
    result: dict[str, dict[str, Any]] = {s: {"factors": {}, "universe_size": n} for s in symbols}

    rankable = {name: direction for name, (_k, direction, _w) in FACTORS.items()}
    rankable.update({name: direction for name, (_k, direction) in CONTEXT_FACTORS.items()})

    for name, higher_is_stronger in rankable.items():
        present = [(s, values[s].get(name)) for s in symbols if _num(values[s].get(name)) is not None]
        if len(present) < 3:
            continue
        ranked = _percentiles([(s, float(v)) for s, v in present], higher_is_stronger)
        for s, pct in ranked.items():
            result[s]["factors"][name] = {"value": round(values[s][name], 6), "percentile": pct}

    for s in symbols:
        num = 0.0
        den = 0.0
        for name, (_key, _dir, weight) in FACTORS.items():
            f = result[s]["factors"].get(name)
            if f is not None:
                num += weight * f["percentile"]
                den += weight
        result[s]["composite_percentile"] = round(num / den, 1) if den > 0 else None
        result[s]["factors_used"] = round(den, 4)
    return result


def _percentiles(pairs: list[tuple[str, float]], higher_is_stronger: bool) -> dict[str, float]:
    """Rank-based percentile in [0,100]; ties share the average rank."""
    n = len(pairs)
    order = sorted(pairs, key=lambda t: t[1], reverse=not higher_is_stronger)
    # average-rank for ties so identical values get identical percentiles
    out: dict[str, float] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and order[j + 1][1] == order[i][1]:
            j += 1
        # ranks i..j (0-based); percentile = mean_rank/(n-1)*100
        mean_rank = (i + j) / 2.0
        pct = round(100.0 * mean_rank / (n - 1), 1) if n > 1 else 50.0
        for k in range(i, j + 1):
            out[order[k][0]] = pct
        i = j + 1
    return out


def _blend(*vals: Optional[float]) -> Optional[float]:
    present = [v for v in vals if v is not None]
    return sum(present) / len(present) if present else None


def _num(value: Any) -> Optional[float]:
    try:
        f = float(value)
        return f if f == f and f not in (float("inf"), float("-inf")) else None
    except (TypeError, ValueError):
        return None
