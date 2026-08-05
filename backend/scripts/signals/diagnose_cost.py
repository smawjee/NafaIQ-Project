"""Validity check on the cost model used by the H1/H2 gates.

Both pilots reported a ~1.7% round-trip cost for the reversal top decile in
*every* liquidity tier, including the most liquid decile of PSX. That is not
credible — liquid PSX names trade at spreads measured in basis points — and the
panel-wide median cost was the explicit floor (0.40%), meaning the estimated
spread was ~0 for the typical name.

Corwin-Schultz separates spread from volatility by comparing the one-day and
two-day high-low ranges. When prices *trend* (a stock in a sustained selloff)
the two-day range exceeds sqrt(2) times the one-day range for reasons that have
nothing to do with the spread, and the estimator absorbs the difference as
spread. The reversal top decile is, by construction, the set of names that just
trended hardest — so any such bias lands exactly where it does the most damage.

This script quantifies the bias. It does NOT re-test H1 or H2 and does not
change their pre-registered thresholds; it establishes whether those verdicts
were measured with a sound instrument.

    python scripts/signals/diagnose_cost.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from panel import load_panel  # noqa: E402
from pilot_reversal import rolling_cs_spread  # noqa: E402


def main() -> None:
    panel = load_panel()
    spread = rolling_cs_spread(panel)
    turnover = pd.DataFrame(panel.close * panel.volume).rolling(
        60, min_periods=30).median().to_numpy()
    trailing20 = panel.trailing_return(20)
    vol20 = pd.DataFrame(panel.returns()).rolling(20, min_periods=10).std().to_numpy()

    ok = np.isfinite(spread) & np.isfinite(turnover) & (turnover > 0)
    print("=" * 74)
    print("1. ESTIMATED SPREAD BY LIQUIDITY DECILE")
    print("   (should fall steeply with liquidity; a flat profile means the")
    print("    estimator is not measuring liquidity at all)")
    print("=" * 74)
    t = turnover[ok]
    s = spread[ok]
    edges = np.nanquantile(t, np.linspace(0, 1, 11))
    print(f"  {'decile':>7} {'median turnover PKR':>22} {'median CS spread':>18}")
    for d in range(10):
        m = (t >= edges[d]) & (t <= edges[d + 1])
        if m.sum() == 0:
            continue
        print(f"  {d:>7} {np.median(t[m]):>22,.0f} {np.median(s[m]):>17.3%}")

    print()
    print("=" * 74)
    print("2. IS THE 'SPREAD' JUST VOLATILITY?")
    print("=" * 74)
    m = ok & np.isfinite(vol20)
    a, b = spread[m], vol20[m]
    corr = float(np.corrcoef(a, b)[0, 1])
    print(f"  corr(CS spread, 20d realised vol) = {corr:+.3f}")
    print("  A spread estimator should be only weakly related to volatility;")
    print("  a high correlation means the two are not being separated.")

    print()
    print("=" * 74)
    print("3. SPREAD BY RECENT-MOVE DECILE  <-- the bias that matters")
    print("   The reversal top decile IS the bottom trailing-return decile.")
    print("=" * 74)
    m = ok & np.isfinite(trailing20)
    tr, sp = trailing20[m], spread[m]
    q = np.nanquantile(tr, np.linspace(0, 1, 11))
    print(f"  {'decile':>7} {'median 20d return':>20} {'median CS spread':>18}")
    for d in range(10):
        sel = (tr >= q[d]) & (tr <= q[d + 1])
        if sel.sum() == 0:
            continue
        tag = "  <- biggest losers (what we buy)" if d == 0 else ""
        print(f"  {d:>7} {np.median(tr[sel]):>19.2%} {np.median(sp[sel]):>17.3%}{tag}")

    print()
    print("=" * 74)
    print("4. IMPLIED ANNUAL COST OF THE STRATEGY AT THESE ESTIMATES")
    print("=" * 74)
    for horizon, label in ((5, "5d"), (20, "20d")):
        rebalances = 252 / horizon
        for cost in (0.004, 0.017):
            print(f"  {label}: {rebalances:>5.0f} round trips/yr x {cost:.2%} "
                  f"= {rebalances * cost:>6.0%} annual drag")


if __name__ == "__main__":
    main()
