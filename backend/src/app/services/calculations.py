"""Centralized pure-function calculations.

These functions take plain data structures and return plain data structures.
No I/O. No DB access. No API clients. Components and services consume these
to keep math in one place.

Naming convention: every function returns a typed dict; inputs are typed.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional


# ----- Portfolio ---------------------------------------------------------


def holding_value(shares: float, latest_price: float) -> float:
    if shares is None or latest_price is None:
        return 0.0
    return float(shares) * float(latest_price)


def cost_basis(shares: float, avg_cost: float) -> float:
    if shares is None or avg_cost is None:
        return 0.0
    return float(shares) * float(avg_cost)


def unrealized_pnl(current_value: float, cost: float) -> float:
    return round(current_value - cost, 2)


def pnl_pct(unrealized: float, cost: float) -> float:
    if cost <= 0:
        return 0.0
    return round((unrealized / cost) * 100, 2)


def today_pnl(shares: float, latest_price: float, previous_close: float) -> float:
    if shares is None or latest_price is None or previous_close is None:
        return 0.0
    return round(float(shares) * (float(latest_price) - float(previous_close)), 2)


def today_pnl_pct(today: float, base_value: float) -> float:
    if base_value <= 0:
        return 0.0
    return round((today / base_value) * 100, 2)


def compute_holding_row(
    symbol: str,
    shares: float,
    avg_cost: float,
    latest_price: Optional[float],
    previous_close: Optional[float],
    today_qty: Optional[float] = None,
    today_avg_price: Optional[float] = None,
    day_change: Optional[float] = None,
) -> dict[str, Any]:
    """Return a typed holding row for portfolio aggregation.

    When today_qty / today_avg_price are provided (shares bought today via
    stock_transactions), today_pnl splits into:
      - today's bought shares: (current_price - today's avg buy price) × today_qty
      - older shares:          (current_price - previous_close) × (shares - today_qty)
    Otherwise today_pnl uses previous_close for all shares (previous behaviour).
    """
    # Unpriceable holdings (no live snapshot AND no EOD close) fall back to cost
    # basis so they read flat (0%) instead of a spurious -100% loss.
    priced = latest_price is not None
    price = latest_price if priced else avg_cost
    cur = holding_value(shares, price)
    cost = cost_basis(shares, avg_cost)
    pnl = unrealized_pnl(cur, cost)
    pct = pnl_pct(pnl, cost)
    if not priced:
        # No real price -> no meaningful daily change.
        t_pnl = 0.0
        today_base_val = 0.0
    elif day_change is not None and not (today_qty and today_qty > 0):
        # Prefer PSX's OWN reported day change (per share). This is robust when
        # the stored previous_close happens to equal the current price — e.g. a
        # stale/empty snapshot makes current_price fall back to the latest EOD
        # close, which equals previous_close, collapsing today's P/L to 0.
        t_pnl = float(day_change) * shares
        today_base_val = (price - float(day_change)) * shares
    elif today_qty and today_qty > 0:
        bought_today = min(today_qty, shares)
        old_shares = max(shares - today_qty, 0)
        t_pnl = (price - (today_avg_price or 0.0)) * bought_today
        if previous_close is not None:
            t_pnl += (price - previous_close) * old_shares
        today_base_val = ((today_avg_price or 0.0) * bought_today)
        if previous_close is not None:
            today_base_val += previous_close * old_shares
    else:
        t_pnl = today_pnl(shares, price, previous_close or 0.0)
        today_base_val = (previous_close or 0.0) * shares if previous_close is not None else 0.0
    return {
        "symbol": symbol,
        "shares": shares,
        "avg_cost": avg_cost,
        "current_price": latest_price,
        "previous_close": previous_close,
        "market_value": round(cur, 2),
        "cost_basis": round(cost, 2),
        "unrealized_pnl": pnl,
        "pnl_pct": pct,
        "today_pnl": round(t_pnl, 2),
        "today_base": round(today_base_val, 2),
    }


def aggregate_portfolio_totals(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """Sum totals across many holding rows."""
    total_value = round(sum(h.get("market_value", 0) for h in holdings), 2)
    total_cost = round(sum(h.get("cost_basis", 0) for h in holdings), 2)
    total_pnl = round(sum(h.get("unrealized_pnl", 0) for h in holdings), 2)
    total_pct = pnl_pct(total_pnl, total_cost)
    total_today = round(sum(h.get("today_pnl", 0) for h in holdings), 2)

    def _today_base(h: dict[str, Any]) -> float:
        tb = h.get("today_base", 0)
        if tb and tb > 0:
            return tb
        # backward-compat: value shares against previous close when today_base
        # isn't supplied (older holding rows / direct callers).
        pc = h.get("previous_close")
        return pc * h.get("shares", 0) if pc else 0.0

    today_base_total = round(sum(_today_base(h) for h in holdings), 2)
    total_today_pct = today_pnl_pct(total_today, today_base_total)
    return {
        "total_market_value": total_value,
        "total_cost_basis": total_cost,
        "total_unrealized_pnl": total_pnl,
        "total_unrealized_pnl_pct": total_pct,
        "today_pnl": total_today,
        "today_pnl_pct": total_today_pct,
    }


def allocation_by_stock(holdings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = sum(h.get("market_value", 0) for h in holdings) or 1.0
    out: list[dict[str, Any]] = []
    for h in holdings:
        v = h.get("market_value", 0)
        out.append(
            {
                "symbol": h.get("symbol"),
                "value": round(v, 2),
                "pct": round((v / total) * 100, 2),
            }
        )
    out.sort(key=lambda x: x["value"], reverse=True)
    return out


def allocation_by_sector(
    holdings: list[dict[str, Any]],
    sector_map: dict[str, Optional[str]],
) -> list[dict[str, Any]]:
    by_sector: dict[str, float] = {}
    for h in holdings:
        sym = h.get("symbol", "")
        sector = sector_map.get(sym) or "Other"
        by_sector[sector] = by_sector.get(sector, 0.0) + h.get("market_value", 0)
    total = sum(by_sector.values()) or 1.0
    out = [
        {
            "sector": sec,
            "value": round(v, 2),
            "pct": round((v / total) * 100, 2),
        }
        for sec, v in by_sector.items()
    ]
    out.sort(key=lambda x: x["value"], reverse=True)
    return out


def portfolio_history_from_ohlcv(
    holdings: list[dict[str, Any]],
    ohlcv: dict[str, list[dict[str, Any]]],
    days: int = 180,
) -> list[dict[str, Any]]:
    """Build a per-day portfolio value series.

    holdings: each item has symbol + shares.
    ohlcv: symbol -> list of {date, close} sorted ASC.
    """
    if not holdings:
        return []
    # collect all dates that have at least one symbol price
    date_set: set[date] = set()
    per_sym: dict[str, dict[date, float]] = {}
    for sym, bars in ohlcv.items():
        m: dict[date, float] = {}
        for b in bars:
            d = b.get("date")
            if isinstance(d, str):
                try:
                    d_obj = date.fromisoformat(d)
                except ValueError:
                    continue
            elif isinstance(d, date):
                d_obj = d
            else:
                continue
            m[d_obj] = float(b.get("close") or 0)
            date_set.add(d_obj)
        per_sym[sym] = m
    sorted_dates = sorted(date_set, reverse=True)[:days]
    sorted_dates.reverse()
    points: list[dict[str, Any]] = []
    for d in sorted_dates:
        total = 0.0
        for h in holdings:
            sym = h.get("symbol")
            shares = h.get("shares", 0) or 0
            close = per_sym.get(sym, {}).get(d)
            if close is not None:
                total += shares * close
        points.append(
            {
                "date": d.isoformat(),
                "label": d.strftime("%b %d"),
                "value": round(total, 2),
            }
        )
    return points


def performance_vs_kse100(
    portfolio_points: list[dict[str, Any]],
    kse100_points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize both series to the first point and combine.

    Both inputs are date-ordered lists of {date, value/close}.
    """
    if not portfolio_points or not kse100_points:
        return []
    base_port = portfolio_points[0].get("value") or 0
    base_kse = kse100_points[0].get("close") or kse100_points[0].get("value") or 0
    if base_port <= 0 or base_kse <= 0:
        return []
    # join on date
    kse_map = {p.get("date"): p.get("close") or p.get("value") for p in kse100_points}
    out: list[dict[str, Any]] = []
    for p in portfolio_points:
        d = p.get("date")
        kse_close = kse_map.get(d)
        if kse_close is None:
            continue
        out.append(
            {
                "date": d,
                "label": p.get("label") or str(d),
                "value": round(p.get("value") or 0, 2),
                "benchmark": round((kse_close / base_kse) * base_port, 2),
            }
        )
    return out


