"""Rebuild `psx_intraday` bars for one session from the AhleTrade trade tape.

Why this exists
---------------
The intraday bars are normally assembled by sampling `psx_market_snapshot`
every 60s and folding each sample into its 5-minute bucket. That can only ever
approximate a candle: a bucket sees ~5 prices, so its high and low are whichever
prints happened to be sampled, and per-bar volume has to be reverse-engineered
from a day-cumulative counter.

On 2026-08-07 it produced something worse. `merge_sample` folded the
session-wide `day_high`/`day_low` into every bucket after the first sample, so
each candle spanned the whole day's range: MEBL had 3 distinct (high, low)
pairs across all 58 bars, and 28,276 of 29,518 bars market-wide had
open == close. Every candle drew as an identical full-height hairline. The
writer bug is fixed, but the rows already stored are still wrong.

The tape carries every print, so this rebuilds the affected session exactly
rather than deleting or averaging anything. AhleTrade serves the current
session only, so `--session` cannot reach further back than today.

    python scripts/backfill_intraday_from_tape.py --dry-run
    python scripts/backfill_intraday_from_tape.py
    python scripts/backfill_intraday_from_tape.py --symbols MEBL,CNERGY
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.db.supabase import async_execute  # noqa: E402
from app.scrapers.ahletrade import AhleTradePoller  # noqa: E402
from app.services.market.intraday import PKT, bars_from_trades  # noqa: E402

# Supabase rejects very large payloads; ~500 symbols x ~70 buckets needs paging.
UPSERT_CHUNK = 500


async def _all_symbols() -> list[str]:
    res = await async_execute(
        lambda c: c.table("psx_market_snapshot").select("symbol").order("symbol")
    )
    return [r["symbol"] for r in (res.data or []) if r.get("symbol")]


async def _upsert(rows: list[dict]) -> None:
    for i in range(0, len(rows), UPSERT_CHUNK):
        chunk = rows[i : i + UPSERT_CHUNK]
        await async_execute(
            lambda c, c_=chunk: c.table("psx_intraday").upsert(
                c_, on_conflict="symbol,ts"
            )
        )


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session", help="PKT trading date (YYYY-MM-DD). Default: today.")
    ap.add_argument("--symbols", help="Comma-separated. Default: every snapshot symbol.")
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true", help="Report, write nothing.")
    args = ap.parse_args()

    session = (
        date.fromisoformat(args.session) if args.session else datetime.now(PKT).date()
    )
    today = datetime.now(PKT).date()
    if session != today:
        print(
            f"refusing: the tape only serves the current session "
            f"({today}); asked for {session}"
        )
        return 2

    symbols = (
        [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        if args.symbols
        else await _all_symbols()
    )
    if not symbols:
        print("no symbols to rebuild")
        return 1
    print(f"session {session} · {len(symbols)} symbols · dry_run={args.dry_run}")

    poller = AhleTradePoller()
    sem = asyncio.Semaphore(args.concurrency)
    rows: list[dict] = []
    no_trades: list[str] = []
    failed: list[str] = []

    async def one(sym: str) -> None:
        async with sem:
            try:
                trades = await poller.fetch_trades(sym)
            except Exception as exc:  # noqa: BLE001 - one symbol must not stop the run
                failed.append(f"{sym}: {type(exc).__name__}")
                return
        bars = bars_from_trades(trades or [], symbol=sym, session=session)
        if not bars:
            no_trades.append(sym)
            return
        rows.extend(bars)

    try:
        await asyncio.gather(*(one(s) for s in symbols))
    finally:
        await poller.close()

    rebuilt = len({r["symbol"] for r in rows})
    print(f"built {len(rows)} bars for {rebuilt} symbols")
    print(f"  no trades today: {len(no_trades)}")
    if failed:
        print(f"  fetch failures ({len(failed)}): {failed[:10]}")

    if not rows:
        print("nothing to write")
        return 1

    sample = sorted(
        (r for r in rows if r["symbol"] == rows[0]["symbol"]), key=lambda r: r["ts"]
    )[:3]
    for s in sample:
        print(
            f"  sample {s['symbol']} {s['ts'][11:16]}Z "
            f"O={s['open']} H={s['high']} L={s['low']} C={s['close']} cum={s['cum_volume']}"
        )

    if args.dry_run:
        print("dry run — no writes")
        return 0

    await _upsert(rows)
    print(f"upserted {len(rows)} bars")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
