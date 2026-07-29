"""Long-only Top-K equal-weight portfolio simulator with turnover-based one-way costs."""
from __future__ import annotations

from datetime import date

import numpy as np

from app.services.signals_v2.constants import ONE_WAY_COST


def _nav_metrics(nav: np.ndarray, kse_nav: np.ndarray) -> dict:
    rets = np.diff(nav) / nav[:-1] if len(nav) > 1 else np.asarray([])
    peak = np.maximum.accumulate(nav) if len(nav) else np.asarray([1.0])
    dd = float(np.min(nav / peak - 1)) if len(nav) else 0.0
    sd = float(np.std(rets, ddof=1)) if len(rets) > 1 else 0.0
    downside = rets[rets < 0]
    dsd = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0.0
    return {
        "net_return": round(float(nav[-1] / nav[0] - 1), 4) if len(nav) else 0.0,
        "excess_return": round(float((nav[-1] / nav[0]) - (kse_nav[-1] / kse_nav[0])), 4) if len(nav) and len(kse_nav) else 0.0,
        "max_drawdown": round(dd, 4),
        "sharpe": round(float(np.mean(rets) / sd) if sd > 0 else 0.0, 4),
        "sortino": round(float(np.mean(rets) / dsd) if dsd > 0 else 0.0, 4),
        "nav_returns": rets,
    }


def simulate_topk(daily_picks: dict[date, list[str]], prices: dict[str, dict[date, float]],
                  kse: dict[date, float], *, k: int, rebalance_days: int,
                  one_way_cost: float = ONE_WAY_COST, max_weight: float = 0.20) -> dict:
    all_dates = sorted(kse.keys())
    nav, kse_nav = 1.0, 1.0
    nav_series, kse_series = [], []
    held: dict[str, float] = {}          # symbol -> weight
    turnover_total, rebalances = 0.0, 0
    last_rebalance = None

    for i, d in enumerate(all_dates):
        # mark-to-market from previous close
        if i > 0:
            prev = all_dates[i - 1]
            port_ret = 0.0
            for sym, w in held.items():
                p0, p1 = prices.get(sym, {}).get(prev), prices.get(sym, {}).get(d)
                if p0 and p1 and p0 > 0:
                    port_ret += w * (p1 / p0 - 1)
            nav *= (1 + port_ret)
            kse_nav *= (kse[d] / kse[prev]) if kse.get(prev) else 1.0
        # rebalance on cadence
        if last_rebalance is None or (d - last_rebalance).days >= rebalance_days:
            picks = [s for s in daily_picks.get(d, []) if prices.get(s, {}).get(d, 0) > 0][:k]
            target = {s: min(max_weight, 1.0 / k) for s in picks} if picks else {}
            traded = sum(abs(target.get(s, 0) - held.get(s, 0))
                         for s in set(target) | set(held))
            nav *= (1 - one_way_cost * traded)
            turnover_total += traded
            held = target
            last_rebalance = d
            rebalances += 1
        nav_series.append(nav); kse_series.append(kse_nav)

    m = _nav_metrics(np.asarray(nav_series), np.asarray(kse_series))
    m["turnover"] = round(turnover_total / max(1, rebalances), 4)
    m["hit_rate"] = 0.0  # filled by caller from realized picks if desired
    m["avg_holding_days"] = float(rebalance_days)
    return m