# ----- Finance -----------------------------------------------------------


def savings_rate(income: float, expenses: float) -> float:
    if income <= 0:
        return 0.0
    return round(((income - expenses) / income) * 100, 2)


def budget_usage(spent: float, limit_amount: float) -> float:
    if limit_amount <= 0:
        return 0.0
    return round((spent / limit_amount) * 100, 2)


def goal_progress(saved: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return round((saved / target) * 100, 2)


def bill_due_in_days(due: Optional[date], today: Optional[date] = None) -> Optional[int]:
    if due is None:
        return None
    today = today or date.today()
    return (due - today).days


def compare_to_last_month(
    current: float, last: float
) -> dict[str, Any]:
    if last == 0:
        return {"absolute": round(current - last, 2), "pct": None}
    return {
        "absolute": round(current - last, 2),
        "pct": round(((current - last) / abs(last)) * 100, 2),
    }


# ----- Zakat -------------------------------------------------------------


def zakat_estimate(
    total_assets: float,
    total_deductions: float,
    nisab_value: float,
    rate_pct: float = 2.5,
) -> dict[str, Any]:
    """Standard 2.5% Zakat estimate.

    Returns net_zakatable, zakat_due, and whether nisab threshold is met.
    """
    net = max(total_assets - total_deductions, 0.0)
    nisab_met = net >= nisab_value
    due = round(net * (rate_pct / 100.0), 2) if nisab_met else 0.0
    return {
        "total_assets": round(total_assets, 2),
        "total_deductions": round(total_deductions, 2),
        "net_zakatable": round(net, 2),
        "nisab_value": round(nisab_value, 2),
        "nisab_met": nisab_met,
        "rate_pct": rate_pct,
        "zakat_due": due,
    }


# ----- Time helpers ------------------------------------------------------


def month_string(d: Optional[datetime] = None) -> str:
    d = d or datetime.now(timezone.utc)
    return f"{d.year:04d}-{d.month:02d}"


def previous_month_string(month: str) -> str:
    year_s, m_s = month.split("-")
    year, m = int(year_s), int(m_s)
    if m == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{m - 1:02d}"
