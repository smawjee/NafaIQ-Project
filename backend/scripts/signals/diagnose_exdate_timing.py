"""Follow-up: locate the actual price drop around audited ex-dates."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text  # noqa: E402

from app.repositories.base import connect  # noqa: E402
from panel import load_panel  # noqa: E402


async def run() -> None:
    async with connect() as conn:
        div = (await conn.execute(text(
            "SELECT symbol, ex_date FROM psx_dividends WHERE ex_date IS NOT NULL"
        ))).mappings().all()
    div_df = pd.DataFrame(div)
    div_df["symbol"] = div_df["symbol"].str.upper()
    div_df["ex_date"] = pd.to_datetime(div_df["ex_date"])

    panel = load_panel()
    returns = panel.returns()
    dates = panel.dates.values.astype("datetime64[ns]")
    sym_ix = {s: i for i, s in enumerate(panel.symbols)}

    offs = {-2: [], -1: [], 0: [], 1: [], 2: []}
    per_symbol: dict[str, list[float]] = {}
    for _, row in div_df.iterrows():
        col = sym_ix.get(row["symbol"])
        if col is None:
            continue
        i = np.searchsorted(dates, np.datetime64(row["ex_date"], "ns"))
        if i >= panel.shape[0]:
            continue
        for off, bucket in offs.items():
            j = i + off
            if 0 <= j < panel.shape[0] and np.isfinite(returns[j, col]):
                bucket.append(float(returns[j, col]))
        if np.isfinite(returns[i, col]):
            per_symbol.setdefault(row["symbol"], []).append(float(returns[i, col]))

    print("mean single-day return around audited ex_date (offset in sessions):")
    for off in (-2, -1, 0, 1, 2):
        v = offs[off]
        print(f"  ex_date{off:+d}: n={len(v):>4}  mean {np.mean(v):+.3%}")

    print("\nlargest single-day drops on ex_date+0 (top 10 by |drop|):")
    rows = []
    for _, row in div_df.iterrows():
        col = sym_ix.get(row["symbol"])
        if col is None:
            continue
        i = np.searchsorted(dates, np.datetime64(row["ex_date"], "ns"))
        if i >= panel.shape[0]:
            continue
        rows.append((row["symbol"], row["ex_date"].date(),
                     float(returns[i, col])))
    worst = sorted(rows, key=lambda t: t[2])[:10]
    for sym, d, r in worst:
        print(f"  {sym:>6} {d}  {r:+.2%}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
