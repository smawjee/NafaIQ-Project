"""Diagnostics for the pilot retrospective (read-only).

Tests four contamination/validity hypotheses against the actual data:

  H1  Arm C front-running: entry at txn_date precedes public disclosure by
      (notice_date - txn_date). If the gap is weeks, the CAR includes
      non-tradeable pre-disclosure drift.
  H2  Arm B ex-date strip coverage: psx_corporate_actions ann_date min.
      Events before that date were not ex-date-stripped.
  H3  Unadjusted ex-dividend contamination: mean single-day return on audited
      ex_dates (psx_dividends) vs baseline; count of [4%,12%] one-day drops
      per year in the panel (potential unadjusted cash-dividend gaps).
  H4  Where the cash-dividend damage would land: the overlap between Arm A's
      value quintile (high E/P = dividend payers) and ex-dates.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text  # noqa: E402

from app.repositories.base import connect  # noqa: E402


async def run() -> None:
    async with connect() as conn:
        # --- H1: notice vs txn gap (Arm C entry timing) --------------------
        rows = (await conn.execute(text("""
            SELECT notice_date, txn_date, direction
            FROM psx_insider_transactions
            WHERE direction = 'buy' AND txn_date IS NOT NULL
              AND notice_date IS NOT NULL
        """))).mappings().all()
        df = pd.DataFrame(rows)
        gap = (pd.to_datetime(df["notice_date"]) - pd.to_datetime(df["txn_date"])).dt.days
        print("H1  Arm C entry timing (buy rows)")
        print(f"    n={len(df)}  gap notice-txn: median {gap.median():.0f}d, "
              f"mean {gap.mean():.1f}d, p10 {gap.quantile(.1):.0f}, p90 {gap.quantile(.9):.0f}")
        print(f"    rows where txn_date == notice_date: {(gap == 0).mean():.1%}")
        print(f"    rows where txn_date > notice_date (data oddity): {(gap < 0).mean():.1%}")

        # --- H2: CA strip coverage -----------------------------------------
        r = (await conn.execute(text(
            "SELECT min(ann_date) AS lo, max(ann_date) AS hi, count(*) AS n "
            "FROM psx_corporate_actions"
        ))).mappings().first()
        print("\nH2  Corporate-action strip set (Arm B)")
        print(f"    ann_date {r['lo']} -> {r['hi']}  n={r['n']}")
        print(f"    => B75/B95 events before {r['lo']} were NOT ex-date-stripped")

        # --- H3: ex-dividend contamination in the panel ---------------------
        div = (await conn.execute(text(
            "SELECT symbol, ex_date FROM psx_dividends WHERE ex_date IS NOT NULL"
        ))).mappings().all()
    div_df = pd.DataFrame(div)
    div_df["symbol"] = div_df["symbol"].str.upper()
    div_df["ex_date"] = pd.to_datetime(div_df["ex_date"])
    print(f"\nH3  Unadjusted ex-dividend contamination (psx_dividends n={len(div_df)})")

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from panel import load_panel  # noqa: E402

    panel = load_panel()
    returns = panel.returns()
    dates = pd.DatetimeIndex(panel.dates)
    sym_ix = {s: i for i, s in enumerate(panel.symbols)}

    # Mean single-day return on audited ex-dates vs baseline (same symbol, same year).
    ex_ret, base_ret = [], []
    for _, row in div_df.iterrows():
        col = sym_ix.get(row["symbol"])
        if col is None:
            continue
        i = np.searchsorted(dates.values.astype("datetime64[ns]"),
                            np.datetime64(row["ex_date"], "ns"))
        if i >= panel.shape[0]:
            continue
        r_ex = returns[i, col]
        if not np.isfinite(r_ex):
            continue
        ex_ret.append(r_ex)
        yr = pd.Timestamp(dates[i]).year
        same_yr = [(j, col) for j in range(panel.shape[0])
                   if pd.Timestamp(dates[j]).year == yr]
        baseline = [returns[j, c] for j, c in same_yr if np.isfinite(returns[j, c])]
        if baseline:
            base_ret.append(np.mean(baseline))
    if ex_ret:
        print(f"    matched ex-dates: {len(ex_ret)}")
        print(f"    mean return on ex-date: {np.mean(ex_ret):+.3%} "
              f"(vs symbol-year baseline {np.mean(base_ret):+.3%})")

    # Density of [4%,12%] one-day drops per year — the band cash ex-dates occupy.
    drops = np.isfinite(returns) & (returns < -0.04) & (returns > -0.12)
    by_year = pd.Series(drops.sum(axis=1), index=dates).groupby(dates.year).sum()
    print("    one-day drops in [-12%, -4%] per year (cash-ex-date band):")
    for yr, n in by_year.items():
        days = (dates.year == yr).sum()
        print(f"      {yr}: {int(n):>5}  ({100*n/days:5.1f} per session)")


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
