"""Verify Arm B's ex-date strip: does it use ann_date or the real ex-date?

psx_corporate_actions has ONLY ann_date (no ex_date column). The price gap
concentrates at ex_date-2..-1 (measured in diagnose_exdate_timing.py), which
is weeks after the announcement. So stripping events within +-1 session of
ann_date removes almost nothing that matters. This script counts how many
B75/B95 events actually sit on/near a real ex-date (from psx_dividends, which
has ex_date) and whether the implemented strip caught them.
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
from panel import load_panel  # noqa: E402
from pilot_limit_bounce import find_events, BAND_75, BAND_95, NO_OVERLAP_SESSIONS  # noqa: E402


async def run() -> None:
    async with connect() as conn:
        ca = (await conn.execute(text(
            "SELECT symbol, ann_date FROM psx_corporate_actions"
        ))).mappings().all()
        div = (await conn.execute(text(
            "SELECT symbol, ex_date FROM psx_dividends WHERE ex_date IS NOT NULL"
        ))).mappings().all()
    ca_dates = {(r["symbol"].upper(), np.datetime64(r["ann_date"])) for r in ca}
    ex_dates = {(r["symbol"].upper(), np.datetime64(r["ex_date"])) for r in div}
    print(f"ann-date strip set: {len(ca_dates)} (has NO ex_date column)")
    print(f"real ex-date set (psx_dividends, 2025-03+): {len(ex_dates)}")

    panel = load_panel()
    from pilot_reversal import cost_matrix  # noqa: E402
    from app.services.signals.costs import CostParams  # noqa: E402

    cost = cost_matrix(panel, CostParams())
    events = find_events(panel, cost, ca_dates)
    dates = panel.dates.values.astype("datetime64[ns]")

    for band, df in events.items():
        if df.empty:
            continue
        df = df.copy()
        df["col"] = [int(np.where(panel.symbols == s)[0][0]) for s in df["symbol"]]
        # Events whose date is within +-2 sessions of a REAL ex-date.
        near_ex = []
        for _, row in df.iterrows():
            sym, day = str(row["symbol"]), np.datetime64(row["event_date"], "D")
            for off in range(-2, 3):
                d = day + np.timedelta64(off, "D")
                if (sym, d) in ex_dates:
                    near_ex.append((row["event_date"], sym))
                    break
        # Of those, how many were also within +-1 session of an ann_date
        # (i.e. actually stripped by the implementation)?
        stripped_also = 0
        for _, row in df.iterrows():
            sym, day = str(row["symbol"]), np.datetime64(row["event_date"], "D")
            for off in (-1, 0, 1):
                if (sym, day + np.timedelta64(off, "D")) in ca_dates:
                    stripped_also += 1
                    break
        print(f"\n{band}: {len(df)} events total; "
              f"{len(near_ex)} on/near a REAL ex-date; "
              f"stripped by ann-date rule: {stripped_also}")
        print("  sample real-ex-date events that survived the strip:")
        for d, s in near_ex[:5]:
            print(f"    {s} {pd.Timestamp(d).date()}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
