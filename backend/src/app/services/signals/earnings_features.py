"""Point-in-time earnings features from PSX quarterly/annual financials.

PSX has no published analyst estimates, so 'surprise' is defined against a
time-series expectation (standardized unexpected earnings, SUE): the latest
year-over-year EPS change relative to the mean/std of the firm's own historical
YoY changes. Everything is computed from data at or before an as-of fiscal
period, so a feature vector can never see an EPS the market had not yet reported.

These are pure functions over already-loaded rows — no DB, no outcomes, no
look-ahead. They feed the (still-gated) event model; nothing here is served as a
forecast.
"""
from __future__ import annotations

import math
import re
from typing import Any, Optional

_PERIOD_RE = re.compile(r"^\s*(\d{4})\s*Q\s*([1-4])\s*$", re.IGNORECASE)


def parse_period(period: str | None) -> Optional[tuple[int, int]]:
    """'2026Q3' -> (2026, 3). Returns None for anything unparseable."""
    if not period:
        return None
    m = _PERIOD_RE.match(str(period))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _num(x: Any) -> Optional[float]:
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def eps_series(quarterly_rows: list[dict[str, Any]], *, as_of: tuple[int, int] | None = None):
    """Ascending [((year, q), eps)] with EPS present, truncated at the as-of period."""
    out: list[tuple[tuple[int, int], float]] = []
    for row in quarterly_rows:
        pq = parse_period(row.get("period"))
        eps = _num(row.get("eps"))
        if pq is None or eps is None:
            continue
        if as_of is not None and pq > as_of:
            continue  # point-in-time: never use a quarter not yet reported
        out.append((pq, eps))
    out.sort(key=lambda t: t[0])
    # De-dup on period (keep last seen) while preserving order.
    dedup: dict[tuple[int, int], float] = {}
    for pq, eps in out:
        dedup[pq] = eps
    return sorted(dedup.items(), key=lambda t: t[0])


def _yoy_changes(series) -> list[float]:
    """EPS[(y,q)] - EPS[(y-1,q)] for every quarter that has a prior-year match."""
    lookup = {pq: eps for pq, eps in series}
    changes: list[float] = []
    for (year, q), eps in series:
        prior = lookup.get((year - 1, q))
        if prior is not None:
            changes.append(eps - prior)
    return changes


def _std(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return math.sqrt(var)


def compute_earnings_features(
    quarterly_rows: list[dict[str, Any]],
    annual_rows: list[dict[str, Any]] | None = None,
    *,
    as_of_period: str | None = None,
) -> dict[str, Any]:
    """Leakage-safe earnings features as of a fiscal period (default: latest)."""
    as_of = parse_period(as_of_period)
    series = eps_series(quarterly_rows, as_of=as_of)
    out: dict[str, Any] = {
        "eps_latest": None, "eps_change": None, "earnings_surprise": None,
        "eps_ttm": None, "eps_ttm_growth": None, "profitability_quality": None,
        "as_of_period": None, "quarters_available": len(series),
    }
    if not series:
        return out

    (latest_pq, latest_eps) = series[-1]
    out["eps_latest"] = round(latest_eps, 4)
    out["as_of_period"] = f"{latest_pq[0]}Q{latest_pq[1]}"

    lookup = {pq: eps for pq, eps in series}
    prior_yoy = lookup.get((latest_pq[0] - 1, latest_pq[1]))
    if prior_yoy is not None:
        latest_change = latest_eps - prior_yoy
        out["eps_change"] = round(latest_change / (abs(prior_yoy) + 1e-6), 4)
        # SUE: standardize the latest YoY change against the firm's own history.
        hist = _yoy_changes(series[:-1])  # exclude the latest to avoid self-reference
        if len(hist) >= 2:
            mean = sum(hist) / len(hist)
            sd = _std(hist)
            if sd > 0:
                out["earnings_surprise"] = round((latest_change - mean) / sd, 4)

    # Trailing-twelve-month EPS + its YoY growth (needs 8 consecutive quarters).
    if len(series) >= 4:
        ttm = sum(eps for _, eps in series[-4:])
        out["eps_ttm"] = round(ttm, 4)
        if len(series) >= 8:
            prior_ttm = sum(eps for _, eps in series[-8:-4])
            if abs(prior_ttm) > 1e-6:
                out["eps_ttm_growth"] = round((ttm - prior_ttm) / abs(prior_ttm), 4)

    # Profitability quality from the latest annual margin known as-of.
    out["profitability_quality"] = _profitability_quality(annual_rows or [], as_of_year=latest_pq[0])
    return out


async def load_earnings_features(symbol: str, *, as_of_period: str | None = None) -> dict[str, Any]:
    """Load financials for a symbol and compute point-in-time earnings features."""
    from app.repositories import signals_repo

    quarterly = await signals_repo.quarterly_financials(symbol)
    annual = await signals_repo.annual_financials(symbol)
    return compute_earnings_features(quarterly, annual, as_of_period=as_of_period)


def _profitability_quality(annual_rows: list[dict[str, Any]], *, as_of_year: int) -> Optional[float]:
    """Latest ROE (fallback net margin) reported at or before the as-of year, as a fraction."""
    best_year = None
    best_val = None
    for row in annual_rows:
        year = row.get("year")
        if not isinstance(year, int) or year > as_of_year:
            continue
        val = _num(row.get("roe"))
        if val is None:
            val = _num(row.get("npm"))
        if val is None:
            continue
        if best_year is None or year > best_year:
            best_year, best_val = year, val
    if best_val is None:
        return None
    return round(best_val / 100.0, 4)  # reported as a percent → fraction
