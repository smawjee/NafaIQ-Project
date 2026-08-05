"""H3 — does the reversal edge survive cost at longer horizons, with buffering?

H1/H2 concluded the edge is "about the same size as the cost". That conclusion
was measured under the two most expensive assumptions available:

  * a 20-session horizon (12.6 round trips a year), and
  * 100% turnover every rebalance (the whole decile re-bought each period).

Cost drag is (252 / horizon) * round_trip, so it falls by 3x at 60 sessions and
6x at 120. And entry/exit banding — buy the top decile, hold until the name
leaves the top 30% — is standard practice precisely because it removes the
churn that a naive decile backtest charges for.

This tests both. Nothing about the signal changes; only how it is held.
"""
from __future__ import annotations

import json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from panel import ARTIFACT_DIR, load_panel
from pilot_reversal import cost_matrix
from app.services.signals.costs import CostParams

HORIZONS = (20, 40, 60, 120)
ENTRY_Q, EXIT_Q = 0.90, 0.70          # buy top 10%, hold until below top 30%


def backtest(panel, horizon, cost, *, buffered: bool,
             date_from=None, date_to=None):
    """Equal-weight long-only book, rebalanced every `horizon` sessions.

    Cost is charged only on the names actually traded that period, which is the
    whole point: a held name pays nothing.
    """
    investable = panel.investable_mask()
    contaminated = panel.contamination_mask(back=horizon, forward=horizon)
    usable = investable & ~contaminated
    trailing = panel.trailing_return(horizon)
    forward = panel.forward_return(horizon)

    # Evaluate only inside the window, but compute masks/features on the FULL
    # panel. Slicing the panel instead would destroy the 250 bars of trailing
    # history the investable mask needs and silently discard most of a short
    # window (the 2025-26 holdout collapsed from ~20 periods to 6 that way).
    dates = panel.dates.values
    lo = 0 if date_from is None else int(np.searchsorted(dates, np.datetime64(date_from)))
    hi = panel.shape[0] if date_to is None else int(np.searchsorted(dates, np.datetime64(date_to)))

    held: set[int] = set()
    gross_r, net_r, turnovers = [], [], []

    for i in range(lo, hi, horizon):
        m = usable[i] & np.isfinite(trailing[i]) & np.isfinite(forward[i])
        n = int(m.sum())
        if n < 40:
            continue
        cols = np.flatnonzero(m)
        # Signal = reversal: biggest recent losers rank highest.
        score = -trailing[i, cols]
        pct = np.argsort(np.argsort(score)) / max(n - 1, 1)

        entry = set(cols[pct >= ENTRY_Q].tolist())
        if buffered:
            keep = {c for c, p in zip(cols.tolist(), pct.tolist())
                    if c in held and p >= EXIT_Q}
            target = entry | keep
        else:
            target = entry
        if not target:
            continue

        idx = np.fromiter(target, dtype=int)
        fwd = forward[i, idx]
        demeaned = fwd - np.mean(forward[i, cols])

        bought = target - held
        sold = held - target
        traded = len(bought) + len(sold)
        turnovers.append(traded / max(len(target), 1))

        # Half a round trip per side actually transacted.
        traded_idx = np.fromiter(bought, dtype=int) if bought else np.empty(0, int)
        cost_paid = (cost[i, traded_idx].sum() if traded_idx.size else 0.0) / len(target)

        gross_r.append(float(np.mean(demeaned)))
        net_r.append(float(np.mean(demeaned) - cost_paid))
        held = target

    g, nr = np.asarray(gross_r), np.asarray(net_r)
    per_year = 252 / horizon
    return {
        "periods": int(g.size),
        "gross_per_period": round(float(g.mean()), 5) if g.size else None,
        "net_per_period": round(float(nr.mean()), 5) if nr.size else None,
        "net_annualised": round(float(nr.mean()) * per_year, 4) if nr.size else None,
        "sharpe": round(float(nr.mean() / nr.std() * np.sqrt(per_year)), 3)
                  if nr.size > 2 and nr.std() > 0 else None,
        "avg_turnover": round(float(np.mean(turnovers)), 3) if turnovers else None,
        "win_rate": round(float((nr > 0).mean()), 3) if nr.size else None,
    }


def main():
    panel = load_panel()
    cost = cost_matrix(panel, CostParams())
    report = {"entry_q": ENTRY_Q, "exit_q": EXIT_Q, "runs": []}

    print("=" * 84)
    print("H3 — horizon x turnover buffering (reversal, long-only, after cost)")
    print("=" * 84)
    print(f"{'horizon':>8} {'buffered':>9} {'periods':>8} {'gross':>9} {'net':>9} "
          f"{'net/yr':>9} {'Sharpe':>7} {'turnov':>7} {'win':>6}")
    for h in HORIZONS:
        for buffered in (False, True):
            r = backtest(panel, h, cost, buffered=buffered)
            r.update(horizon=h, buffered=buffered)
            report["runs"].append(r)
            print(f"{h:>8} {str(buffered):>9} {r['periods']:>8} "
                  f"{r['gross_per_period']:>8.3%} {r['net_per_period']:>8.3%} "
                  f"{r['net_annualised']:>8.2%} {str(r['sharpe']):>7} "
                  f"{r['avg_turnover']:>7.2f} {r['win_rate']:>6.2f}")

    (ARTIFACT_DIR / "pilot_horizon_turnover.json").write_bytes(
        json.dumps(report, indent=2).encode("utf-8"))
    print(f"\n  report -> {ARTIFACT_DIR / 'pilot_horizon_turnover.json'}")


if __name__ == "__main__":
    main()
