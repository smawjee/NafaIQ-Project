"""Deterministic confidence + risk engine (§6, §19.8).

Every percentage/score a user sees comes from a pure function here — the LLM
never assigns a number. Functions return a typed sentinel (``None``) when inputs
are too sparse to compute a meaningful value, so the narrative can omit the
metric rather than emit a garbage number (§19.8).
"""
from __future__ import annotations

import statistics
from math import ceil
from typing import Any, Optional

Number = float


def _values(rows: list[dict[str, Any]], *keys: str) -> list[float]:
    """Extract the first present numeric key from each row."""
    out: list[float] = []
    for row in rows:
        for k in keys:
            if k in row and row[k] is not None:
                try:
                    out.append(float(row[k]))
                except (TypeError, ValueError):
                    pass
                break
    return out


def _returns(rows: list[dict[str, Any]]) -> list[float]:
    """Period-over-period returns from a value series (skips non-positive)."""
    vals = _values(rows, "value", "close", "benchmark")
    rets: list[float] = []
    for prev, cur in zip(vals, vals[1:]):
        if prev > 0:
            rets.append(cur / prev - 1.0)
    return rets


def spending_deviation_confidence(actual: float, baseline: float) -> Optional[float]:
    """How far actual spending deviates from its baseline, 0–100 (capped).

    Insufficient data (non-positive baseline) => None.
    """
    if baseline is None or baseline <= 0:
        return None
    deviation_pct = abs(actual - baseline) / baseline * 100.0
    return round(min(100.0, deviation_pct), 4)


def diversification_score(holdings: list[dict[str, Any]]) -> Optional[float]:
    """Inverted Herfindahl index, 0–100 (higher = more diversified).

    HHI = Σ wᵢ² over market-value weights. Score = (1 − HHI) · 100.
    One holding => 0 (fully concentrated). n equal holdings => (1 − 1/n)·100.
    Empty / zero total => None.
    """
    values = _values(holdings, "market_value", "value")
    total = sum(v for v in values if v > 0)
    if total <= 0:
        return None
    hhi = sum((v / total) ** 2 for v in values if v > 0)
    return round((1.0 - hhi) * 100.0, 6)


def budget_health_score(budgets: list[dict[str, Any]]) -> Optional[float]:
    """Budget health, 0–100. 100 when every budget is within its limit;
    penalized by the average over-budget percentage.

    NOTE: the exact scoring curve is a product decision worth a human review;
    this implementation only penalizes overspend (utilization > 100%).
    Empty / no valid limits => None.
    """
    overages: list[float] = []
    for b in budgets:
        limit = b.get("limit_amount") or b.get("limit")
        spent = b.get("spent")
        if not limit or limit <= 0 or spent is None:
            continue
        over_pct = max(0.0, (float(spent) - float(limit)) / float(limit) * 100.0)
        overages.append(over_pct)
    if not overages:
        return None
    return round(max(0.0, 100.0 - statistics.mean(overages)), 6)


def months_to_goal(saved: float, target: float, monthly_rate: float) -> Optional[int]:
    """Deterministic months-to-target projection.

    Already reached => 0. Non-positive contribution rate or target => None
    (cannot project).
    """
    if target is None or target <= 0 or monthly_rate is None or monthly_rate <= 0:
        return None
    remaining = float(target) - float(saved)
    if remaining <= 0:
        return 0
    return int(ceil(remaining / float(monthly_rate)))


def portfolio_volatility(history: list[dict[str, Any]]) -> Optional[float]:
    """σ of period returns from a portfolio-value series, as a percentage.

    Needs ≥ 2 returns (≥ 3 value points); otherwise None.
    """
    rets = _returns(history)
    if len(rets) < 2:
        return None
    return round(statistics.stdev(rets) * 100.0, 6)


def portfolio_beta(
    history: list[dict[str, Any]], benchmark: list[dict[str, Any]]
) -> Optional[float]:
    """Beta vs a benchmark (KSE-100): cov(port, bench) / var(bench).

    Needs ≥ 2 aligned returns and non-zero benchmark variance; else None.
    """
    port = _returns(history)
    bench = _returns(benchmark)
    n = min(len(port), len(bench))
    if n < 2:
        return None
    port, bench = port[:n], bench[:n]
    var_bench = statistics.variance(bench)
    if var_bench == 0:
        return None
    cov = statistics.covariance(port, bench)
    return round(cov / var_bench, 6)


def risk_band(
    diversification: Optional[float],
    volatility: Optional[float],
    beta: Optional[float],
) -> str:
    """Deterministic Low | Moderate | High band from the three risk inputs.

    Each of concentration (low diversification), high volatility, and high beta
    contributes one risk point. Returns "Unknown" when nothing can be assessed.
    """
    if diversification is None and volatility is None and beta is None:
        return "Unknown"
    score = 0
    if diversification is not None and diversification < 40.0:
        score += 1
    if volatility is not None and volatility > 20.0:
        score += 1
    if beta is not None and beta > 1.2:
        score += 1
    if score >= 2:
        return "High"
    if score == 1:
        return "Moderate"
    return "Low"
