"""Read-only holdings reconciliation report.

Compares every psx_holdings row against the fold of its stock_transactions lots
and prints the mismatches, split into the two kinds that need different repairs:

  NO LOTS  -> a real position whose receipt was never written. Repair with the
              opening-lot backfill migration (20260722110000).
  DRIFT    -> lots exist but disagree with the stored aggregate. Repair with a
              targeted reconciliation migration, or rebuild_holdings_from_transactions
              if the lots are known-good.

Writes nothing. Safe to run against production. It touches only psx_holdings and
stock_transactions — no market data (psx_ohlcv, psx_market_snapshot, psx_profile)
is read or modified.

Usage (from the backend directory):
    python -m scripts.portfolio.reconciliation_report
    python -m scripts.portfolio.reconciliation_report --portfolio 19
"""
from __future__ import annotations

import argparse
import asyncio

from app.services.portfolio import detect_holding_drift


async def _run(portfolio_id: int | None) -> int:
    rows = await detect_holding_drift(portfolio_id)
    no_lots = [r for r in rows if not r["has_lots"]]
    drifted = [r for r in rows if r["has_lots"]]

    print(f"Holdings needing repair: {len(rows)}")
    print(f"  no backing lots : {len(no_lots)}")
    print(f"  drifted         : {len(drifted)}")

    if no_lots:
        print("\n--- NO LOTS (backfill an opening lot) ---")
        print(f"{'pf':>6}  {'symbol':<10} {'shares':>10} {'avg_cost':>12}")
        for r in sorted(no_lots, key=lambda x: (x["portfolio_id"], x["symbol"])):
            print(f"{r['portfolio_id']:>6}  {r['symbol']:<10} "
                  f"{r['holding_shares']:>10} {r['holding_avg_cost']:>12.4f}")

    if drifted:
        print("\n--- DRIFT (lots disagree with the stored aggregate) ---")
        print(f"{'pf':>6}  {'symbol':<10} {'stored_sh':>10} {'lot_sh':>8} "
              f"{'stored_avg':>12} {'lot_avg':>12}")
        for r in sorted(drifted, key=lambda x: (x["portfolio_id"], x["symbol"])):
            print(f"{r['portfolio_id']:>6}  {r['symbol']:<10} "
                  f"{r['holding_shares']:>10} {r['expected_shares']:>8} "
                  f"{r['holding_avg_cost']:>12.4f} {r['expected_avg_cost']:>12.4f}")

    if not rows:
        print("\nEvery holding reconstructs from its transaction history.")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Holdings reconciliation report")
    parser.add_argument("--portfolio", type=int, default=None,
                        help="restrict to one portfolio id (default: all)")
    args = parser.parse_args()
    asyncio.run(_run(args.portfolio))


if __name__ == "__main__":
    main()
