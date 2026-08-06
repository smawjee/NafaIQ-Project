"""Offline: measure how PSX stocks moved after each technical rating.

Walks historical adjusted bars for a liquid sample, recomputes the setup at
sampled points, pairs each rating with its realized forward return, and writes
src/app/ml/signals/rating_stats.json. Honest base rates — dispersion and
sample size included; no forward-looking data enters the setup at each point.
"""
from __future__ import annotations

import asyncio
import time

from app.repositories import signals_repo
from app.services.signals.rating_calibration import HORIZON, aggregate, write_artifact
from app.services.signals.technical import compute_technical_setup

SYMBOL_CAP = 180
STRIDE = 8          # sample every 8th bar to bound compute
MIN_PRIOR = 200     # setup needs >=200 bars


async def main() -> None:
    symbols = await signals_repo.top_symbols_by_volume(SYMBOL_CAP)
    samples: list[tuple[str, float]] = []
    t0 = time.perf_counter()
    done = 0
    for sym in symbols:
        try:
            bars = await signals_repo.adjusted_bars(sym, limit=3000)
        except Exception:
            continue
        closes = [b.get("close") for b in bars]
        n = len(bars)
        # The 26 components look back at most ~200 bars, so a bounded trailing
        # window gives the identical rating at O(window) instead of O(i) per point.
        WINDOW = 260
        for i in range(MIN_PRIOR, n - HORIZON, STRIDE):
            c0 = closes[i]
            cN = closes[i + HORIZON]
            try:
                c0f, cNf = float(c0), float(cN)
            except (TypeError, ValueError):
                continue
            if c0f <= 0 or cNf <= 0:
                continue
            setup = compute_technical_setup(bars[max(0, i + 1 - WINDOW): i + 1])
            if setup.status != "available" or not setup.rating:
                continue
            samples.append((setup.rating, cNf / c0f - 1.0))
        done += 1
        if done % 30 == 0:
            print(f"  {done}/{len(symbols)} symbols, {len(samples)} samples "
                  f"({time.perf_counter()-t0:.0f}s)", flush=True)

    stats = aggregate(samples)
    path = write_artifact(stats)
    print(f"\nwrote {path}")
    print(f"total samples: {stats['total_samples']}")
    for b, s in stats["buckets"].items():
        if s.get("n"):
            print(f"  {b:<15} n={s['n']:<6} p_up={s.get('p_up')}  median={s.get('median_return')}  "
                  f"p10={s.get('p10')} p90={s.get('p90')}")


if __name__ == "__main__":
    asyncio.run(main())
