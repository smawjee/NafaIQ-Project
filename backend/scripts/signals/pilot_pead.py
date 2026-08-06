"""H4 — post-earnings announcement drift on PSX.

Pre-registered in RESEARCH_LOG.md (2026-08-05) *before* this ran, and chosen
because a power calculation said it is answerable — unlike cross-sectional
alpha, which needs ~260 years of PSX data to reach t=2.

The escape from that constraint is structural: an event study's unit is the
announcement, so n is 9,543 events across 644 dates rather than 111 overlapping
calendar periods, and reported PEAD effects are an order of magnitude larger
than a per-period alpha.

Surprise proxy: PSX has no analyst estimates and only ~4 quarters per symbol of
financials, so a time-series SUE is not estimable. The standard substitute for
markets without coverage is the announcement reaction itself — the market's own
repricing is the best available measure of how surprising the news was.

Inference is **clustered by event date**. Earnings cluster heavily (14.9 events
per date, up to 328), so treating events as independent would overstate t by
roughly 4x — the same class of error that inflated every earlier number here.

    python scripts/signals/pilot_pead.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from panel import ARTIFACT_DIR, load_panel  # noqa: E402
from pilot_reversal import cost_matrix  # noqa: E402

from app.services.signals.costs import CostParams  # noqa: E402

REACTION_END = 1        # surprise measured over [0, +1]
DRIFT_START = 2         # outcome measured over [+2, +20]
DRIFT_END = 20
N_QUINTILES = 5
EXPLORE_END = pd.Timestamp("2026-01-01")
MIN_PER_DATE = 5        # need enough same-date events to form quintiles

EARNINGS_PATTERN = r"financial result|quarterly report|annual result|half year|profit"


async def load_events() -> pd.DataFrame:
    from sqlalchemy import text

    from app.repositories.base import connect

    async with connect() as conn:
        rows = (await conn.execute(text("""
            SELECT symbol, posted_at
            FROM psx_announcements
            WHERE title ~* :pattern AND symbol IS NOT NULL AND posted_at IS NOT NULL
        """), {"pattern": EARNINGS_PATTERN})).mappings().all()
    df = pd.DataFrame(rows)
    df["symbol"] = df["symbol"].str.upper()
    df["posted_at"] = pd.to_datetime(df["posted_at"], utc=True)
    return df.drop_duplicates(subset=["symbol", "posted_at"])


def build_samples(panel, events: pd.DataFrame, cost: np.ndarray) -> pd.DataFrame:
    """One row per usable event: surprise, drift, cost, event date."""
    symbol_ix = {s: i for i, s in enumerate(panel.symbols)}
    dates = panel.dates.values.astype("datetime64[ns]")
    investable = panel.investable_mask()
    returns = panel.returns()

    # Equal-weighted universe return per day — the abnormal-return benchmark.
    market = np.full(panel.shape[0], np.nan)
    for i in range(panel.shape[0]):
        m = investable[i] & np.isfinite(returns[i])
        if m.sum() >= 20:
            market[i] = float(np.mean(returns[i, m]))
    abnormal = returns - market.reshape(-1, 1)

    out: list[dict[str, Any]] = []
    for symbol, posted in zip(events["symbol"], events["posted_at"]):
        col = symbol_ix.get(symbol)
        if col is None:
            continue
        # Day 0 = first bar STRICTLY after the announcement timestamp, so an
        # after-close release is never traded on the same session.
        ts = np.datetime64(posted.tz_convert(None), "ns")
        day0 = int(np.searchsorted(dates, ts, side="right"))
        if day0 + DRIFT_END >= panel.shape[0] or day0 < 60:
            continue
        if not investable[day0, col]:
            continue

        reaction = abnormal[day0:day0 + REACTION_END + 1, col]
        drift = abnormal[day0 + DRIFT_START:day0 + DRIFT_END + 1, col]
        if not np.isfinite(reaction).all() or not np.isfinite(drift).all():
            continue

        out.append({
            "symbol": symbol,
            "event_date": dates[day0],
            "surprise": float(np.sum(reaction)),
            "drift": float(np.sum(drift)),
            "cost": float(cost[day0, col]),
        })
    return pd.DataFrame(out)


def quintile_profile(df: pd.DataFrame) -> dict[str, Any]:
    """Quintiles formed *within* each event date, then aggregated across dates.

    Forming quintiles within a date removes any market-wide effect on that day,
    and aggregating to one observation per date is what makes the t-statistic
    honest given heavy same-date clustering.
    """
    per_date: list[np.ndarray] = []
    for _, group in df.groupby("event_date"):
        if len(group) < MIN_PER_DATE:
            continue
        ranks = group["surprise"].rank(method="first")
        bucket = np.ceil(ranks / len(group) * N_QUINTILES).astype(int).clip(1, N_QUINTILES)
        means = np.full(N_QUINTILES, np.nan)
        for q in range(1, N_QUINTILES + 1):
            sel = group[bucket == q]
            if len(sel):
                means[q - 1] = float(sel["drift"].mean())
        if np.isfinite(means).all():
            per_date.append(means)

    if not per_date:
        return {"dates": 0}

    matrix = np.vstack(per_date)
    q_means = matrix.mean(axis=0)
    spread = matrix[:, -1] - matrix[:, 0]
    t_stat = float(spread.mean() / (spread.std(ddof=1) / np.sqrt(spread.size))) if spread.size > 2 else 0.0

    idx = np.arange(N_QUINTILES, dtype=np.float64)
    monotonicity = float(np.corrcoef(idx, q_means)[0, 1])

    # Long the top quintile, short the bottom: each leg pays its own round trip.
    mean_cost = float(df["cost"].mean())
    return {
        "dates": int(matrix.shape[0]),
        "events": int(len(df)),
        "quintile_drift": [round(float(v), 5) for v in q_means],
        "q5_minus_q1_gross": round(float(spread.mean()), 5),
        "q5_minus_q1_net": round(float(spread.mean()) - 2 * mean_cost, 5),
        "top_quintile_net": round(float(q_means[-1]) - mean_cost, 5),
        "t_stat_clustered": round(t_stat, 3),
        "monotonicity": round(monotonicity, 4),
        "mean_cost": round(mean_cost, 5),
    }


def verdict(explore: dict, holdout: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    net = explore.get("q5_minus_q1_net")
    if net is None or net <= 0:
        reasons.append(f"explore Q5-Q1 after cost {net} not positive")
    mono = explore.get("monotonicity")
    if mono is None or abs(mono) < 0.8:
        reasons.append(f"monotonicity {mono} below 0.8")
    t = explore.get("t_stat_clustered")
    if t is None or t < 2.0:
        reasons.append(f"clustered t {t} below 2.0")

    if reasons:
        return ("RED" if (net is None or net <= 0 or (t or 0) < 2.0) else "AMBER"), reasons

    ho_net = holdout.get("q5_minus_q1_net")
    if ho_net is None or ho_net <= 0:
        return "AMBER", [f"holdout Q5-Q1 after cost {ho_net} did not confirm"]
    return "GREEN", []


def main() -> None:
    print("=" * 78)
    print("H4 — post-earnings announcement drift (pre-registered 2026-08-05)")
    print("=" * 78)

    panel = load_panel()
    cost = cost_matrix(panel, CostParams())
    events = asyncio.run(load_events())
    print(f"  {len(events):,} earnings-type announcements")

    samples = build_samples(panel, events, cost)
    print(f"  {len(samples):,} usable events "
          f"({samples['event_date'].min()} -> {samples['event_date'].max()})"
          if len(samples) else "  no usable events")
    if samples.empty:
        return

    explore = samples[samples["event_date"] < EXPLORE_END.to_datetime64()]
    holdout = samples[samples["event_date"] >= EXPLORE_END.to_datetime64()]
    print(f"  explore {len(explore):,} events / holdout {len(holdout):,}")

    ex = quintile_profile(explore)
    ho = quintile_profile(holdout)

    for label, res in (("EXPLORE", ex), ("HOLDOUT", ho)):
        print(f"\n  --- {label} ---")
        if res.get("dates", 0) == 0:
            print("    too few events per date to form quintiles")
            continue
        print(f"    events {res['events']:,} across {res['dates']} dates")
        print("    drift by surprise quintile (low -> high):")
        print("      " + "  ".join(f"{v:+.2%}" for v in res["quintile_drift"]))
        print(f"    Q5-Q1 gross {res['q5_minus_q1_gross']:+.3%} | "
              f"net {res['q5_minus_q1_net']:+.3%}")
        print(f"    top quintile net {res['top_quintile_net']:+.3%} | "
              f"cost {res['mean_cost']:.3%}")
        print(f"    clustered t {res['t_stat_clustered']:+.2f} | "
              f"monotonicity {res['monotonicity']:+.3f}")

    v, reasons = verdict(ex, ho)
    print("\n" + "=" * 78)
    print(f"  H4 VERDICT: {v}")
    for r in reasons:
        print(f"    - {r}")
    print("=" * 78)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    report = {"explore": ex, "holdout": ho, "verdict": v, "reasons": reasons}
    (ARTIFACT_DIR / "pilot_pead.json").write_bytes(
        json.dumps(report, indent=2, default=str).encode("utf-8"))
    print(f"\n  report -> {ARTIFACT_DIR / 'pilot_pead.json'}")


if __name__ == "__main__":
    main()
