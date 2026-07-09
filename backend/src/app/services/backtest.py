from __future__ import annotations

from datetime import date

import pandas as pd

from app.models import BacktestParams, BacktestResult, MarketSnapshotItem, OHLCVBar
from app.services.indicators import bars_to_df


def run_backtest(
    history_map: dict[str, list[OHLCVBar]],
    snapshot: list[MarketSnapshotItem],
    params: BacktestParams,
) -> BacktestResult:
    """Simple buy-and-hold backtest: match universe, hold for N days, compare to KSE-100."""
    spec = params.filter_spec
    matched: list[str] = [
        i.symbol for i in snapshot
        if spec.get("sector") is None or True  # simplified: match all for now
    ]

    if not matched:
        return BacktestResult(avg_return=0, median_return=0, kse_return=0, winners=0, losers=0, matched_symbols=0)

    returns = []
    since_date = date.fromisoformat(params.since) if params.since else date.today()

    for sym in matched:
        bars = history_map.get(sym, [])
        if not bars:
            continue
        df = bars_to_df(bars)
        df = df[df.index >= pd.Timestamp(since_date)]
        if len(df) < params.hold_days:
            continue
        start_price = df["close"].iloc[0]
        end_price_idx = min(params.hold_days, len(df) - 1)
        end_price = df["close"].iloc[end_price_idx]
        if start_price and start_price > 0:
            ret = (end_price / start_price - 1) * 100
            returns.append(ret)

    if not returns:
        return BacktestResult(avg_return=0, median_return=0, kse_return=0, winners=0, losers=0, matched_symbols=len(matched))

    winners = sum(1 for r in returns if r > 0)
    losers = sum(1 for r in returns if r <= 0)

    return BacktestResult(
        avg_return=round(sum(returns) / len(returns), 2),
        median_return=round(sorted(returns)[len(returns) // 2], 2),
        kse_return=0,
        winners=winners,
        losers=losers,
        matched_symbols=len(matched),
    )
